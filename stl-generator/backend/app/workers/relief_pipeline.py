"""Relief Pipeline Worker - Single image to relief STL"""
import io
import uuid
import hashlib
from typing import Dict, Any, Optional
from PIL import Image
import numpy as np
import trimesh
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Job, Artifact
from app.models.job import JobState
from app.models.artifact import ArtifactType, ArtifactFormat
from app.models.validation import ValidationReport, ValidationFinding, ValidationScope, ValidationStatus, FindingSeverity
from app.core.config import settings


class ReliefPipeline:
    """Pipeline B: Single image to relief/bas-relief STL"""
    
    def __init__(self, job_id: str, db: AsyncSession):
        self.job_id = job_id
        self.db = db
        self.job: Optional[Job] = None
        
    async def run(self):
        """Main pipeline execution"""
        try:
            # Load job
            self.job = await self.db.get(Job, self.job_id)
            if not self.job:
                raise ValueError(f"Job {self.job_id} not found")
            
            # Update state to VALIDATING
            await self._update_job_state(JobState.VALIDATING)
            
            # Step 1: Validate input image
            input_artifact = await self._get_input_artifact()
            if not input_artifact:
                await self._fail_job("No input image provided")
                return
                
            validation_passed = await self._validate_input(input_artifact)
            if not validation_passed:
                await self._update_job_state(JobState.ACTION_REQUIRED, "Input validation failed")
                return
            
            # Update state to RUNNING
            await self._update_job_state(JobState.RUNNING)
            
            # Step 2: Generate depth map
            depth_map = await self._generate_depth_map(input_artifact)
            
            # Step 3: Create relief mesh
            relief_mesh = await self._create_relief_mesh(depth_map)
            
            # Step 4: Clean and repair mesh
            cleaned_mesh = await self._clean_mesh(relief_mesh)
            
            # Step 5: Scale to target dimensions
            scaled_mesh = await self._scale_mesh(cleaned_mesh)
            
            # Step 6: Validate printability
            printability_passed = await self._validate_printability(scaled_mesh)
            if not printability_passed:
                await self._update_job_state(JobState.REVIEW_REQUIRED, "Printability issues detected")
                return
            
            # Step 7: Export STL
            stl_artifact = await self._export_stl(scaled_mesh)
            
            # Step 8: Calculate quality score
            await self._calculate_quality_score()
            
            # Update state to SUCCEEDED
            await self._update_job_state(JobState.SUCCEEDED)
            
        except Exception as e:
            await self._fail_job(str(e))
    
    async def _update_job_state(self, state: JobState, hold_reason: Optional[str] = None):
        """Update job state"""
        self.job.state = state
        self.job.hold_reason = hold_reason
        await self.db.commit()
        await self.db.refresh(self.job)
    
    async def _fail_job(self, error_message: str):
        """Mark job as failed"""
        self.job.state = JobState.FAILED
        self.job.error_message = error_message
        await self.db.commit()
    
    async def _get_input_artifact(self) -> Optional[Artifact]:
        """Get the input image artifact"""
        # Query for RAW_IMAGE artifact
        from sqlalchemy import select
        result = await self.db.execute(
            select(Artifact).where(
                Artifact.job_id == self.job_id,
                Artifact.artifact_type == ArtifactType.RAW_IMAGE
            )
        )
        return result.scalar_one_or_none()
    
    async def _validate_input(self, artifact: Artifact) -> bool:
        """Validate input image"""
        report = ValidationReport(
            id=f"vr_{uuid.uuid4().hex[:12]}",
            job_id=self.job_id,
            scope=ValidationScope.INPUT,
            status=ValidationStatus.PASS
        )
        
        # TODO: Download image from S3 and validate
        # For MVP, we'll simulate validation
        
        # Check resolution
        min_resolution = 512
        # Simulated check - in real implementation, download and check actual image
        width, height = 1024, 1024  # Placeholder
        
        if width < min_resolution or height < min_resolution:
            finding = ValidationFinding(
                id=f"vf_{uuid.uuid4().hex[:12]}",
                report_id=report.id,
                severity=FindingSeverity.ERROR,
                code="LOW_RESOLUTION",
                title="Image resolution too low",
                message_plain=f"Image resolution {width}x{height} is below minimum {min_resolution}x{min_resolution}",
                metric_name="resolution",
                metric_value=min(width, height),
                threshold=min_resolution
            )
            report.findings.append(finding)
            report.status = ValidationStatus.FAIL
        
        self.db.add(report)
        await self.db.commit()
        
        return report.status == ValidationStatus.PASS
    
    async def _generate_depth_map(self, input_artifact: Artifact) -> np.ndarray:
        """Generate depth map from input image"""
        # TODO: Implement actual depth estimation
        # For MVP, generate a simple gradient depth map
        
        # Simulate depth map generation
        depth_map = np.random.rand(256, 256) * 10  # 10mm max depth
        
        # Save depth map artifact
        depth_artifact = Artifact(
            id=f"art_{uuid.uuid4().hex[:12]}",
            job_id=self.job_id,
            project_id=self.job.project_id,
            artifact_type=ArtifactType.DEPTH_MAP,
            format=ArtifactFormat.PNG,
            uri=f"jobs/{self.job_id}/depth_map.png",
            sha256=hashlib.sha256(depth_map.tobytes()).hexdigest(),
            size_bytes=depth_map.nbytes,
            metadata_json={"width": 256, "height": 256, "max_depth_mm": 10}
        )
        self.db.add(depth_artifact)
        await self.db.commit()
        
        return depth_map
    
    async def _create_relief_mesh(self, depth_map: np.ndarray) -> trimesh.Trimesh:
        """Create relief mesh from depth map"""
        height, width = depth_map.shape
        
        # Create grid of vertices
        xx, yy = np.meshgrid(np.arange(width), np.arange(height))
        vertices = np.stack([xx.ravel(), yy.ravel(), depth_map.ravel()], axis=1)
        
        # Create faces (two triangles per pixel)
        faces = []
        for i in range(height - 1):
            for j in range(width - 1):
                idx = i * width + j
                # First triangle
                faces.append([idx, idx + 1, idx + width])
                # Second triangle
                faces.append([idx + 1, idx + width + 1, idx + width])
        
        mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
        
        # Add base
        mesh = self._add_base_to_relief(mesh)
        
        return mesh
    
    def _add_base_to_relief(self, mesh: trimesh.Trimesh) -> trimesh.Trimesh:
        """Add a solid base to the relief mesh"""
        # Create a box for the base
        bounds = mesh.bounds
        base_height = 2.0  # 2mm base
        
        base_box = trimesh.creation.box(
            extents=[
                bounds[1][0] - bounds[0][0],
                bounds[1][1] - bounds[0][1],
                base_height
            ]
        )
        
        # Position base below the relief
        base_box.apply_translation([
            (bounds[1][0] + bounds[0][0]) / 2,
            (bounds[1][1] + bounds[0][1]) / 2,
            bounds[0][2] - base_height / 2
        ])
        
        # Combine relief and base
        combined = trimesh.util.concatenate([mesh, base_box])
        return combined
    
    async def _clean_mesh(self, mesh: trimesh.Trimesh) -> trimesh.Trimesh:
        """Clean and repair the mesh"""
        # Remove duplicate vertices
        mesh.remove_duplicate_faces()
        mesh.remove_degenerate_faces()
        
        # Fill holes if any
        if not mesh.is_watertight:
            mesh.fill_holes()
        
        # Save cleaned mesh artifact
        cleaned_artifact = Artifact(
            id=f"art_{uuid.uuid4().hex[:12]}",
            job_id=self.job_id,
            project_id=self.job.project_id,
            artifact_type=ArtifactType.MESH_CLEANED,
            format=ArtifactFormat.PLY,
            uri=f"jobs/{self.job_id}/mesh_cleaned.ply",
            sha256=hashlib.sha256(mesh.export(file_type='ply')).hexdigest(),
            size_bytes=len(mesh.export(file_type='ply')),
            metadata_json={
                "vertices": len(mesh.vertices),
                "faces": len(mesh.faces),
                "watertight": mesh.is_watertight
            }
        )
        self.db.add(cleaned_artifact)
        await self.db.commit()
        
        return mesh
    
    async def _scale_mesh(self, mesh: trimesh.Trimesh) -> trimesh.Trimesh:
        """Scale mesh to target dimensions"""
        config = self.job.config or {}
        target_scale = config.get("output_scale_preset", "MINI_32MM")
        
        # Define scale presets (in mm)
        scale_presets = {
            "MINI_28MM": 28.0,
            "MINI_32MM": 32.0,
            "CUSTOM": config.get("custom_scale_mm", 30.0)
        }
        
        target_size = scale_presets.get(target_scale, 32.0)
        
        # Scale to fit in target size bounding box
        current_size = mesh.extents.max()
        scale_factor = target_size / current_size
        mesh.apply_scale(scale_factor)
        
        # Save scaled mesh artifact
        scaled_artifact = Artifact(
            id=f"art_{uuid.uuid4().hex[:12]}",
            job_id=self.job_id,
            project_id=self.job.project_id,
            artifact_type=ArtifactType.MESH_SCALED_MM,
            format=ArtifactFormat.PLY,
            uri=f"jobs/{self.job_id}/mesh_scaled.ply",
            sha256=hashlib.sha256(mesh.export(file_type='ply')).hexdigest(),
            size_bytes=len(mesh.export(file_type='ply')),
            metadata_json={
                "scale_preset": target_scale,
                "dimensions_mm": mesh.extents.tolist(),
                "scale_factor": scale_factor
            }
        )
        self.db.add(scaled_artifact)
        await self.db.commit()
        
        return mesh
    
    async def _validate_printability(self, mesh: trimesh.Trimesh) -> bool:
        """Validate mesh printability"""
        report = ValidationReport(
            id=f"vr_{uuid.uuid4().hex[:12]}",
            job_id=self.job_id,
            scope=ValidationScope.PRINTABILITY,
            status=ValidationStatus.PASS
        )
        
        # Check if watertight
        if not mesh.is_watertight:
            finding = ValidationFinding(
                id=f"vf_{uuid.uuid4().hex[:12]}",
                report_id=report.id,
                severity=FindingSeverity.ERROR,
                code="NOT_WATERTIGHT",
                title="Mesh is not watertight",
                message_plain="The mesh has holes and cannot be printed",
                recommended_action="REPAIR"
            )
            report.findings.append(finding)
            report.status = ValidationStatus.FAIL
        
        # Check minimum wall thickness (simplified)
        min_thickness = 0.4  # 0.4mm minimum
        # For relief, check base thickness
        if mesh.extents[2] < min_thickness:
            finding = ValidationFinding(
                id=f"vf_{uuid.uuid4().hex[:12]}",
                report_id=report.id,
                severity=FindingSeverity.WARNING,
                code="THIN_WALLS",
                title="Thin features detected",
                message_plain=f"Model has features thinner than {min_thickness}mm",
                metric_name="min_thickness",
                metric_value=mesh.extents[2],
                threshold=min_thickness
            )
            report.findings.append(finding)
            if report.status == ValidationStatus.PASS:
                report.status = ValidationStatus.WARN
        
        self.db.add(report)
        await self.db.commit()
        
        return report.status != ValidationStatus.FAIL
    
    async def _export_stl(self, mesh: trimesh.Trimesh) -> Artifact:
        """Export mesh as STL"""
        stl_bytes = mesh.export(file_type='stl')
        
        stl_artifact = Artifact(
            id=f"art_{uuid.uuid4().hex[:12]}",
            job_id=self.job_id,
            project_id=self.job.project_id,
            artifact_type=ArtifactType.FINAL_STL,
            format=ArtifactFormat.STL,
            uri=f"jobs/{self.job_id}/final.stl",
            sha256=hashlib.sha256(stl_bytes).hexdigest(),
            size_bytes=len(stl_bytes),
            metadata_json={
                "vertices": len(mesh.vertices),
                "faces": len(mesh.faces),
                "dimensions_mm": mesh.extents.tolist(),
                "volume_mm3": mesh.volume,
                "watertight": mesh.is_watertight
            }
        )
        self.db.add(stl_artifact)
        await self.db.commit()
        
        # TODO: Actually upload to S3
        
        return stl_artifact
    
    async def _calculate_quality_score(self):
        """Calculate and store quality score"""
        # Gather metrics
        input_quality = 0.8  # Placeholder - based on resolution, contrast, etc.
        reconstruction_confidence = 0.7  # Placeholder - based on depth map quality
        printability_risk = 0.1  # Based on validation findings
        
        # Apply pipeline-specific weights
        w_in = settings.RELIEF_WEIGHT_INPUT
        w_rec = settings.RELIEF_WEIGHT_RECON  
        w_pr = settings.RELIEF_WEIGHT_PRINT
        
        quality_score = (
            w_in * input_quality +
            w_rec * reconstruction_confidence +
            w_pr * (1 - printability_risk)
        )
        
        self.job.quality_score = quality_score
        self.job.quality_score_version = "v1"
        self.job.quality_summary = {
            "input_quality": input_quality,
            "reconstruction_confidence": reconstruction_confidence,
            "printability_risk": printability_risk,
            "notes": []
        }
        
        await self.db.commit()
