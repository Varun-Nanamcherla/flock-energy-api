import json
from contextlib import asynccontextmanager
from typing import List
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from app.client import UrjaPortalClient
from app.config import settings
from app.models import (
    AuthStatus,
    HierarchyNode,
    MeterConsumptionResponse,
    MeterDetail,
    MeterSummary,
)

# Persistent adapter instance
portal_client = UrjaPortalClient(
    base_url=settings.urja_base_url,
    username=settings.urja_username,
    password=settings.urja_password,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Perform early login attempt on startup
    try:
        portal_client.login()
    except Exception as e:
        print(f"Initial login deferred: {e}")
    yield


app = FastAPI(
    title="Flock Energy - Urja Meter Ops API",
    version="1.0.0",
    description="Clean, normalized REST API wrapper around the legacy Urja Meter Ops portal.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post(
    "/api/v1/auth/login",
    response_model=AuthStatus,
    tags=["Authentication"],
    summary="Authenticate legacy session",
)
def manual_login():
    """Forces session re-authentication against the legacy Urja portal."""
    success = portal_client.login()
    if not success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not authenticate with Urja portal credentials.",
        )
    return AuthStatus(authenticated=True, message="Authenticated successfully")


@app.get(
    "/api/v1/meters",
    response_model=List[MeterSummary],
    tags=["Meters"],
    summary="List all smart meters",
)
def list_meters():
    """Fetches and normalizes the full list of smart meters."""
    try:
        return portal_client.get_meters()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@app.get(
    "/api/v1/meters/{meter_id}",
    response_model=MeterDetail,
    tags=["Meters"],
    summary="Get single meter details",
)
def get_meter(meter_id: str):
    """Retrieves normalized telemetry and metadata for a specific meter."""
    try:
        return portal_client.get_meter_details(meter_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meter '{meter_id}' not found.",
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@app.get(
    "/api/v1/meters/{meter_id}/consumption",
    response_model=MeterConsumptionResponse,
    tags=["Consumption"],
    summary="Get meter consumption timeseries",
)
def get_consumption(meter_id: str):
    """Parses consumption timeseries history for a specific meter."""
    try:
        return portal_client.get_meter_consumption(meter_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@app.get(
    "/api/v1/hierarchy",
    response_model=HierarchyNode,
    tags=["Topology"],
    summary="Get network tree hierarchy",
)
def get_hierarchy():
    """Fetches grid network distribution hierarchy."""
    try:
        return portal_client.get_hierarchy()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


# Helper script command to dump openapi.json directly
def export_openapi():
    with open("openapi.json", "w") as f:
        json.dump(app.openapi(), f, indent=2)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)