from fastapi import APIRouter, status
from pydantic import BaseModel
from datetime import datetime
import logging

from ..database import check_database_health
from ..utils.redis_client import redis_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rides", tags=["health"])


class HealthResponse(BaseModel):
    status: str
    service: str
    timestamp: datetime
    dependencies: dict


@router.get("/health", response_model=HealthResponse, status_code=status.HTTP_200_OK)
async def health_check():
    """Health check endpoint for Kubernetes probes"""
    try:
        # Check database
        db_healthy = await check_database_health()
        
        # Check Redis
        redis_healthy = await redis_client.health_check()
        
        # Determine overall status
        overall_status = "healthy" if db_healthy and redis_healthy else "unhealthy"
        
        response = HealthResponse(
            status=overall_status,
            service="ride-matching",
            timestamp=datetime.utcnow(),
            dependencies={
                "database": "connected" if db_healthy else "disconnected",
                "redis": "connected" if redis_healthy else "disconnected"
            }
        )
        
        # Return appropriate status code
        response_status = status.HTTP_200_OK if overall_status == "healthy" else status.HTTP_503_SERVICE_UNAVAILABLE
        
        return response
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="unhealthy",
            service="ride-matching",
            timestamp=datetime.utcnow(),
            dependencies={
                "database": "error",
                "redis": "error"
            }
        )