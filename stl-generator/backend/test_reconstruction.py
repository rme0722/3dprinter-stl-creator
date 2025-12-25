import cv2
import numpy as np
import os
from pathlib import Path

# Paths to two benchmark images
IMG_DIR = Path(__file__).parent.parent / "validation_photos" / "sceaux_castle"
IMAGES = sorted(list(IMG_DIR.glob("*.jpg")))[:2]

if len(IMAGES) < 2:
    print("Not enough images found in sceaux_castle dir")
    exit()

def run_test():
    img1 = cv2.imread(str(IMAGES[0]))
    img2 = cv2.imread(str(IMAGES[1]))
    
    print(f"Loaded Img1: {img1.shape}")
    print(f"Loaded Img2: {img2.shape}")
    
    # 1. Features
    sift = cv2.SIFT_create(nfeatures=20000, contrastThreshold=0.005, edgeThreshold=20)
    kp1, des1 = sift.detectAndCompute(img1, None)
    kp2, des2 = sift.detectAndCompute(img2, None)
    print(f"Keypoints: {len(kp1)} vs {len(kp2)}")
    
    # 2. Match
    flann = cv2.FlannBasedMatcher({'algorithm': 1, 'trees': 5}, {'checks': 50})
    matches = flann.knnMatch(des1, des2, k=2)
    good = [m for m, n in matches if m.distance < 0.9 * n.distance]
    print(f"Good matches: {len(good)}")
    
    pts1 = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    pts2 = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    
    print(f"Pts1 shape: {pts1.shape}")
    
    # 3. Geometry
    h, w = img1.shape[:2]
    # Geometric guess
    focal = 0.85 * max(w, h)
    pp = (w / 2, h / 2)
    K = np.array([[focal, 0, pp[0]], [0, focal, pp[1]], [0, 0, 1]], dtype=np.float32)
    
    print(f"K:\n{K}")
    
    # Essential Matrix
    E, mask_E = cv2.findEssentialMat(pts1, pts2, K, cv2.RANSAC, 0.999, 1.0) # Standard threshold
    print(f"E found? {E is not None}")
    if E is not None:
        print(f"Mask_E inliers: {np.sum(mask_E)}")

        # Recover Pose
        num_inliers, R, t, mask_pose = cv2.recoverPose(E, pts1, pts2, K)
        print(f"RecoverPose Inliers: {num_inliers}")
        
        # Test triangulation inputs
        mask_pose_indices = mask_pose.ravel() == 1
        
        pts1_tri = pts1[mask_pose_indices].reshape(-1, 2).T
        pts2_tri = pts2[mask_pose_indices].reshape(-1, 2).T
        
        print(f"Triangulation Input Shapes: {pts1_tri.shape}, {pts2_tri.shape}")
        
        P1 = np.ascontiguousarray(K @ np.eye(3, 4), dtype=np.float32)
        P2 = np.ascontiguousarray(K @ np.hstack((R, t)), dtype=np.float32)
        
        # Points must be 2xN float32 AND contiguous
        pts1_tri = np.ascontiguousarray(pts1[mask_pose_indices].reshape(-1, 2).T, dtype=np.float32)
        pts2_tri = np.ascontiguousarray(pts2[mask_pose_indices].reshape(-1, 2).T, dtype=np.float32)
        
        try:
            pts_4d = cv2.triangulatePoints(P1, P2, pts1_tri, pts2_tri)
            print("Triangulation Success!")
            
            pts_3d = pts_4d[:3] / pts_4d[3]
            print(f"First 3D point: {pts_3d[:, 0]}")
        except Exception as e:
            print(f"Triangulation CRASH: {e}")

if __name__ == "__main__":
    run_test()
