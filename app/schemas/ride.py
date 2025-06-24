from pydantic import BaseModel, Field, UUID4
from typing import Optional
from datetime import datetime
from decimal import Decimal
from ..models.ride import RideStatus, RideType


# Request schemas
class RideCreateRequest(BaseModel):
    pickup_address: str = Field(..., min_length=5, max_length=500)
    destination_address: str = Field(..., min_length=5, max_length=500)
    ride_type: RideType = RideType.STANDARD
    special_requests: Optional[str] = Field(None, max_length=1000)


class RideStatusUpdateRequest(BaseModel):
    status: RideStatus
    estimated_arrival: Optional[int] = Field(None, description="Minutes until arrival")


class RideCancelRequest(BaseModel):
    reason: str = Field(..., min_length=5, max_length=500)
    cancelled_by: str = Field(..., pattern="^(rider|driver)$")  # Fixed: pattern instead of regex


# Response schemas
class RideResponse(BaseModel):
    id: UUID4
    rider_id: UUID4
    driver_id: Optional[UUID4] = None
    pickup_address: str
    destination_address: str
    estimated_fare: Optional[Decimal] = None
    actual_fare: Optional[Decimal] = None
    status: RideStatus
    ride_type: RideType
    special_requests: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    accepted_at: Optional[datetime] = None
    pickup_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RideCreateResponse(BaseModel):
    ride: RideResponse
    message: str = "Ride requested successfully. Finding nearby drivers..."


class RideListResponse(BaseModel):
    rides: list[RideResponse]
    total: int
    limit: int
    offset: int


# Driver response info (when ride is matched)
class DriverInfo(BaseModel):
    id: UUID4
    first_name: str
    phone: str
    vehicle: dict
    rating: float
    current_location: dict


class RideWithDriverResponse(BaseModel):
    ride: RideResponse
    driver: Optional[DriverInfo] = None