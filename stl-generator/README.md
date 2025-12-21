# 3D Model to STL Generator

A web application for generating 3D-printable STL files from images using three pipelines:
- **Multi-photo scanning** (photogrammetry/NeRF) - Future
- **Single-image relief** - MVP Focus
- **Generative minis** - Stubbed in MVP

## Tech Stack

- **Frontend**: Next.js 14 + TypeScript + TailwindCSS + shadcn/ui
- **Backend**: FastAPI + Python 3.11
- **Database**: PostgreSQL 15
- **Cache/Queue**: Redis
- **Workflow**: Temporal (simplified to Celery for MVP)
- **Storage**: S3-compatible (MinIO for local)
- **3D Processing**: trimesh, Pillow, depth estimation models
- **Container**: Docker + Docker Compose

## Project Structure

```
stl-generator/
├── frontend/           # Next.js web app
├── backend/           # FastAPI control plane
├── services/          # Worker services & MCP tools
├── docker/            # Docker configurations
├── scripts/           # Setup and utility scripts
└── docs/              # Additional documentation
```

## Quick Start

1. Install prerequisites:
   - Node.js 18+
   - Python 3.11+
   - Docker & Docker Compose
   - PostgreSQL 15
   - Redis

2. Set up environment:
   ```bash
   # Frontend
   cd frontend
   npm install
   cp .env.example .env.local

   # Backend
   cd ../backend
   python -m venv venv
   source venv/bin/activate  # or venv\Scripts\activate on Windows
   pip install -r requirements.txt
   cp .env.example .env
   ```

3. Start services:
   ```bash
   docker-compose up -d
   ```

4. Run migrations:
   ```bash
   cd backend
   alembic upgrade head
   ```

5. Start development servers:
   ```bash
   # Terminal 1: Backend
   cd backend
   uvicorn main:app --reload

   # Terminal 2: Frontend
   cd frontend
   npm run dev
   ```

## MVP Scope (4-8 weeks)

Focus on Relief Pipeline (single image to relief STL):
- Upload single image
- Generate depth map
- Create relief mesh
- Basic printability validation
- Export STL

See `project_spec.md` for full details.
