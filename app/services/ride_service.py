from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc
from typing import Optional, List, Tuple
import logging
from uuid import UUID
from datetime import datetime
from decimal import Decimal

from ..models.ride import Ride, RideStatus
from ..schemas.ride import RideCreateRequest, RideStatusUpdateRequest, RideCancelRequest
from ..config import settings

logger = logging.getLogger(__name__)


class RideService:
    
    def calculate_estimated_fare(self, pickup_address: str, destination_address: str) -> Decimal:
        """Calculate estimated fare (simplified - no actual distance calculation)"""
        try:
            # Simple fare calculation based on address complexity
            # In real implementation, you'd use Google Maps or similar
            base_fare = Decimal(str(settings.base_fare))
            
            # Simple estimate: longer addresses = longer distance
            estimated_km = max(2, len(destination_address) // 20)
            distance_fare = Decimal(str(estimated_km)) * Decimal(str(settings.per_km_rate))
            
            total_fare = base_fare + distance_fare
            return round(total_fare, 2)
            
        except Exception as e:
            logger.error(f"Error calculating fare: {e}")
            return Decimal("10.00")  # Default fare

    async def create_ride(
        self, 
        rider_id: UUID, 
        ride_data: RideCreateRequest,
        db: AsyncSession
    ) -> Ride:
        """Create a new ride request"""
        try:
            # Calculate estimated fare
            estimated_fare = self.calculate_estimated_fare(
                ride_data.pickup_address, 
                ride_data.destination_address
            )
            
            # Create ride
            ride = Ride(
                rider_id=rider_id,
                pickup_address=ride_data.pickup_address,
                destination_address=ride_data.destination_address,
                ride_type=ride_data.ride_type,
                special_requests=ride_data.special_requests,
                estimated_fare=estimated_fare,
                status=RideStatus.REQUESTED
            )
            
            db.add(ride)
            await db.commit()
            await db.refresh(ride)
            
            logger.info(f"Created ride {ride.id} for rider {rider_id}")
            return ride
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to create ride: {e}")
            raise

    async def get_ride_by_id(self, ride_id: UUID, db: AsyncSession) -> Optional[Ride]:
        """Get ride by ID"""
        try:
            stmt = select(Ride).where(Ride.id == ride_id)
            result = await db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get ride {ride_id}: {e}")
            raise

    async def update_ride_status(
        self, 
        ride_id: UUID, 
        status_data: RideStatusUpdateRequest,
        driver_id: Optional[UUID] = None,
        db: AsyncSession = None
    ) -> bool:
        """Update ride status"""
        try:
            # Get current ride
            ride = await self.get_ride_by_id(ride_id, db)
            if not ride:
                logger.warning(f"Ride {ride_id} not found")
                return False
            
            # Validate status transition
            if not self._is_valid_status_transition(ride.status, status_data.status):
                logger.warning(f"Invalid status transition: {ride.status} -> {status_data.status}")
                return False
            
            # Update fields based on status
            update_data = {"status": status_data.status}
            
            if status_data.status == RideStatus.MATCHED and driver_id:
                update_data["driver_id"] = driver_id
            elif status_data.status == RideStatus.ACCEPTED:
                update_data["accepted_at"] = datetime.utcnow()
            elif status_data.status == RideStatus.PICKUP:
                update_data["pickup_at"] = datetime.utcnow()
            elif status_data.status == RideStatus.IN_PROGRESS:
                update_data["started_at"] = datetime.utcnow()
            elif status_data.status == RideStatus.COMPLETED:
                update_data["completed_at"] = datetime.utcnow()
                # Set actual fare (for now, same as estimated)
                update_data["actual_fare"] = ride.estimated_fare
            
            # Execute update
            stmt = (
                update(Ride)
                .where(Ride.id == ride_id)
                .values(**update_data)
            )
            
            await db.execute(stmt)
            await db.commit()
            
            logger.info(f"Updated ride {ride_id} status to {status_data.status}")
            return True
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to update ride status: {e}")
            raise

    async def cancel_ride(
        self, 
        ride_id: UUID, 
        cancel_data: RideCancelRequest,
        db: AsyncSession
    ) -> bool:
        """Cancel a ride"""
        try:
            ride = await self.get_ride_by_id(ride_id, db)
            if not ride:
                return False
            
            # Check if ride can be cancelled
            if ride.status in [RideStatus.COMPLETED, RideStatus.CANCELLED]:
                logger.warning(f"Cannot cancel ride {ride_id} in status {ride.status}")
                return False
            
            # Update to cancelled status
            stmt = (
                update(Ride)
                .where(Ride.id == ride_id)
                .values(status=RideStatus.CANCELLED)
            )
            
            await db.execute(stmt)
            await db.commit()
            
            logger.info(f"Cancelled ride {ride_id}: {cancel_data.reason}")
            return True
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to cancel ride: {e}")
            raise

    async def get_rider_rides(
        self, 
        rider_id: UUID, 
        limit: int = 20, 
        offset: int = 0,
        db: AsyncSession = None
    ) -> Tuple[List[Ride], int]:
        """Get rides for a specific rider with pagination"""
        try:
            # Get rides
            stmt = (
                select(Ride)
                .where(Ride.rider_id == rider_id)
                .order_by(desc(Ride.created_at))
                .limit(limit)
                .offset(offset)
            )
            result = await db.execute(stmt)
            rides = result.scalars().all()
            
            # Get total count
            count_stmt = select(Ride).where(Ride.rider_id == rider_id)
            count_result = await db.execute(count_stmt)
            total = len(count_result.scalars().all())
            
            return list(rides), total
            
        except Exception as e:
            logger.error(f"Failed to get rider rides: {e}")
            raise

    def _is_valid_status_transition(self, current_status: RideStatus, new_status: RideStatus) -> bool:
        """Validate if status transition is allowed"""
        valid_transitions = {
            RideStatus.REQUESTED: [RideStatus.MATCHED, RideStatus.CANCELLED],
            RideStatus.MATCHED: [RideStatus.ACCEPTED, RideStatus.CANCELLED],
            RideStatus.ACCEPTED: [RideStatus.PICKUP, RideStatus.CANCELLED],
            RideStatus.PICKUP: [RideStatus.IN_PROGRESS, RideStatus.CANCELLED],
            RideStatus.IN_PROGRESS: [RideStatus.COMPLETED, RideStatus.CANCELLED],
            RideStatus.COMPLETED: [],  # Terminal state
            RideStatus.CANCELLED: []   # Terminal state
        }
        
        return new_status in valid_transitions.get(current_status, [])