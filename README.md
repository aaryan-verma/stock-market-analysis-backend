# Stock Market Analysis Backend

A FastAPI-based backend application for stock market analysis, providing endpoints for stock data, news, and visualization.

## Features

- [x] REST API using FastAPI with async support
- [x] PostgreSQL database with SQLAlchemy 2.0 and async query support
- [x] Real-time news retrieval from NewsAPI
- [x] Stock data visualization endpoints
- [x] Authentication with JWT tokens
- [x] Alembic migrations for database versioning
- [x] Comprehensive logging setup
- [x] Dockerized deployment support

## Quickstart

### 1. Clone the repository

```bash
git clone <repository-url>
cd stock-market-analysis-backend
```

### 2. Install dependencies

```bash
# Create and activate a virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Setup database

```bash
# Start PostgreSQL database using Docker
docker-compose up -d

# Run Alembic migrations
alembic upgrade head
```

### 4. Create a .env file

Create a `.env` file in the project root with the following content:
```
# Database settings
DATABASE__USERNAME=postgres
DATABASE__PASSWORD=postgres
DATABASE__DB=app
DATABASE__PORT=5432
DATABASE__HOSTNAME=localhost

# Security settings
SECURITY__JWT_SECRET_KEY=your_secret_key

# API Keys
NEWS_API_KEY=your_newsapi_key_here
```

### 5. Run the application

```bash
uvicorn app.main:app --reload
```

The API documentation will be available at http://localhost:8000/redoc

## API Endpoints

- `/news/{symbol}` - Get stock-specific news
- `/visualization` - Stock data visualization
- `/auth/login` - User authentication
- `/auth/refresh` - Refresh JWT token

## Environment Variables

The application requires certain environment variables to be set for proper functioning:

### API Keys
- `NEWS_API_KEY`: API key for NewsAPI.org (required for the news endpoint)

For development, a default API key is provided as fallback, but it's recommended to get your own key for production use.

### Database Configuration
- `DATABASE__USERNAME`: Database username
- `DATABASE__PASSWORD`: Database password
- `DATABASE__DB`: Database name
- `DATABASE__PORT`: Database port
- `DATABASE__HOSTNAME`: Database host

### Security Settings
- `SECURITY__JWT_SECRET_KEY`: Secret key for JWT token generation
- `SECURITY__ALLOWED_HOSTS`: List of allowed hosts (default: ["localhost", "127.0.0.1"])
- `SECURITY__BACKEND_CORS_ORIGINS`: List of allowed CORS origins

## Deployment

### Docker

The application includes a Dockerfile for containerized deployment:

```bash
# Build the Docker image
docker build -t stock-market-analysis-backend .

# Run the container
docker run -p 8000:8000 --env-file .env stock-market-analysis-backend
```

## Data Sources

The backend fetches stock market data from the following sources:

- **Upstox API** - For historical price data for stocks listed on NSE and other exchanges