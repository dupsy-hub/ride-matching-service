from fastapi import APIRouter, Depends, HTTPException, status, Header, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import logging
from uuid import UUID

from ..database import get_db
from ..schemas.ride import (
    RideCreateRequest,
    RideStatusUpdateRequest,
    RideCancelRequest,
    RideCreateResponse,
    RideResponse,
    RideWithDriverResponse,
    RideListResponse
)
from ..services.ride_service import RideService
from ..services.matching_service import MatchingService
from ..services.event_service import EventService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rides", tags=["rides"])

# Service instances
ride_service = RideService()
matching_service = MatchingService()
event_service = EventService()


# Mock JWT validation (replace with actual implementation)
async def get_current_user_id(authorization: Optional[str] = Header(None)) -> UUID:
    """Extract user ID from JWT token"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header"
        )
    
    # Mock user ID for now
    return UUID("87654321-4321-8765-2109-876543210987")


async def get_current_driver_id(authorization: Optional[str] = Header(None)) -> UUID:
    """Extract driver ID from JWT token"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header"
        )
    
    # Mock driver ID for now
    return UUID("12345678-1234-5678-9012-123456789012")


@router.post("/request", response_model=RideCreateResponse, status_code=status.HTTP_201_CREATED)
async def request_ride(
    ride_data: RideCreateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    rider_id: UUID = Depends(get_current_user_id)
):
    """Request a new ride"""
    try:
        # Create the ride
        ride = await ride_service.create_ride(rider_id, ride_data, db)
        
        # Start matching process in background
        background_tasks.add_task(matching_service.attempt_ride_match, ride.id, db)
        
        # Publish ride requested event
        await event_service.notify_ride_requested({
            "ride_id": str(ride.id),
            "rider_id": str(rider_id),
            "pickup_address": ride.pickup_address,
            "destination_address": ride.destination_address,
            "estimated_fare": float(ride.estimated_fare),
            "ride_type": ride.ride_type
        })
        
        return RideCreateResponse(
            ride=RideResponse.from_orm(ride),
            message="Ride requested successfully. Finding nearby drivers..."
        )
        
    except Exception as e:
        logger.error(f"Failed to request ride: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create ride request"
        )


@router.get("/{ride_id}", response_model=RideWithDriverResponse)
async def get_ride(
    ride_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
):
    """Get ride details"""
    try:
        ride = await ride_service.get_ride_by_id(ride_id, db)
        
        if not ride:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ride not found"
            )
        
        # Check if user has access to this ride
        if ride.rider_id != user_id and ride.driver_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # TODO: Fetch driver info from User Service if ride has driver
        driver_info = None
        if ride.driver_id:
            # Mock driver info for now
            driver_info = {
                "id": ride.driver_id,
                "first_name": "John",
                "phone": "+1234567890",
                "vehicle": {
                    "make": "Toyota",
                    "model": "Camry",
                    "color": "Blue",
                    "license_plate": "ABC-123"
                },
                "rating": 4.8,
                "current_location": {
                    "latitude": 6.5244,
                    "longitude": 3.3792
                }
            }
        
        return RideWithDriverResponse(
            ride=RideResponse.from_orm(ride),
            driver=driver_info
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get ride: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve ride"
        )


@router.put("/{ride_id}/status", response_model=dict)
async def update_ride_status(
    ride_id: UUID,
    status_data: RideStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
    driver_id: UUID = Depends(get_current_driver_id)
):
    """Update ride status (driver only)"""
    try:
        # Verify driver is assigned to this ride
        ride = await ride_service.get_ride_by_id(ride_id, db)
        
        if not ride:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ride not found"
            )
        
        if ride.driver_id != driver_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only assigned driver can update ride status"
            )
        
        # Update status
        success = await ride_service.update_ride_status(
            ride_id, status_data, db=db
        )
        
        if success:
            # Publish status update event
            await event_service.publish_ride_event(
                "ride_status_updated",
                {
                    "ride_id": str(ride_id),
                    "driver_id": str(driver_id),
                    "new_status": status_data.status,
                    "rider_id": str(ride.rider_id)
                }
            )
            
            return {"message": f"Ride status updated to {status_data.status}"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid status transition"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update ride status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update ride status"
        )


@router.post("/{ride_id}/cancel", response_model=dict)
async def cancel_ride(
    ride_id: UUID,
    cancel_data: RideCancelRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
):
    """Cancel a ride"""
    try:
        ride = await ride_service.get_ride_by_id(ride_id, db)
        
        if not ride:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ride not found"
            )
        
        # Check if user has permission to cancel
        if ride.rider_id != user_id and ride.driver_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        success = await ride_service.cancel_ride(ride_id, cancel_data, db)
        
        if success:
            # Publish cancellation event
            await event_service.notify_ride_cancelled({
                "ride_id": str(ride_id),
                "rider_id": str(ride.rider_id),
                "driver_id": str(ride.driver_id) if ride.driver_id else None,
                "reason": cancel_data.reason,
                "cancelled_by": cancel_data.cancelled_by
            })
            
            return {"message": "Ride cancelled successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot cancel ride in current status"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel ride: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel ride"
        )


@router.get("/history", response_model=RideListResponse)
async def get_ride_history(
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    rider_id: UUID = Depends(get_current_user_id)
):
    """Get ride history for current user"""
    try:
        rides, total = await ride_service.get_rider_rides(
            rider_id, limit, offset, db
        )
        
        return RideListResponse(
            rides=[RideResponse.from_orm(ride) for ride in rides],
            total=total,
            limit=limit,
            offset=offset
        )
        
    except Exception as e:
        logger.error(f"Failed to get ride history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve ride history"
        )