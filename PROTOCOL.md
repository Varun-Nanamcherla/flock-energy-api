# PROTOCOL.md — Urja Meter Ops Reverse Engineering Findings

## 1. Authentication Workflow
- **Target URL:** `https://urja-ops.flockenergy.tech/login`
- **Method:** `POST`
- **Payload:** Form URL-encoded or JSON (`username`, `password`, optional `csrf_token`).
- **Session Mechanism:** 
  - On 200/302, legacy server sets `Set-Cookie: session_id=...; Path=/; HttpOnly`.
  - Session lifetime expires after inactivity or explicitly upon 401 response.

## 2. Endpoints Discovered
| Endpoint | Method | Response Type | Notes |
|---|---|---|---|
| `/login` | GET/POST | HTML / 302 | Sets HTTP-only session cookie |
| `/meters` | GET | HTML Table / JSON | Lists meter ID, serial, status, location |
| `/meters/{id}` | GET | HTML Details | Telemetry values (L1 voltage, power factor) |
| `/meters/{id}/consumption` | GET | HTML Table | Historical timestamped kWh consumption |
| `/hierarchy` | GET | HTML / JSON | Parent-child substation/feeder relationships |

## 3. Data Inconsistencies & Anomaly Handling
- **Numeric Formatting:** Values contain unit suffixes (e.g., `"230.4 V"`, `"12.1 kWh"`). The parser strips non-numeric characters using regex (`[-+]?\d*\.\d+|\d+`) and casts to `float`.
- **Session Expiration:** When cookies expire, the legacy site silently returns a redirect (302) to `/login`. Handled via automatic retry re-authentication in `UrjaPortalClient._request_with_retry`.