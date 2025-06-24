from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import logging
from uuid import UUID

from ..database import get_db
from ..schemas.driver import (
    DriverLocationUpdateRequest,
    DriverAvailabilityUpdateRequest,
    DriverLocationResponse,
    DriverAvailabilityResponse,
    NearbyDriversResponse
)
from ..services.driver_service import DriverService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rides", tags=["drivers"])
driver_service = DriverService()


# Mock JWT validation (replace with actual implementation)
async def get_current_driver_id(authorization: Optional[str] = Header(None)) -> UUID:
    """Extract driver ID from JWT token"""
    # TODO: Implement actual JWT validation
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header"
        )
    
    # Mock driver ID for now
    return UUID("12345678-1234-5678-9012-123456789012")


@router.put("/driver/location", response_model=DriverLocationResponse)
async def update_driver_location(
    location_data: DriverLocationUpdateRequest,
    db: AsyncSession = Depends(get_db),
    driver_id: UUID = Depends(get_current_driver_id)
):
    """Update driver location and availability status"""
    try:
        driver_location = await driver_service.update_driver_location(
            driver_id, location_data, db
        )
        
        return DriverLocationResponse.from_orm(driver_location)
        
    except Exception as e:
        logger.error(f"Failed to update driver location: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update location"
        )


@router.get("/driver/availability", response_model=DriverAvailabilityResponse)
async def get_driver_availability(
    driver_id: UUID = Depends(get_current_driver_id)
):
    """Get driver availability status"""
    try:
        availability_data = await driver_service.get_driver_availability_status(driver_id)
        
        return DriverAvailabilityResponse(**availability_data)
        
    except Exception as e:
        logger.error(f"Failed to get driver availability: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get availability status"
        )


@router.put("/driver/availability", response_model=dict)
async def update_driver_availability(
    availability_data: DriverAvailabilityUpdateRequest,
    db: AsyncSession = Depends(get_db),
    driver_id: UUID = Depends(get_current_driver_id)
):
    """Update driver availability status only"""
    try:
        success = await driver_service.update_driver_availability(
            driver_id, availability_data, db
        )
        
        if success:
            return {"message": "Availability updated successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Driver not found"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update driver availability: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update availability"
        )


@router.get("/nearby-drivers", response_model=NearbyDriversResponse)
async def get_nearby_drivers(
    city: str,
    area: str
):
    """Get available drivers in specific area (for testing/admin purposes)"""
    try:
        drivers = await driver_service.get_available_drivers_in_area(city, area)
        
        return NearbyDriversResponse(
            drivers=drivers,
            count=len(drivers),
            search_area=f"{area}, {city}"
        )
        
    except Exception as e:
        logger.error(f"Failed to get nearby drivers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get nearby drivers"
        )