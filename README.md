# 🚖 Ride Matching Service

A high-performance FastAPI microservice for handling ride requests and driver matching in the RideShare Pro platform.

## 🎯 Features

- **Ride Request Management**: Create, track, and manage ride requests
- **Driver Matching**: Intelligent algorithm to match riders with available drivers
- **Real-time Updates**: Redis-based event system for live notifications
- **Location Management**: Simple city/area-based driver location tracking
- **Status Tracking**: Complete ride lifecycle management
- **Health Monitoring**: Kubernetes-ready health checks

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────┐    ┌─────────────────┐
│   FastAPI App   │────│ PostgreSQL   │    │     Redis       │
│                 │    │              │    │                 │
│ • Ride Routes   │    │ • Rides      │    │ • Driver Status │
│ • Driver Routes │    │ • Locations  │    │ • Events/PubSub │
│ • Health Check  │    │              │    │ • Caching       │
└─────────────────┘    └──────────────┘    └─────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+ (for local development)
- PostgreSQL 15+
- Redis 7+

### 1. Clone and Setup

```bash
git clone <repository-url>
cd ride-matching-service
```

### 2. Environment Configuration

Create a `.env` file:

```bash
# Application
DEBUG=true
PORT=8002

# Database
DATABASE_URL=postgresql+asyncpg://rideshare:password@localhost:5432/rideshare_db

# Redis
REDIS_URL=redis://localhost:6379/0

# External Services
USER_SERVICE_URL=http://user-service:8001
PAYMENT_SERVICE_URL=http://payment-service:8003
NOTIFICATION_SERVICE_URL=http://notification-service:8004

# Business Logic
MAX_DRIVERS_TO_NOTIFY=3
DRIVER_RESPONSE_TIMEOUT=30
BASE_FARE=2.50
PER_KM_RATE=1.20
PER_MINUTE_RATE=0.25
```

### 3. Run with Docker Compose

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f ride-matching-service

# Stop services
docker-compose down
```

### 4. Access the Application

- **API Documentation**: http://localhost:8002/docs
- **Health Check**: http://localhost:8002/health
- **Redis Commander**: http://localhost:8081
- **pgAdmin**: http://localhost:8080 (admin@rideshare.com / admin)

## 📋 API Endpoints

### Ride Management

```http
POST   /api/rides/request           # Request a new ride
GET    /api/rides/{ride_id}         # Get ride details
PUT    /api/rides/{ride_id}/status  # Update ride status (driver)
POST   /api/rides/{ride_id}/cancel  # Cancel ride
GET    /api/rides/history           # Get ride history
```

### Driver Management

```http
PUT    /api/rides/driver/location     # Update driver location
GET    /api/rides/driver/availability # Get availability status
PUT    /api/rides/driver/availability # Update availability
GET    /api/rides/nearby-drivers      # Get nearby drivers
```

### Health & Monitoring

```http
GET    /api/rides/health             # Detailed health check
GET    /health                       # Simple health check
```

## 🧪 Testing the API

### 1. Request a Ride

```bash
curl -X POST "http://localhost:8002/api/rides/request" \
  -H "Authorization: Bearer mock-token" \
  -H "Content-Type: application/json" \
  -d '{
    "pickup_address": "Victoria Island, Lagos",
    "destination_address": "Ikoyi, Lagos",
    "ride_type": "standard",
    "special_requests": "Please call when you arrive"
  }'
```

### 2. Update Driver Location

```bash
curl -X PUT "http://localhost:8002/api/rides/driver/location" \
  -H "Authorization: Bearer driver-token" \
  -H "Content-Type: application/json" \
  -d '{
    "city": "Lagos",
    "area": "Victoria Island",
    "is_available": true
  }'
```

### 3. Check Ride Status

```bash
curl -X GET "http://localhost:8002/api/rides/{ride_id}" \
  -H "Authorization: Bearer mock-token"
```

## 🔧 Development

### Local Development Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL="postgresql+asyncpg://rideshare:password@localhost:5432/rideshare_db"
export REDIS_URL="redis://localhost:6379/0"

# Run the application
python -m uvicorn app.main:app --reload --port 8002
```

### Database Migrations

```bash
# Generate migration
alembic revision --autogenerate -m "Create initial tables"

# Run migrations
alembic upgrade head
```

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-mock

# Run tests
pytest tests/ -v
```

## 📊 Business Logic

### Matching Algorithm

1. **Extract Location**: Parse city/area from pickup address
2. **Find Drivers**: Search available drivers in same area
3. **Expand Search**: If no drivers found, search entire city
4. **Select Driver**: Pick first available driver (FIFO)
5. **Notify**: Send ride request to selected driver
6. **Timeout**: 30-second response window

### Fare Calculation

```python
Base Fare: $2.50
+ Distance Rate: $1.20 per km (estimated)
+ Time Rate: $0.25 per minute (traffic)
= Total Estimated Fare
```

### Status Transitions

```
requested → matched → accepted → pickup → in_progress → completed
     ↓         ↓         ↓         ↓           ↓
  cancelled  cancelled  cancelled  cancelled  cancelled
```

## 🚀 Events & Integration

### Published Events

**Ride Events** (`ride-events` channel):

- `ride_requested` - New ride request created
- `ride_matched` - Driver assigned to ride
- `ride_accepted` - Driver accepted the ride
- `ride_cancelled` - Ride was cancelled
- `ride_completed` - Ride finished successfully

**Driver Notifications** (`driver-notifications` channel):

- `ride_request` - New ride request for driver
- `ride_cancelled` - Assigned ride was cancelled

**User Notifications** (`user-notifications` channel):

- `ride_matched` - Driver found for your ride
- `ride_accepted` - Driver accepted your ride
- `ride_cancelled` - Your ride was cancelled

### Event Schema

```json
{
  "event_id": "uuid",
  "event_type": "ride_requested",
  "timestamp": "2025-01-01T12:00:00Z",
  "service": "ride-matching",
  "data": {
    "ride_id": "uuid",
    "rider_id": "uuid",
    "pickup_address": "Victoria Island, Lagos"
  }
}
```

## 🔧 Configuration

### Environment Variables

| Variable                  | Default | Description                       |
| ------------------------- | ------- | --------------------------------- |
| `DEBUG`                   | `false` | Enable debug mode                 |
| `PORT`                    | `8002`  | Application port                  |
| `DATABASE_URL`            | -       | PostgreSQL connection string      |
| `REDIS_URL`               | -       | Redis connection string           |
| `MAX_DRIVERS_TO_NOTIFY`   | `3`     | Max drivers per ride request      |
| `DRIVER_RESPONSE_TIMEOUT` | `30`    | Driver response timeout (seconds) |
| `BASE_FARE`               | `2.50`  | Base ride fare                    |
| `PER_KM_RATE`             | `1.20`  | Rate per kilometer                |

## 🐳 Docker Deployment

### Build Image

```bash
docker build -t ride-matching-service:latest .
```

### Run Container

```bash
docker run -d \
  --name ride-matching \
  -p 8002:8002 \
  -e DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/db" \
  -e REDIS_URL="redis://host:6379/0" \
  ride-matching-service:latest
```

## 📈 Monitoring

### Health Checks

- **Liveness**: `GET /health` - Simple status check
- **Readiness**: `GET /api/rides/health` - Detailed dependency check

### Logging

The service uses structured JSON logging:

```json
{
  "timestamp": "2025-01-01T12:00:00Z",
  "level": "info",
  "event": "Request started",
  "method": "POST",
  "url": "/api/rides/request",
  "correlation_id": "uuid"
}
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is part of the RideShare Pro platform - Module 1 Kubernetes Project.

---

**Ready to match some rides!** 🚖✨
