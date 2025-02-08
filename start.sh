#!/bin/bash
echo "Starting server on port: $PORT"
echo "Current directory: $(pwd)"
echo "Python version: $(python --version)"
echo "Contents of current directory: $(ls -la)"

uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 4 