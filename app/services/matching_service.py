from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List, Dict, Any
import logging
import asyncio
from uuid import UUID

from .driver_service import DriverService
from .ride_service import RideService
from .event_service import EventService
from ..models.ride import RideStatus
from ..schemas.ride import RideStatusUpdateRequest
from ..config import settings

logger = logging.getLogger(__name__)


class MatchingService:
    def __init__(self):
        self.driver_service = DriverService()
        self.ride_service = RideService()
        self.event_service = EventService()

    def extract_location_from_address(self, address: str) -> Dict[str, str]:
        """Extract city and area from address (simplified)"""
        try:
            # Simple parsing - in reality you'd use geocoding
            parts = address.split(",")
            if len(parts) >= 2:
                area = parts[0].strip()
                city = parts[-1].strip()
            else:
                # Default fallback
                area = "Downtown"
                city = "Lagos"
            
            return {"city": city, "area": area}
        except Exception as e:
            logger.error(f"Error parsing address: {e}")
            return {"city": "Lagos", "area": "Downtown"}

    async def find_available_drivers(self, pickup_address: str) -> List[Dict[str, Any]]:
        """Find available drivers near pickup location"""
        try:
            location = self.extract_location_from_address(pickup_address)
            
            # Get drivers in same area first
            drivers = await self.driver_service.get_available_drivers_in_area(
                location["city"], 
                location["area"]
            )
            
            # If no drivers in exact area, expand search to whole city
            if not drivers and location["area"] != "Downtown":
                logger.info(f"No drivers in {location['area']}, expanding to {location['city']}")
                # Get all available drivers in the city
                all_city_drivers = await self.driver_service.get_available_drivers_in_area(
                    location["city"], 
                    ""  # Empty area to get all in city
                )
                drivers = all_city_drivers
            
            # Limit to max drivers to notify
            drivers = drivers[:settings.max_drivers_to_notify]
            
            logger.info(f"Found {len(drivers)} available drivers for matching")
            return drivers
            
        except Exception as e:
            logger.error(f"Error finding available drivers: {e}")
            return []

    async def attempt_ride_match(self, ride_id: UUID, db: AsyncSession) -> bool:
        """Attempt to match a ride with available drivers"""
        try:
            # Get ride details
            ride = await self.ride_service.get_ride_by_id(ride_id, db)
            if not ride or ride.status != RideStatus.REQUESTED:
                logger.warning(f"Ride {ride_id} not available for matching")
                return False

            # Find available drivers
            drivers = await self.find_available_drivers(ride.pickup_address)
            
            if not drivers:
                logger.info(f"No available drivers found for ride {ride_id}")
                # Publish event that no drivers found
                await self.event_service.publish_ride_event(
                    "ride_no_drivers_found",
                    {
                        "ride_id": str(ride_id),
                        "rider_id": str(ride.rider_id),
                        "pickup_address": ride.pickup_address,
                        "timestamp": ride.created_at.isoformat()
                    }
                )
                return False

            # For now, just take the first available driver (simple matching)
            selected_driver = drivers[0]
            driver_id = UUID(selected_driver["driver_id"])
            
            # Update ride status to matched
            success = await self.ride_service.update_ride_status(
                ride_id,
                RideStatusUpdateRequest(status=RideStatus.MATCHED),
                driver_id=driver_id,
                db=db
            )
            
            if success:
                # Mark driver as unavailable
                await self.driver_service.update_driver_availability(
                    driver_id,
                    {"is_available": False},
                    db
                )
                
                # Publish ride matched event
                await self.event_service.publish_ride_event(
                    "ride_matched",
                    {
                        "ride_id": str(ride_id),
                        "rider_id": str(ride.rider_id),
                        "driver_id": str(driver_id),
                        "pickup_address": ride.pickup_address,
                        "destination_address": ride.destination_address,
                        "estimated_fare": float(ride.estimated_fare),
                        "timestamp": ride.created_at.isoformat()
                    }
                )
                
                # Notify driver about ride request
                await self.event_service.publish_driver_notification(
                    str(driver_id),
                    {
                        "type": "ride_request",
                        "ride_id": str(ride_id),
                        "pickup_address": ride.pickup_address,
                        "destination_address": ride.destination_address,
                        "estimated_fare": float(ride.estimated_fare),
                        "special_requests": ride.special_requests,
                        "timeout": settings.driver_response_timeout
                    }
                )
                
                logger.info(f"Successfully matched ride {ride_id} with driver {driver_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error matching ride {ride_id}: {e}")
            return False

    async def process_ride_queue(self, db: AsyncSession):
        """Process pending ride requests (background task)"""
        try:
            # This would typically be called by a background worker
            # For now, it's a simple implementation
            
            # Get all requested rides
            from sqlalchemy import select
            from ..models.ride import Ride
            
            stmt = select(Ride).where(Ride.status == RideStatus.REQUESTED)
            result = await db.execute(stmt)
            pending_rides = result.scalars().all()
            
            logger.info(f"Processing {len(pending_rides)} pending rides")
            
            for ride in pending_rides:
                await self.attempt_ride_match(ride.id, db)
                # Small delay to avoid overwhelming the system
                await asyncio.sleep(0.1)
                
        except Exception as e:
            logger.error(f"Error processing ride queue: {e}")

    async def handle_driver_response(
        self, 
        ride_id: UUID, 
        driver_id: UUID, 
        accepted: bool,
        db: AsyncSession
    ) -> bool:
        """Handle driver's response to ride request"""
        try:
            if accepted:
                # Update ride status to accepted
                success = await self.ride_service.update_ride_status(
                    ride_id,
                    RideStatusUpdateRequest(status=RideStatus.ACCEPTED),
                    db=db
                )
                
                if success:
                    # Publish acceptance event
                    await self.event_service.publish_ride_event(
                        "ride_accepted",
                        {
                            "ride_id": str(ride_id),
                            "driver_id": str(driver_id),
                            "timestamp": asyncio.get_event_loop().time()
                        }
                    )
                    logger.info(f"Driver {driver_id} accepted ride {ride_id}")
                
                return success
            else:
                # Driver declined - find another driver
                logger.info(f"Driver {driver_id} declined ride {ride_id}")
                
                # Mark driver as available again
                await self.driver_service.update_driver_availability(
                    driver_id,
                    {"is_available": True},
                    db
                )
                
                # Reset ride to requested status for re-matching
                await self.ride_service.update_ride_status(
                    ride_id,
                    RideStatusUpdateRequest(status=RideStatus.REQUESTED),
                    db=db
                )
                
                # Try to match with another driver
                return await self.attempt_ride_match(ride_id, db)
                
        except Exception as e:
            logger.error(f"Error handling driver response: {e}")
            return False