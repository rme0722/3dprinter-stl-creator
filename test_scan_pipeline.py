import asyncio
import os
import requests
import time
import json
from pathlib import Path

# Config
API_URL = "http://localhost:8000/api/v1"
TEST_DATA_DIR = Path("test_data")

def create_dummy_images():
    """Create a set of dummy images for testing"""
    import cv2
    import numpy as np
    
    if not TEST_DATA_DIR.exists():
        TEST_DATA_DIR.mkdir()
    
    files = []
    print("Generating dummy images...")
    # Create 3 images with some features (circles/rectangles) so feature matching doesn't totally fail
    for i in range(3):
        img = np.zeros((400, 400, 3), dtype=np.uint8)
        # Add random noise/background
        img[:] = np.random.randint(0, 50, (400, 400, 3))
        
        # Draw some common features in all images (shifted slightly)
        shift = i * 5
        cv2.circle(img, (100 + shift, 100), 20, (255, 255, 255), -1)
        cv2.rectangle(img, (200 + shift, 200), (300 + shift, 300), (0, 255, 0), -1)
        cv2.putText(img, "TEST", (50, 350), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        
        path = TEST_DATA_DIR / f"scan_img_{i}.jpg"
        cv2.imwrite(str(path), img)
        files.append(path)
    
    return files

def test_scan_pipeline():
    print("=== Testing Photogrammetry Pipeline ===")
    
    # 1. Create Project
    print("\n1. Creating Project...")
    resp = requests.post(f"{API_URL}/projects/", json={
        "name": "Scan Test Project",
        "description": "Automated test project"
    })
    if resp.status_code not in [200, 201]:
        print(f"Failed to create project: {resp.text}")
        return
    project = resp.json()
    project_id = project['id']
    print(f"   Project created: {project_id}")
    
    # 2. Create Scan Job
    print("\n2. Creating Scan Job...")
    resp = requests.post(f"{API_URL}/projects/{project_id}/jobs", json={
        "pipeline_type": "SCAN",
        "printer_profile_id": "pp_default_fdm"
    })
    if resp.status_code not in [200, 201]:
        print(f"Failed to create job: {resp.text}")
        return
    job = resp.json()
    job_id = job['id']
    print(f"   Job created: {job_id}")
    
    # 3. Upload Images
    print("\n3. Uploading Images...")
    files = create_dummy_images()
    for fpath in files:
        with open(fpath, "rb") as f:
            resp = requests.post(
                f"{API_URL}/uploads/file/{job_id}",
                files={"file": f},
                data={"artifact_type": "RAW_PHOTO"}
            )
            if resp.status_code != 200:
                print(f"Failed to upload {fpath}: {resp.text}")
                return
            print(f"   Uploaded {fpath.name}")
            
    # 4. Submit Job
    print("\n4. Submitting Job...")
    resp = requests.post(f"{API_URL}/jobs/{job_id}/submit")
    if resp.status_code != 200:
        print(f"Failed to submit: {resp.text}")
        return
    print("   Job submitted")
    
    # 5. Poll Status
    print("\n5. Polling Status...")
    start_time = time.time()
    while time.time() - start_time < 60: # 1 minute timeout
        resp = requests.get(f"{API_URL}/jobs/{job_id}")
        job = resp.json()
        state = job['state']
        
        print(f"   Status: {state}")
        
        if state == "SUCCEEDED":
            print("\nSUCCESS! Job completed.")
            break
        elif state == "FAILED":
            print(f"\nFAILED! Job failed with error: {job.get('error_message')}")
            break
            
        time.sleep(2)
    
    # 6. Verify Artifacts
    print("\n6. Verifying Artifacts...")
    resp = requests.get(f"{API_URL}/jobs/{job_id}/artifacts")
    artifacts = resp.json()
    stl_found = False
    for art in artifacts:
        print(f"   Found artifact: {art['artifact_type']} ({art['filename']})")
        if art['artifact_type'] == "FINAL_STL":
            stl_found = True
            
    if stl_found:
        print("\nPASS: Final STL artifact generated.")
    else:
        print("\nFAIL: No STL artifact found.")

if __name__ == "__main__":
    try:
        test_scan_pipeline()
    except Exception as e:
        print(f"\nTest crashed: {e}")
