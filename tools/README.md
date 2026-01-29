# External Tools

This directory can contain local copies of optional tools for portability.

## Required for 3D Scanning

| Tool | Purpose | Download |
|------|---------|----------|
| COLMAP | Structure-from-Motion & MVS | [colmap.github.io](https://colmap.github.io/install.html) |
| OpenMVS | Dense reconstruction & meshing | [github.com/cdcseacave/openMVS](https://github.com/cdcseacave/openMVS) |

## Installation Options

### Option 1: Local Bundle (Portable)

1. Download COLMAP Windows binary
2. Extract to `tools/COLMAP/`
3. Download OpenMVS Windows binary
4. Extract to `tools/OpenMVS/`

### Option 2: System-Wide Installation

1. Install tools to any location
2. Add to system PATH, or
3. Set environment variables:
   - `COLMAP_PATH` - Path to COLMAP.bat
   - `OPENMVS_PATH` - Path to OpenMVS bin directory

## Structure

When installed locally:

```
tools/
├── COLMAP/
│   └── COLMAP-3.x.x-windows-cuda/
│       └── COLMAP.bat
└── OpenMVS/
    ├── InterfaceCOLMAP.exe
    ├── ReconstructMesh.exe
    └── ...
```

## Note

The scanning features require a CUDA-capable GPU for optimal performance.
Without these tools, STL Creator still works for basic image-to-STL generation.
