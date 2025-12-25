import cv2
import numpy as np
import os
import sys
from pathlib import Path

# Paths to two benchmark images
IMG_DIR = Path(__file__).parent.parent / "validation_photos" / "sceaux_castle"
IMAGES = sorted(list(IMG_DIR.glob("*.jpg")))[:2]

if len(IMAGES) < 2:
    print("Not enough images found in sceaux_castle dir")
    exit()

def log(msg):
    print(msg)
    sys.stdout.flush()

def run_test():
    img1 = cv2.imread(str(IMAGES[0]))
    img2 = cv2.imread(str(IMAGES[1]))
    
    log(f"Loaded Img1: {img1.shape}")
    
    # 1. Features
    sift = cv2.SIFT_create(nfeatures=20000, contrastThreshold=0.005, edgeThreshold=20)
    kp1, des1 = sift.detectAndCompute(img1, None)
    kp2, des2 = sift.detectAndCompute(img2, None)
    log(f"Keypoints: {len(kp1)} vs {len(kp2)}")
    
    # 2. Match
    flann = cv2.FlannBasedMatcher({'algorithm': 1, 'trees': 5}, {'checks': 50})
    matches = flann.knnMatch(des1, des2, k=2)
    good = [m for m, n in matches if m.distance < 0.9 * n.distance]
    log(f"Good matches: {len(good)}")
    
    # Original shape (N, 1, 2)
    pts1 = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    pts2 = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    
    log(f"Pts1 shape raw: {pts1.shape}")
    
    # 3. Geometry
    h, w = img1.shape[:2]
    focal = 0.85 * max(w, h)
    pp = (w / 2, h / 2)
    K = np.array([[focal, 0, pp[0]], [0, focal, pp[1]], [0, 0, 1]], dtype=np.float32)
    
    log("Finding Essential Mat...")
    E, mask_E = cv2.findEssentialMat(pts1, pts2, K, cv2.RANSAC, 0.999, 1.0)
    
    if E is None:
        log("Essential Mat failed")
        return

    log(f"Recovering Pose... E shape: {E.shape}, dtype: {E.dtype}")
    
    # Try passing (N, 2)
    pts1_flat = pts1.reshape(-1, 2)
    pts2_flat = pts2.reshape(-1, 2)
    
    num_inliers, R, t, mask_pose = cv2.recoverPose(E, pts1_flat, pts2_flat, K)
    log(f"RecoverPose Inliers: {num_inliers}")
    
    unique_vals = np.unique(mask_pose)
    log(f"Mask values: {unique_vals}")
    
    # RELAXED CHECK: > 0 instead of == 1
    mask_pose_indices = mask_pose.ravel() > 0
    
    # Prepare for Triangulation
    P1 = K @ np.eye(3, 4)
    P2 = K @ np.hstack((R, t))
    
    # Ensure Contiguous and Float32
    P1 = np.ascontiguousarray(P1, dtype=np.float32)
    P2 = np.ascontiguousarray(P2, dtype=np.float32)
    
    # Filter points
    pts1_valid = pts1_flat[mask_pose_indices]
    pts2_valid = pts2_flat[mask_pose_indices]
    log(f"Valid points after pose mask: {len(pts1_valid)}")
    
    if len(pts1_valid) == 0:
        log("No points left.")
        return

    # Triangulate expects (2, N)
    pts1_tri = np.ascontiguousarray(pts1_valid.T, dtype=np.float32)
    pts2_tri = np.ascontiguousarray(pts2_valid.T, dtype=np.float32)
    
    log(f"Triangulating... P1 safe: {P1.flags['C_CONTIGUOUS']}, P2 safe: {P2.flags['C_CONTIGUOUS']}")
    log(f"pts1_tri shape: {pts1_tri.shape}, safe: {pts1_tri.flags['C_CONTIGUOUS']}")
    
    try:
        pts_4d = cv2.triangulatePoints(P1, P2, pts1_tri, pts2_tri)
        log("Triangulation Success!")
        
        pts_3d = pts_4d[:3] / pts_4d[3]
        log(f"First 3D point: {pts_3d[:, 0]}")
    except Exception as e:
        log(f"Triangulation CRASH: {e}")

if __name__ == "__main__":
    run_test()
