from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class MeterSummary(BaseModel):
    meter_id: str = Field(..., description="Unique meter identifier")
    serial_number: str = Field(..., description="Hardware serial number")
    status: str = Field(..., description="Active, Inactive, Maintenance, etc.")
    model: Optional[str] = Field(None, description="Hardware model name")
    location: Optional[str] = Field(None, description="Assigned site or zone")


class MeterDetail(MeterSummary):
    firmware_version: Optional[str] = None
    installation_date: Optional[str] = None
    last_communication: Optional[str] = None
    voltage_l1: Optional[float] = None
    current_l1: Optional[float] = None
    power_factor: Optional[float] = None


class ConsumptionReading(BaseModel):
    timestamp: str = Field(..., description="Timestamp of the reading")
    reading_kwh: float = Field(..., description="Cumulative energy reading in kWh")
    interval_kwh: Optional[float] = Field(
        None, description="Energy consumed during interval"
    )


class MeterConsumptionResponse(BaseModel):
    meter_id: str
    total_records: int
    readings: List[ConsumptionReading]


class HierarchyNode(BaseModel):
    id: str
    name: str
    type: str  # Region, Substation, Feeder, Meter
    children: List["HierarchyNode"] = []


HierarchyNode.model_rebuild()


class AuthStatus(BaseModel):
    authenticated: bool
    message: str