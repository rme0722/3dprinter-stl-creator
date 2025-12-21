#!/bin/bash

# Setup script for 3D STL Generator

echo "Setting up 3D STL Generator..."

# Check for required tools
command -v docker >/dev/null 2>&1 || { echo "Docker is required but not installed. Aborting." >&2; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { echo "Docker Compose is required but not installed. Aborting." >&2; exit 1; }
command -v node >/dev/null 2>&1 || { echo "Node.js is required but not installed. Aborting." >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "Python 3 is required but not installed. Aborting." >&2; exit 1; }

echo "Starting infrastructure services..."
docker-compose up -d

echo "Waiting for services to start..."
sleep 10

echo "Setting up backend..."
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

echo "Running database migrations..."
alembic upgrade head

echo "Initializing database with default data..."
python scripts/init_db.py

echo "Setting up frontend..."
cd ../frontend
npm install
cp .env.example .env.local

echo "Setup complete!"
echo ""
echo "To start the development servers:"
echo "  Backend: cd backend && source venv/bin/activate && uvicorn app.main:app --reload"
echo "  Frontend: cd frontend && npm run dev"
echo ""
echo "Services running:"
echo "  PostgreSQL: localhost:5432"
echo "  Redis: localhost:6379"
echo "  MinIO: localhost:9000 (console: localhost:9001)"
echo ""
echo "Default credentials:"
echo "  MinIO: minioadmin/minioadmin"
echo "  PostgreSQL: user/password"
