from sqlalchemy import Column, String, DECIMAL, TIMESTAMP, UUID, Text, Enum
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
import uuid
import enum
from ..database import Base


class RideStatus(str, enum.Enum):
    REQUESTED = "requested"
    MATCHED = "matched"
    ACCEPTED = "accepted"
    PICKUP = "pickup"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class RideType(str, enum.Enum):
    STANDARD = "standard"
    PREMIUM = "premium"
    SHARED = "shared"


class Ride(Base):
    __tablename__ = "rides"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rider_id = Column(PG_UUID(as_uuid=True), nullable=False)
    driver_id = Column(PG_UUID(as_uuid=True), nullable=True)
    
    # Location info (simplified - just addresses)
    pickup_address = Column(Text, nullable=False)
    destination_address = Column(Text, nullable=False)
    
    # Fare information
    estimated_fare = Column(DECIMAL(10, 2), nullable=True)
    actual_fare = Column(DECIMAL(10, 2), nullable=True)
    
    # Ride details
    status = Column(Enum(RideStatus), nullable=False, default=RideStatus.REQUESTED)
    ride_type = Column(Enum(RideType), nullable=False, default=RideType.STANDARD)
    special_requests = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    accepted_at = Column(TIMESTAMP(timezone=True), nullable=True)
    pickup_at = Column(TIMESTAMP(timezone=True), nullable=True)
    started_at = Column(TIMESTAMP(timezone=True), nullable=True)
    completed_at = Column(TIMESTAMP(timezone=True), nullable=True)

    def __repr__(self):
        return f"<Ride(id={self.id}, status={self.status}, rider_id={self.rider_id})>"