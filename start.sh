#!/bin/bash
echo "Starting server on port: $PORT"
echo "Current directory: $(pwd)"
echo "Python version: $(python --version)"

# Run migrations first
echo "Running database migrations..."
alembic upgrade head

# Start the server with default port 10000
echo "Starting server on port: ${PORT:-10000}"
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000} --workers 4 