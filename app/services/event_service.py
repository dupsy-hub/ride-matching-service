import logging
from typing import Dict, Any
from datetime import datetime
import uuid

from ..utils.redis_client import redis_client

logger = logging.getLogger(__name__)


class EventService:
    """Handle event publishing and subscribing via Redis"""
    
    # Event channels
    RIDE_EVENTS_CHANNEL = "ride-events"
    PAYMENT_EVENTS_CHANNEL = "payment-events"
    DRIVER_NOTIFICATIONS_CHANNEL = "driver-notifications"
    USER_NOTIFICATIONS_CHANNEL = "user-notifications"

    async def publish_ride_event(self, event_type: str, event_data: Dict[str, Any]):
        """Publish ride-related events"""
        try:
            event = {
                "event_id": str(uuid.uuid4()),
                "event_type": event_type,
                "timestamp": datetime.utcnow().isoformat(),
                "service": "ride-matching",
                "data": event_data
            }
            
            await redis_client.publish_event(self.RIDE_EVENTS_CHANNEL, event)
            logger.info(f"Published ride event: {event_type}")
            
        except Exception as e:
            logger.error(f"Failed to publish ride event: {e}")
            raise

    async def publish_payment_event(self, event_type: str, event_data: Dict[str, Any]):
        """Publish payment-related events"""
        try:
            event = {
                "event_id": str(uuid.uuid4()),
                "event_type": event_type,
                "timestamp": datetime.utcnow().isoformat(),
                "service": "ride-matching",
                "data": event_data
            }
            
            await redis_client.publish_event(self.PAYMENT_EVENTS_CHANNEL, event)
            logger.info(f"Published payment event: {event_type}")
            
        except Exception as e:
            logger.error(f"Failed to publish payment event: {e}")
            raise

    async def publish_driver_notification(self, driver_id: str, notification_data: Dict[str, Any]):
        """Publish notification to specific driver"""
        try:
            notification = {
                "notification_id": str(uuid.uuid4()),
                "recipient_type": "driver",
                "recipient_id": driver_id,
                "timestamp": datetime.utcnow().isoformat(),
                "data": notification_data
            }
            
            await redis_client.publish_event(self.DRIVER_NOTIFICATIONS_CHANNEL, notification)
            logger.info(f"Published driver notification to {driver_id}")
            
        except Exception as e:
            logger.error(f"Failed to publish driver notification: {e}")
            raise

    async def publish_user_notification(self, user_id: str, notification_data: Dict[str, Any]):
        """Publish notification to specific user"""
        try:
            notification = {
                "notification_id": str(uuid.uuid4()),
                "recipient_type": "user",
                "recipient_id": user_id,
                "timestamp": datetime.utcnow().isoformat(),
                "data": notification_data
            }
            
            await redis_client.publish_event(self.USER_NOTIFICATIONS_CHANNEL, notification)
            logger.info(f"Published user notification to {user_id}")
            
        except Exception as e:
            logger.error(f"Failed to publish user notification: {e}")
            raise

    # Specific event publishers for common scenarios

    async def notify_ride_requested(self, ride_data: Dict[str, Any]):
        """Notify when new ride is requested"""
        await self.publish_ride_event("ride_requested", ride_data)
        
        # Also notify user
        await self.publish_user_notification(
            ride_data["rider_id"],
            {
                "type": "ride_requested",
                "message": "Your ride has been requested. Finding nearby drivers...",
                "ride_id": ride_data["ride_id"]
            }
        )

    async def notify_ride_matched(self, ride_data: Dict[str, Any]):
        """Notify when ride is matched with driver"""
        await self.publish_ride_event("ride_matched", ride_data)
        
        # Notify rider
        await self.publish_user_notification(
            ride_data["rider_id"],
            {
                "type": "ride_matched",
                "message": f"Driver found! They're on their way to {ride_data['pickup_address']}",
                "ride_id": ride_data["ride_id"],
                "driver_id": ride_data["driver_id"]
            }
        )

    async def notify_ride_accepted(self, ride_data: Dict[str, Any]):
        """Notify when driver accepts the ride"""
        await self.publish_ride_event("ride_accepted", ride_data)
        
        # Notify rider
        await self.publish_user_notification(
            ride_data["rider_id"],
            {
                "type": "ride_accepted",
                "message": "Driver accepted your ride! They're on their way.",
                "ride_id": ride_data["ride_id"],
                "driver_id": ride_data["driver_id"]
            }
        )

    async def notify_ride_cancelled(self, ride_data: Dict[str, Any]):
        """Notify when ride is cancelled"""
        await self.publish_ride_event("ride_cancelled", ride_data)
        
        # Notify both rider and driver if assigned
        await self.publish_user_notification(
            ride_data["rider_id"],
            {
                "type": "ride_cancelled",
                "message": f"Your ride has been cancelled. {ride_data.get('reason', '')}",
                "ride_id": ride_data["ride_id"]
            }
        )
        
        if ride_data.get("driver_id"):
            await self.publish_driver_notification(
                ride_data["driver_id"],
                {
                    "type": "ride_cancelled",
                    "message": "The ride has been cancelled.",
                    "ride_id": ride_data["ride_id"]
                }
            )

    async def notify_ride_completed(self, ride_data: Dict[str, Any]):
        """Notify when ride is completed"""
        await self.publish_ride_event("ride_completed", ride_data)
        
        # Trigger payment processing
        await self.publish_payment_event("process_payment", {
            "ride_id": ride_data["ride_id"],
            "rider_id": ride_data["rider_id"],
            "driver_id": ride_data["driver_id"],
            "amount": ride_data["fare"],
            "payment_method_id": ride_data.get("payment_method_id")
        })
        
        # Notify rider
        await self.publish_user_notification(
            ride_data["rider_id"],
            {
                "type": "ride_completed",
                "message": f"You've arrived! Your fare was ${ride_data['fare']}",
                "ride_id": ride_data["ride_id"]
            }
        )
        
        # Notify driver
        await self.publish_driver_notification(
            ride_data["driver_id"],
            {
                "type": "ride_completed",
                "message": f"Ride completed! You earned ${ride_data.get('driver_earnings', 0)}",
                "ride_id": ride_data["ride_id"]
            }
        )