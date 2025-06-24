from pydantic import BaseModel, Field, UUID4
from datetime import datetime


# Request schemas
class DriverLocationUpdateRequest(BaseModel):
    city: str = Field(..., min_length=2, max_length=100)
    area: str = Field(..., min_length=2, max_length=100)
    is_available: bool = True


class DriverAvailabilityUpdateRequest(BaseModel):
    is_available: bool


# Response schemas
class DriverLocationResponse(BaseModel):
    driver_id: UUID4
    city: str
    area: str
    is_available: bool
    last_updated: datetime

    class Config:
        from_attributes = True


class DriverAvailabilityResponse(BaseModel):
    is_available: bool
    current_location: dict
    active_ride_id: UUID4 = None


class NearbyDriversResponse(BaseModel):
    drivers: list[dict]
    count: int
    search_area: str