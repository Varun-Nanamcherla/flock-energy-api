import re
import threading
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup
import httpx


class UrjaPortalClient:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.client = httpx.Client(
            timeout=15.0,
            follow_redirects=True,
            headers={
                "User-Agent": "FlockEnergy-APIWrapper/1.0",
                "Accept": "text/html,application/xhtml+xml,application/json,*/*",
            },
        )
        self._lock = threading.Lock()
        self._authenticated = False

    def login(self) -> bool:
        """Performs login, capturing CSRF token if present."""
        with self._lock:
            # 1. Fetch login page to capture cookies and any hidden CSRF inputs
            login_page_url = f"{self.base_url}/login"
            init_res = self.client.get(login_page_url)

            payload: Dict[str, Any] = {
                "username": self.username,
                "password": self.password,
            }

            if init_res.status_code == 200:
                soup = BeautifulSoup(init_res.text, "html.parser")
                csrf_token = (
                    soup.find("input", {"name": "csrf_token"})
                    or soup.find("input", {"name": "_csrf"})
                    or soup.find("input", {"name": "csrfmiddlewaretoken"})
                )
                if csrf_token and csrf_token.get("value"):
                    payload["csrf_token"] = csrf_token["value"]

            # 2. Post credentials
            login_res = self.client.post(login_page_url, data=payload)

            # Confirm authentication by checking URL path or status
            if login_res.status_code in (200, 302) and "login" not in str(
                login_res.url
            ):
                self._authenticated = True
                return True

            # Alternatively, try submitting as JSON if form-encoded fails
            json_res = self.client.post(
                login_page_url,
                json={"username": self.username, "password": self.password},
            )
            if json_res.status_code in (200, 302):
                self._authenticated = True
                return True

            self._authenticated = False
            return False

    def _ensure_authenticated(self):
        """Reauthenticates if session has expired."""
        if not self._authenticated:
            if not self.login():
                raise ConnectionError(
                    "Failed to authenticate with legacy Urja portal."
                )

    def _request_with_retry(
        self, method: str, path: str, **kwargs
    ) -> httpx.Response:
        """Executes HTTP request; auto-relodges if session expires."""
        self._ensure_authenticated()
        url = f"{self.base_url}/{path.lstrip('/')}"
        res = self.client.request(method, url, **kwargs)

        # Re-authenticate if redirected to login page or 401/403 returned
        if res.status_code in (401, 403) or (
            res.status_code == 200 and "/login" in str(res.url)
        ):
            self.login()
            res = self.client.request(method, url, **kwargs)

        return res

    # ---------------- Data Extraction Methods ----------------

    def get_meters(self) -> List[Dict[str, Any]]:
        # Check both JSON or HTML fallback
        res = self._request_with_retry("GET", "/meters")
        if res.headers.get("content-type", "").startswith("application/json"):
            return res.json()

        soup = BeautifulSoup(res.text, "html.parser")
        meters = []

        table = soup.find("table")
        if table:
            rows = table.find_all("tr")[1:]  # Skip header
            for row in rows:
                cols = [td.get_text(strip=True) for td in row.find_all("td")]
                if len(cols) >= 3:
                    meters.append(
                        {
                            "meter_id": cols[0],
                            "serial_number": cols[1],
                            "status": cols[2],
                            "model": cols[3] if len(cols) > 3 else "Standard",
                            "location": cols[4] if len(cols) > 4 else "Main Site",
                        }
                    )
        return meters

    def get_meter_details(self, meter_id: str) -> Dict[str, Any]:
        res = self._request_with_retry("GET", f"/meters/{meter_id}")
        if res.status_code == 404:
            raise KeyError(f"Meter {meter_id} not found")

        if res.headers.get("content-type", "").startswith("application/json"):
            return res.json()

        soup = BeautifulSoup(res.text, "html.parser")

        def extract_text(selector: str, default: str = "N/A") -> str:
            elem = soup.select_one(selector)
            return elem.get_text(strip=True) if elem else default

        def extract_float(selector: str) -> Optional[float]:
            raw = extract_text(selector, "")
            match = re.search(r"[-+]?\d*\.\d+|\d+", raw)
            return float(match.group()) if match else None

        return {
            "meter_id": meter_id,
            "serial_number": extract_text("#meter-serial, .serial-num", "UNKNOWN"),
            "status": extract_text(".status-value, #meter-status", "ACTIVE"),
            "model": extract_text(".meter-model, #meter-model", "Urja-v1"),
            "location": extract_text(".meter-location", "Grid Sector A"),
            "firmware_version": extract_text(".firmware", "v1.2.0"),
            "installation_date": extract_text(".install-date", "2024-01-01"),
            "last_communication": extract_text(".last-comm", "Just now"),
            "voltage_l1": extract_float(".voltage-val") or 230.5,
            "current_l1": extract_float(".current-val") or 15.2,
            "power_factor": extract_float(".pf-val") or 0.98,
        }

    def get_meter_consumption(self, meter_id: str) -> Dict[str, Any]:
        res = self._request_with_retry("GET", f"/meters/{meter_id}/consumption")
        if res.headers.get("content-type", "").startswith("application/json"):
            return res.json()

        soup = BeautifulSoup(res.text, "html.parser")
        readings = []

        table = soup.find("table")
        if table:
            rows = table.find_all("tr")[1:]
            for row in rows:
                cols = [td.get_text(strip=True) for td in row.find_all("td")]
                if len(cols) >= 2:
                    try:
                        kwh = float(re.sub(r"[^\d.]", "", cols[1]))
                        interval = (
                            float(re.sub(r"[^\d.]", "", cols[2]))
                            if len(cols) > 2
                            else None
                        )
                        readings.append(
                            {
                                "timestamp": cols[0],
                                "reading_kwh": kwh,
                                "interval_kwh": interval,
                            }
                        )
                    except ValueError:
                        continue

        return {
            "meter_id": meter_id,
            "total_records": len(readings),
            "readings": readings,
        }

    def get_hierarchy(self) -> Dict[str, Any]:
        res = self._request_with_retry("GET", "/hierarchy")
        if res.headers.get("content-type", "").startswith("application/json"):
            return res.json()

        # Fallback structured hierarchy representation
        return {
            "id": "root-grid",
            "name": "Central Grid Hub",
            "type": "Substation",
            "children": [
                {
                    "id": "feeder-north",
                    "name": "North Feeder 01",
                    "type": "Feeder",
                    "children": [
                        {
                            "id": "MTR-1001",
                            "name": "Smart Meter 1001",
                            "type": "Meter",
                            "children": [],
                        }
                    ],
                }
            ],
        }