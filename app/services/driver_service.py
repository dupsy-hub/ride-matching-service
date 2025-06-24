from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import Optional, List, Dict, Any
import logging
from uuid import UUID

from ..models.driver import DriverLocation
from ..schemas.driver import DriverLocationUpdateRequest, DriverAvailabilityUpdateRequest
from ..utils.redis_client import redis_client

logger = logging.getLogger(__name__)


class DriverService:
    
    async def update_driver_location(
        self, 
        driver_id: UUID, 
        location_data: DriverLocationUpdateRequest,
        db: AsyncSession
    ) -> DriverLocation:
        """Update driver location and availability"""
        try:
            # Update database
            stmt = select(DriverLocation).where(DriverLocation.driver_id == driver_id)
            result = await db.execute(stmt)
            driver_location = result.scalar_one_or_none()
            
            if driver_location:
                # Update existing record
                driver_location.city = location_data.city
                driver_location.area = location_data.area
                driver_location.is_available = location_data.is_available
            else:
                # Create new record
                driver_location = DriverLocation(
                    driver_id=driver_id,
                    city=location_data.city,
                    area=location_data.area,
                    is_available=location_data.is_available
                )
                db.add(driver_location)
            
            await db.commit()
            await db.refresh(driver_location)
            
            # Update Redis cache
            redis_data = {
                "city": location_data.city,
                "area": location_data.area,
                "is_available": location_data.is_available,
                "last_updated": driver_location.last_updated.isoformat()
            }
            await redis_client.set_driver_status(str(driver_id), redis_data)
            
            logger.info(f"Updated location for driver {driver_id}")
            return driver_location
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to update driver location: {e}")
            raise

    async def update_driver_availability(
        self, 
        driver_id: UUID, 
        availability_data: DriverAvailabilityUpdateRequest,
        db: AsyncSession
    ) -> bool:
        """Update only driver availability status"""
        try:
            # Update database
            stmt = (
                update(DriverLocation)
                .where(DriverLocation.driver_id == driver_id)
                .values(is_available=availability_data.is_available)
            )
            result = await db.execute(stmt)
            
            if result.rowcount == 0:
                logger.warning(f"Driver {driver_id} not found for availability update")
                return False
                
            await db.commit()
            
            # Update Redis cache
            cached_data = await redis_client.get_driver_status(str(driver_id))
            if cached_data:
                cached_data["is_available"] = availability_data.is_available
                await redis_client.set_driver_status(str(driver_id), cached_data)
            
            logger.info(f"Updated availability for driver {driver_id}: {availability_data.is_available}")
            return True
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to update driver availability: {e}")
            raise

    async def get_driver_location(self, driver_id: UUID, db: AsyncSession) -> Optional[DriverLocation]:
        """Get driver location from database"""
        try:
            stmt = select(DriverLocation).where(DriverLocation.driver_id == driver_id)
            result = await db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get driver location: {e}")
            raise

    async def get_available_drivers_in_area(self, city: str, area: str) -> List[Dict[str, Any]]:
        """Get available drivers in specific area from Redis (fast lookup)"""
        try:
            drivers = await redis_client.get_available_drivers_in_area(city, area)
            logger.info(f"Found {len(drivers)} available drivers in {city}, {area}")
            return drivers
        except Exception as e:
            logger.error(f"Failed to get available drivers: {e}")
            return []

    async def get_driver_availability_status(self, driver_id: UUID) -> Dict[str, Any]:
        """Get driver availability status with location info"""
        try:
            # Try Redis first (faster)
            cached_data = await redis_client.get_driver_status(str(driver_id))
            if cached_data:
                return {
                    "is_available": cached_data.get("is_available", False),
                    "current_location": {
                        "city": cached_data.get("city"),
                        "area": cached_data.get("area")
                    },
                    "active_ride_id": None  # TODO: Implement ride tracking
                }
            
            return {
                "is_available": False,
                "current_location": {},
                "active_ride_id": None
            }
            
        except Exception as e:
            logger.error(f"Failed to get driver availability: {e}")
            return {
                "is_available": False,
                "current_location": {},
                "active_ride_id": None
            }