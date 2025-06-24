from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import sys
import structlog

from .config import settings
from .utils.redis_client import redis_client
from .routes import health, rides, drivers

# Configure structured logging
logging.basicConfig(
    format="%(message)s",
    stream=sys.stdout,
    level=logging.INFO,
)

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting Ride Matching Service")
    
    try:
        # Connect to Redis
        await redis_client.connect()
        logger.info("Connected to external services")
        
        yield
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise
    finally:
        # Shutdown
        logger.info("Shutting down Ride Matching Service")
        try:
            await redis_client.disconnect()
            logger.info("Disconnected from external services")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")


# Create FastAPI app
app = FastAPI(
    title="Ride Matching Service",
    description="Microservice for handling ride requests and driver matching",
    version="1.0.0",
    debug=settings.debug,
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Middleware for request logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests"""
    start_time = request.state.start_time = 0
    
    # Generate correlation ID for tracing
    correlation_id = request.headers.get("x-correlation-id", "unknown")
    
    logger.info(
        "Request started",
        method=request.method,
        url=str(request.url),
        correlation_id=correlation_id
    )
    
    response = await call_next(request)
    
    logger.info(
        "Request completed",
        method=request.method,
        url=str(request.url),
        status_code=response.status_code,
        correlation_id=correlation_id
    )
    
    return response


# Include routers
app.include_router(health.router)
app.include_router(rides.router)
app.include_router(drivers.router)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "ride-matching",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/api/rides/health",
            "docs": "/docs",
            "redoc": "/redoc"
        }
    }


# Health check for Kubernetes
@app.get("/health")
async def simple_health():
    """Simple health check for load balancers"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.debug,
        log_level="info"
    )