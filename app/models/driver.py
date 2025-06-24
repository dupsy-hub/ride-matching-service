from sqlalchemy import Column, String, Boolean, TIMESTAMP, UUID
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from ..database import Base


class DriverLocation(Base):
    __tablename__ = "driver_locations"

    driver_id = Column(PG_UUID(as_uuid=True), primary_key=True)
    
    # Simplified location (no lat/lng - just city and area)
    city = Column(String(100), nullable=False)
    area = Column(String(100), nullable=False)
    
    # Availability
    is_available = Column(Boolean, default=True, nullable=False)
    
    # Timestamps
    last_updated = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<DriverLocation(driver_id={self.driver_id}, city={self.city}, area={self.area}, available={self.is_available})>"