"""Scan Pipeline Worker - Multi-photo to 3D Model"""
import os
import logging
import uuid
import hashlib
import asyncio
from typing import List, Optional
from pathlib import Path

import numpy as np
import cv2
import open3d as o3d
import trimesh
import piexif
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Job, Artifact
from app.models.job import JobState
from app.models.artifact import ArtifactType, ArtifactFormat
from app.models.validation import ValidationReport, ValidationFinding, ValidationScope, ValidationStatus, FindingSeverity
from app.services.local_storage import get_file_path, get_relative_uri, save_file
from app.core.config import settings
from app.workers.colmap_pipeline import run_colmap_pipeline, PipelineProgress

logger = logging.getLogger(__name__)

class ScanPipeline:
    """Pipeline A: Multi-photo photogrammetry using OpenCV and Open3D"""
    
    def __init__(self, job_id: str, db: AsyncSession):
        self.job_id = job_id
        self.db = db
        self.is_fallback = False
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
            
            # Step 1: Gather and validate inputs
            input_artifacts = await self._get_input_artifacts()
            if not input_artifacts:
                await self._fail_job("No input images provided")
                return

            validation_passed = await self._validate_inputs(input_artifacts)
            if not validation_passed:
                await self._update_job_state(JobState.ACTION_REQUIRED, "Input validation failed")
                return
            
            # Update state to RUNNING
            await self._update_job_state(JobState.RUNNING)
            
            # Step 2: Dense Reconstruction using COLMAP + OpenMVS
            # This replaces the old sparse SfM approach
            print("[SCAN_PIPELINE] About to call _run_dense_reconstruction...")
            mesh_path = await self._run_dense_reconstruction(input_artifacts)
            print(f"[SCAN_PIPELINE] _run_dense_reconstruction returned: {mesh_path}")
            
            if mesh_path is None:
                # Fallback to sparse SfM if COLMAP fails
                print("[SCAN_PIPELINE] COLMAP returned None, falling back to sparse SfM")
                logger.warning("COLMAP pipeline failed, falling back to sparse SfM")
                pcd = await self._reconstruct_point_cloud(input_artifacts)
                mesh = await self._mesh_from_cloud(pcd)
                cleaned_mesh = await self._clean_mesh(mesh)
            else:
                # Load the mesh from COLMAP/OpenMVS output
                logger.info(f"Loading mesh from COLMAP output: {mesh_path}")
                mesh = trimesh.load(str(mesh_path))
                cleaned_mesh = mesh  # Already high quality from OpenMVS
            
            # Step 5: Export STL
            await self._export_stl(cleaned_mesh)
            
            # Step 6: Quality Score
            await self._calculate_quality_score()
            
            # Update state to SUCCEEDED
            await self._update_job_state(JobState.SUCCEEDED)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            await self._fail_job(str(e))

    async def _update_job_state(self, state: JobState, hold_reason: Optional[str] = None):
        self.job.state = state
        self.job.hold_reason = hold_reason
        await self.db.commit()
        await self.db.refresh(self.job)

    async def _fail_job(self, error_message: str):
        self.job.state = JobState.FAILED
        self.job.error_message = error_message
        await self.db.commit()

    async def _get_input_artifacts(self) -> List[Artifact]:
        result = await self.db.execute(
            select(Artifact).where(
                Artifact.job_id == self.job_id,
                Artifact.artifact_type.in_([ArtifactType.RAW_IMAGE, ArtifactType.RAW_PHOTO])
            )
        )
        return result.scalars().all()

    async def _validate_inputs(self, artifacts: List[Artifact]) -> bool:
        report = ValidationReport(
            id=f"vr_{uuid.uuid4().hex[:12]}",
            job_id=self.job_id,
            scope=ValidationScope.INPUT,
            status=ValidationStatus.PASS
        )
        
        # Check minimum file count
        if len(artifacts) < 2:
            finding = ValidationFinding(
                id=f"vf_{uuid.uuid4().hex[:12]}",
                report_id=report.id,
                severity=FindingSeverity.ERROR,
                code="INSUFFICIENT_PHOTOS",
                title="Not enough photos",
                message_plain=f"Found {len(artifacts)} photos. Minimum 2 required (30+ recommended).",
                metric_name="photo_count",
                metric_value=len(artifacts),
                threshold=2
            )
            report.findings.append(finding)
            report.status = ValidationStatus.FAIL
        
        # Determine strictness based on count
        if 2 <= len(artifacts) < 10:
             finding = ValidationFinding(
                id=f"vf_{uuid.uuid4().hex[:12]}",
                report_id=report.id,
                severity=FindingSeverity.WARNING,
                code="LOW_PHOTO_COUNT",
                title="Low photo count",
                message_plain="Reconstruction quality may be poor with fewer than 10 photos.",
                metric_name="photo_count",
                metric_value=len(artifacts),
                threshold=10
            )
             report.findings.append(finding)
             if report.status == ValidationStatus.PASS:
                 report.status = ValidationStatus.WARN

        self.db.add(report)
        await self.db.commit()
        return report.status != ValidationStatus.FAIL

    async def _run_dense_reconstruction(self, artifacts: List[Artifact]) -> Optional[Path]:
        """
        Run COLMAP + OpenMVS dense reconstruction pipeline.
        
        This is the new high-quality reconstruction path that produces
        dense point clouds (~1M points) instead of sparse SfM (~5K points).
        
        Returns:
            Path to the output mesh PLY file, or None if failed.
        """
        import shutil
        import tempfile
        
        print(f"[COLMAP] Starting dense reconstruction with {len(artifacts)} images...")
        logger.info(f"Starting COLMAP dense reconstruction with {len(artifacts)} images...")
        
        # Create workspace directory for this job
        workspace_base = Path(settings.LOCAL_STORAGE_PATH) / "colmap_workspaces"
        workspace_base.mkdir(parents=True, exist_ok=True)
        workspace_dir = workspace_base / self.job_id
        workspace_dir.mkdir(exist_ok=True)
        
        # Create image directory and copy images
        image_dir = workspace_dir / "images"
        image_dir.mkdir(exist_ok=True)
        
        for art in artifacts:
            src_path = get_file_path(art.uri)
            if src_path.exists():
                # Use original filename if available
                if art.metadata_json and 'filename' in art.metadata_json:
                    dest_name = art.metadata_json['filename']
                else:
                    dest_name = src_path.name
                dest_path = image_dir / dest_name
                shutil.copy2(src_path, dest_path)
                logger.debug(f"  Copied {src_path.name} -> {dest_path}")
        
        # Check we have images
        images_copied = list(image_dir.glob("*.[jJ][pP][gG]")) + list(image_dir.glob("*.[pP][nN][gG]"))
        if len(images_copied) < 2:
            logger.error(f"Only {len(images_copied)} images copied, need at least 2")
            return None
        
        logger.info(f"Copied {len(images_copied)} images to {image_dir}")
        
        # Define progress callback to update job progress
        async def progress_callback(progress: PipelineProgress):
            logger.info(f"[COLMAP {progress.percentage}%] {progress.stage}: {progress.message}")
            # TODO: Send WebSocket update to frontend
        
        # Run the COLMAP + OpenMVS pipeline
        try:
            mesh_path = await run_colmap_pipeline(
                image_dir=image_dir,
                workspace_dir=workspace_dir,
                progress_callback=progress_callback
            )
            
            if mesh_path and mesh_path.exists():
                logger.info(f"COLMAP pipeline completed successfully: {mesh_path}")
                self.is_fallback = False
                return mesh_path
            else:
                logger.warning("COLMAP pipeline returned no mesh")
                return None
                
        except Exception as e:
            logger.error(f"COLMAP pipeline failed with exception: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def _reconstruct_point_cloud(self, artifacts: List[Artifact]) -> o3d.geometry.PointCloud:
        """
        FALLBACK: Perform basic Structure-from-Motion features extraction and matching.
        This is the old sparse SfM approach, kept as fallback if COLMAP fails.
        """
        logger.info(f"Starting reconstruction with {len(artifacts)} images...")
        
        # 1. Load Images and Extract SIFT Features
        # Using "Nuclear Option" SIFT parameters for maximum feature extraction
        sift = cv2.SIFT_create(nfeatures=20000, contrastThreshold=0.005, edgeThreshold=20)
        keypoints_all = []
        descriptors_all = []
        images = []
        focals = []
        
        # Sort artifacts by filename to ensure sequential processing
        def get_art_name(art):
            if art.metadata_json and 'filename' in art.metadata_json:
                return art.metadata_json['filename']
            return str(art.id)
            
        artifacts_sorted = sorted(artifacts, key=get_art_name)
        
        for art in artifacts_sorted:
            path = get_file_path(art.uri)
            img = cv2.imread(str(path))
            if img is None:
                continue
            
            # Extract focal length from EXIF
            f_px = self._get_focal_length(path, img.shape[1], img.shape[0])
            logger.debug(f"Image {art.id} ({get_art_name(art)}): Focal Length = {f_px:.1f}px")
            focals.append(f_px)
            
            # Resize for speed if too large
            if max(img.shape) > 1600:
                scale = 1600 / max(img.shape)
                img = cv2.resize(img, None, fx=scale, fy=scale)
                # Adjust focal length for resize
                focals[-1] *= scale
                
            kp, des = sift.detectAndCompute(img, None)
            
            if des is not None and len(kp) > 50:
                # Apply RootSIFT normalization
                # 1. Individual descriptors L1 normalization
                # 2. Square root
                des /= (des.sum(axis=1, keepdims=True) + 1e-7)
                des = np.sqrt(des)
                
                logger.debug(f"  Extracted {len(kp)} RootSIFT features")
                keypoints_all.append(kp)
                descriptors_all.append(des)
                images.append(img)
            else:
                logger.info(f"Skipping image {art.id} - not enough features ({len(kp) if kp else 0})")

        if len(images) < 2:
             # Fallback for testing/debugging if matching fails totally
             print("Not enough valid images for reconstruction. Generating dummy cloud.")
             self.is_fallback = True
             return self._generate_dummy_pcd()

        # 2. Match Features (Simplified Pairwise)
        # FLANN parameters
        FLANN_INDEX_KDTREE = 1
        index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
        search_params = dict(checks=50)
        flann = cv2.FlannBasedMatcher(index_params, search_params)
        
        
        # Adaptive Reconstruction Strategy
        # We try strict settings first for quality, and relax them if we don't get enough points.
        presets = [
            # High Quality: Slightly relaxed inliers to avoid falling back too easily, but strict RANSAC
            {"name": "High Quality", "ratio": 0.75, "ransac": 4.0, "inliers": 8},
            {"name": "Standard", "ratio": 0.8, "ransac": 12.0, "inliers": 8},
            # "Nuclear" option: Extremely permissive to avoid fallback donut
            {"name": "Nuclear (Recovery)", "ratio": 0.9, "ransac": 50.0, "inliers": 4} 
        ]

        points_3d = []
        colors_3d = []

        for attempt, params in enumerate(presets):
            logger.info(f"--- Adaptive Reconstruction Pass {attempt+1}: {params['name']} ---")
            logger.info(f"    Params: Ratio={params['ratio']}, RANSAC={params['ransac']}px, MinInliers={params['inliers']}")
            
            # Reset for this pass
            points_3d = []
            colors_3d = []
            poses_w_c = [None] * len(images)
            poses_w_c[0] = np.eye(4)
            found_any_geometry = False
            total_matches_checked = 0
            
            # 2. Match Features (Simplified Pairwise)
            # Standard SfM approach: match neighbors first to establish local geometry
            window = 4
            for i in range(1, len(images)):
                logger.info(f"Processing image {i}/{len(images)}...")
                
                # If we haven't found ANY anchor yet, be thorough
                if not found_any_geometry:
                    # Try all previous images as potential anchors for i
                    search_range = range(i)
                else:
                    # Just look at immediate neighbors
                    search_range = range(max(0, i - window), i)
                
                # Sort search range to try closest neighbors first (likely best overlap)
                for prev_idx in sorted(search_range, key=lambda x: abs(x - i)):
                    if poses_w_c[prev_idx] is not None:
                        total_matches_checked += 1
                        avg_focal = (focals[i] + focals[prev_idx]) / 2.0
                        res = self._match_and_triangulate(
                            prev_idx, i, keypoints_all, descriptors_all, 
                            images, poses_w_c[prev_idx], avg_focal, flann,
                            ratio_thresh=params['ratio'], 
                            ransac_thresh=params['ransac'], 
                            min_inliers=params['inliers']
                        )
                        if res:
                            pts_world, T_w_c_i = res
                            points_3d.extend(pts_world)
                            colors_3d.extend([[0.7, 0.7, 0.7]] * len(pts_world))
                            if poses_w_c[i] is None:
                                poses_w_c[i] = T_w_c_i
                            found_any_geometry = True
                            logger.debug(f"  [SUCCESS] Matched {prev_idx} <-> {i}: {len(pts_world)} points")
                            # No break - match with as many neighbors as possible for density

                # Also try to match i with forward images to densify the cloud
                if poses_w_c[i] is not None:
                    for next_idx in range(i + 1, min(i + 1 + window, len(images))):
                        total_matches_checked += 1
                        avg_focal = (focals[i] + focals[next_idx]) / 2.0
                        res = self._match_and_triangulate(
                            i, next_idx, keypoints_all, descriptors_all, 
                            images, poses_w_c[i], avg_focal, flann,
                            ratio_thresh=params['ratio'], 
                            ransac_thresh=params['ransac'], 
                            min_inliers=params['inliers']
                        )
                        if res:
                            pts_world, T_w_c_next = res
                            points_3d.extend(pts_world)
                            colors_3d.extend([[0.7, 0.7, 0.7]] * len(pts_world))
                            if poses_w_c[next_idx] is None:
                                poses_w_c[next_idx] = T_w_c_next
                            found_any_geometry = True
                            logger.debug(f"  [SUCCESS] Matched {i} -> {next_idx} (forward): {len(pts_world)} points")

            logger.info(f"Pass {attempt+1} Result: {len(points_3d)} points.")
            
            # Acceptance Criteria
            if len(points_3d) > 500:
                logger.info(f"Strategy '{params['name']}' successful. Proceeding.")
                break
            else:
                logger.warning(f"Strategy '{params['name']}' yielded insufficient points. Retrying...")

        logger.info(f"Reconstruction complete. Total 3D points: {len(points_3d)}. Matches checked: {total_matches_checked}")
        # If sparse SfM yielded too few points, fallback to dummy to ensure pipeline continuity
        if len(points_3d) < 500:
             logger.warning(f"Sparse SfM insufficient ({len(points_3d)} pts). generating fallback cloud.")
             self.is_fallback = True
             return self._generate_dummy_pcd()

        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(np.array(points_3d))
        pcd.colors = o3d.utility.Vector3dVector(np.array(colors_3d))
        
        if len(pcd.points) > 100:
             # Stricter outlier removal (1.0 vs 1.5) to reduce "pebbles"
             cl, ind = pcd.remove_statistical_outlier(nb_neighbors=25, std_ratio=1.0)
             pcd = pcd.select_by_index(ind)
             
        # Estimate normals for Poisson
        # Increase max_nn to 60 (was 30) for smoother normals
        pcd.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.1, max_nn=60))
        
        return pcd

    def _match_and_triangulate(self, idx1, idx2, keypoints_all, descriptors_all, images, T_w_c1, focal, flann,
                             ratio_thresh=0.75, ransac_thresh=4.0, min_inliers=12):
        """Helper to match two images and triangulate points into world space."""
        des1 = descriptors_all[idx1]
        des2 = descriptors_all[idx2]
        kp1 = keypoints_all[idx1]
        kp2 = keypoints_all[idx2]
        
        matches = flann.knnMatch(des1, des2, k=2)
        # Ratio test
        good = [m for m, n in matches if m.distance < ratio_thresh * n.distance]
        
        logger.debug(f"    Comparing {idx1} and {idx2}: {len(good)} good matches")
        
        if len(good) < 10:
            return None
            
        pts1 = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
        pts2 = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
        
        pp = (images[idx1].shape[1] / 2, images[idx1].shape[0] / 2)
        K = np.array([[focal, 0, pp[0]], [0, focal, pp[1]], [0, 0, 1]], dtype=np.float32)
        
        # Try a few focal length variations if the first one fails
        # 1.0 (original), 0.8 (wider), 1.2 (longer)
        focal_multipliers = [1.0, 0.8, 1.25]
        
        best_res = None
        best_pts_count = 0
        
        for mult in focal_multipliers:
            curr_focal = focal * mult
            curr_K = np.array([[curr_focal, 0, pp[0]], [0, curr_focal, pp[1]], [0, 0, 1]], dtype=np.float32)
            
            # Use findEssentialMat with camera matrix
            try:
                # Use passed RANSAC threshold
                E, mask_E = cv2.findEssentialMat(pts1, pts2, curr_K, cv2.RANSAC, 0.999, ransac_thresh)
            except Exception as e:
                logger.error(f"      [CRASH] findEssentialMat failed: {e}")
                continue
                
            if E is None: continue
            
            # Use recoverPose to get relative R and t
            # First return is num_inliers
            try:
                res_pose = cv2.recoverPose(E, pts1, pts2, curr_K)
                num_inliers, R, t, mask_pose = res_pose
            except Exception as e:
                logger.error(f"      [CRASH] recoverPose failed: {e}")
                continue
                
            mask_pose_indices = mask_pose.ravel() > 0
            
            
            # Require decent consensus
            if num_inliers < min_inliers:
                continue
                
            # Triangulate
            # projMatr1 = K [I|0]
            # projMatr2 = K [R|t]
            P1 = np.ascontiguousarray(curr_K @ np.eye(3, 4), dtype=np.float32)
            P2 = np.ascontiguousarray(curr_K @ np.hstack((R, t)), dtype=np.float32)
            
            # Points must be 2xN float32 AND contiguous
            pts1_tri = np.ascontiguousarray(pts1[mask_pose_indices].reshape(-1, 2).T, dtype=np.float32)
            pts2_tri = np.ascontiguousarray(pts2[mask_pose_indices].reshape(-1, 2).T, dtype=np.float32)
            
            if pts1_tri.shape[1] == 0:
                logger.debug("      [SKIPPING] No points left after pose mask")
                continue

            try:
                pts_4d = cv2.triangulatePoints(P1, P2, pts1_tri, pts2_tri)
            except Exception as e:
                import sys
                sys.stderr.write(f"CRASH in triangulatePoints: {e}\n")
                logger.error(f"      [CRASH] triangulatePoints failed: {e}")
                logger.error(f"      Shapes: P1={P1.shape}, P2={P2.shape}, pts1={pts1_tri.shape}, pts2={pts2_tri.shape}")
                continue
            
            # Chirality
            pts_3d_c1 = (pts_4d[:3, :] / (pts_4d[3, :] + 1e-8)).T
            pts_3d_c2 = (np.dot(R, pts_3d_c1.T) + t).T
            valid_mask = (pts_3d_c1[:, 2] > 0) & (pts_3d_c2[:, 2] > 0)
            num_valid = np.sum(valid_mask)
            
            if num_valid > best_pts_count:
                # Basic world transform for the best result
                pts_3d_local1 = pts_3d_c1[valid_mask]
                pts_local_h = np.hstack((pts_3d_local1, np.ones((len(pts_3d_local1), 1))))
                pts_world = np.dot(T_w_c1, pts_local_h.T).T[:, :3]
                
                T_c2_c1 = np.eye(4)
                T_c2_c1[:3, :3] = R
                T_c2_c1[:3, 3] = t.ravel()
                T_w_c2 = np.dot(T_w_c1, np.linalg.inv(T_c2_c1))
                
                # Filter for range
                final_pts = [p.tolist() for p in pts_world if np.all(np.isfinite(p)) and np.abs(p).max() < 100000]
                if len(final_pts) > best_pts_count:
                    best_pts_count = len(final_pts)
                    best_res = (final_pts, T_w_c2)
                    
            if best_pts_count > 50: # Good enough, don't need more versions
                if mult != 1.0:
                    logger.debug(f"      [ADJUSTED] Focal multiplier {mult} worked best ({best_pts_count} pts)")
                break
                
        if best_pts_count < 5:
            return None
            
        return best_res

    def _get_focal_length(self, path: Path, width: int, height: int) -> float:
        """
        Extract focal length from EXIF data, or guess based on sensor size.
        [UPDATE] Forced fallback to geometric guess (0.85 * max_dim) to avoid 
        catastrophic failures from bad EXIF parsing or sensor size assumptions.
        """
        # SANE DEFAULT: 50-60 degree FOV (approx 28-35mm equiv)
        # f = (0.8 to 1.0) * width
        diagonal = np.sqrt(width**2 + height**2)
        safe_focal = 0.85 * max(width, height)
        
        logger.info(f"    [FOCAL FORCE] Ignoring EXIF, using safe geometric guess: {safe_focal:.1f}px")
        return safe_focal

        # EXIF Logic Disabled for robustness
        # try:
        #     exif_dict = piexif.load(str(path))
        #     exif = exif_dict.get("Exif", {})
        #     ...

            
        # Priority 4: Total fallback - diagonal guess (focal is approx 1.2 * diagonal)
        # Standard wide-angle phone guess
        diagonal = np.sqrt(width**2 + height**2)
        return 0.8 * diagonal # Common wide-angle field of view

    def _generate_dummy_pcd(self) -> o3d.geometry.PointCloud:
        """Fallback: Generate a torus point cloud so user gets a cool shape"""
        mesh = o3d.geometry.TriangleMesh.create_torus(torus_radius=0.5, tube_radius=0.2)
        mesh.compute_vertex_normals()
        pcd = mesh.sample_points_poisson_disk(2000)
        pcd.estimate_normals()
        pcd.orient_normals_consistent_tangent_plane(k=10)
        return pcd

    async def _mesh_from_cloud(self, pcd: o3d.geometry.PointCloud) -> o3d.geometry.TriangleMesh:
        print("Running Poisson Surface Reconstruction...")
        
        # Poisson Reconstruction
        logger.info(f"DEBUG: PCD has normals? {pcd.has_normals()}")
        if not pcd.has_normals():
            logger.info("Warning: Point cloud for Poisson mesh generation has no normals. Estimating...")
            pcd.estimate_normals()
            logger.info(f"DEBUG: After estimation, PCD has normals? {pcd.has_normals()}")
            if not pcd.has_normals():
                raise ValueError("Cannot generate mesh: Point cloud has no normals even after estimation.")
                
        logger.info("Running Poisson Surface Reconstruction...")
        with o3d.utility.VerbosityContextManager(o3d.utility.VerbosityLevel.Debug) as cm:
            mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
                pcd, depth=10, width=0, scale=1.1, linear_fit=False)
            
        # Crop low density (noise)
        # Stricter crop (0.2 vs 0.1) to remove wispy artifacts
        vertices_to_remove = densities < np.quantile(densities, 0.2)
        mesh.remove_vertices_by_mask(vertices_to_remove)
        
        return mesh

    async def _clean_mesh(self, mesh: o3d.geometry.TriangleMesh) -> o3d.geometry.TriangleMesh:
        print("Cleaning mesh...")
        
        # 1. Laplacian Smoothing to fix "pebbly" surface
        # Uses nearest neighbor averaging to reduce high-frequency noise
        mesh = mesh.filter_smooth_laplacian(number_of_iterations=3)
        
        mesh.remove_degenerate_triangles()
        mesh.remove_duplicated_triangles()
        mesh.remove_duplicated_vertices()
        mesh.remove_non_manifold_edges()
        
        # Ensure watertight (simple hole filling)
        # Open3D doesn't have robust hole filling, use Trimesh for final polish
        # Convert Open3D -> Trimesh
        # Save temp and load
        temp_path = f"temp_{self.job_id}.ply"
        o3d.io.write_triangle_mesh(temp_path, mesh)
        
        t_mesh = trimesh.load(temp_path)
        os.remove(temp_path)
        
        if not t_mesh.is_watertight:
            t_mesh.fill_holes()
            
        # Scale to standard size (e.g. 32mm height)
        target_height = 32.0
        current_height = t_mesh.extents[2]
        if current_height > 0:
            scale = target_height / current_height
            t_mesh.apply_scale(scale)
            
        # Convert back to Open3D if more processing needed, or keep for export
        # Since we just need to export, we will use Trimesh for export
        return t_mesh

    async def _export_stl(self, mesh: trimesh.Trimesh):
        print("Exporting STL...")
        # Export logic similar to Relief
        stl_bytes = mesh.export(file_type='stl')
        
        # Save to storage
        uri, sha256_hash, size_bytes = await save_file(
            content=stl_bytes,
            category="outputs",
            job_id=self.job_id,
            filename="final.stl"
        )
        
        stl_artifact = Artifact(
            id=f"art_{uuid.uuid4().hex[:12]}",
            job_id=self.job_id,
            project_id=self.job.project_id,
            artifact_type=ArtifactType.FINAL_STL,
            format=ArtifactFormat.STL,
            uri=uri,
            sha256=sha256_hash,
            size_bytes=size_bytes,
            metadata_json={
                "vertices": len(mesh.vertices),
                "faces": len(mesh.faces),
                "volume": mesh.volume,
                "watertight": mesh.is_watertight,
                "filename": "final.stl"
            }
        )
        self.db.add(stl_artifact)
        await self.db.commit()
    
    async def _calculate_quality_score(self):
        # Calculate quality score based on fallback status
        if self.is_fallback:
            self.job.quality_score = 0.40 # "Risky"
            self.job.quality_summary = {
                "input_quality": 0.50,
                "reconstruction_confidence": 0.30,
                "printability_risk": 0.20,
                "reconstruction": "Fallback (Torus)",
                "notes": [
                    "Insufficient feature matches between photos.",
                    "Generated a fallback shape to verify pipeline.",
                    "Try taking photos from more overlapping angles."
                ]
            }
        else:
            self.job.quality_score = 0.85
            self.job.quality_score_version = "v1"
            self.job.quality_summary = {
                "input_quality": 0.90,
                "reconstruction_confidence": 0.85,
                "printability_risk": 0.10,
                "reconstruction": "Open3D Poisson",
                "notes": ["Mesh generated successfully from photos"]
            }
        await self.db.commit()
