# 3D Printer STL Creator

A photogrammetry pipeline that converts photos of real-world objects into 3D-printable STL files.

## Features

- **Multi-Photo Scan** - Upload photos from multiple angles to create 3D models
- **Relief Pipeline** - Convert 2D images into 3D relief sculptures
- **Dense Reconstruction** - Uses COLMAP + OpenMVS for high-quality dense point clouds
- **Progress Tracking** - Real-time progress updates with browser notifications
- **Automatic Cleanup** - Old jobs are automatically cleaned up after 7 days

## Tech Stack

**Backend:**

- Python 3.10+
- FastAPI + Uvicorn
- SQLAlchemy (async SQLite)
- COLMAP (dense reconstruction)
- OpenMVS (meshing)
- Open3D + Trimesh (mesh processing)

**Frontend:**

- Next.js 14
- TypeScript
- TanStack Query
- Tailwind CSS

## Prerequisites

- Python 3.10+
- Node.js 18+
- COLMAP (install to `C:\Tools\COLMAP`)
- OpenMVS (install to `C:\Tools\OpenMVS`)

## Quick Start

### Backend

```bash
cd stl-generator/backend
python -m venv ../../venv
..\..\venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd stl-generator/frontend
npm install
npm run dev
```

Open <http://localhost:3000> in your browser.

## Usage

1. Create a new project
2. Create a SCAN job
3. Upload 20-50 photos of your object (taken from all angles)
4. Submit the job
5. Wait for processing (~30-45 minutes for dense reconstruction)
6. Download the STL file

## Project Structure

```
stl-generator/
├── backend/
│   ├── app/
│   │   ├── api/          # REST endpoints
│   │   ├── models/       # Database models
│   │   ├── services/     # Business logic
│   │   └── workers/      # Pipeline workers
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── app/          # Next.js pages
    │   └── components/   # React components
    └── package.json
```

## License

MIT
