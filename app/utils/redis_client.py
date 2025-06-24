import redis.asyncio as redis
import json
import logging
from typing import Optional, Any, Dict
from ..config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    def __init__(self):
        self.redis: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None

    async def connect(self):
        """Connect to Redis"""
        try:
            self.redis = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                retry_on_timeout=True,
                socket_keepalive=True,
                socket_keepalive_options={},
            )
            # Test connection
            await self.redis.ping()
            logger.info("Connected to Redis successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    async def disconnect(self):
        """Disconnect from Redis"""
        if self.redis:
            await self.redis.close()
            logger.info("Disconnected from Redis")

    async def set_driver_status(self, driver_id: str, location_data: Dict[str, Any], ttl: int = 3600):
        """Set driver location and availability status"""
        try:
            key = f"driver:status:{driver_id}"
            await self.redis.setex(key, ttl, json.dumps(location_data))
        except Exception as e:
            logger.error(f"Failed to set driver status: {e}")
            raise

    async def get_driver_status(self, driver_id: str) -> Optional[Dict[str, Any]]:
        """Get driver location and availability status"""
        try:
            key = f"driver:status:{driver_id}"
            data = await self.redis.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"Failed to get driver status: {e}")
            return None

    async def get_available_drivers_in_area(self, city: str, area: str) -> list[Dict[str, Any]]:
        """Get all available drivers in a specific area"""
        try:
            pattern = "driver:status:*"
            keys = await self.redis.keys(pattern)
            available_drivers = []
            
            for key in keys:
                data = await self.redis.get(key)
                if data:
                    driver_data = json.loads(data)
                    if (driver_data.get("is_available") and 
                        driver_data.get("city") == city and 
                        driver_data.get("area") == area):
                        driver_id = key.split(":")[-1]
                        driver_data["driver_id"] = driver_id
                        available_drivers.append(driver_data)
            
            return available_drivers
        except Exception as e:
            logger.error(f"Failed to get available drivers: {e}")
            return []

    async def publish_event(self, channel: str, event_data: Dict[str, Any]):
        """Publish event to Redis channel"""
        try:
            await self.redis.publish(channel, json.dumps(event_data))
            logger.info(f"Published event to {channel}: {event_data}")
        except Exception as e:
            logger.error(f"Failed to publish event: {e}")
            raise

    async def subscribe_to_events(self, channels: list[str]):
        """Subscribe to Redis channels"""
        try:
            self.pubsub = self.redis.pubsub()
            await self.pubsub.subscribe(*channels)
            logger.info(f"Subscribed to channels: {channels}")
            return self.pubsub
        except Exception as e:
            logger.error(f"Failed to subscribe to events: {e}")
            raise

    async def health_check(self) -> bool:
        """Check Redis health"""
        try:
            await self.redis.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False


# Global Redis client instance
redis_client = RedisClient()