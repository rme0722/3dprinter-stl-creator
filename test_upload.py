#!/usr/bin/env python3
"""
Quick test script to debug the 422 upload error.
"""
import requests
import json

# Test the upload endpoint directly
def test_upload():
    # First, create a test job
    print("1. Creating test project...")
    project_data = {"name": "Test Project", "description": "Debug upload"}
    resp = requests.post("http://localhost:8000/api/v1/projects/", json=project_data)
    print(f"Project response: {resp.status_code}")
    if resp.status_code != 201:
        print(f"Error: {resp.text}")
        return
    
    project = resp.json()
    project_id = project["id"]
    print(f"Created project: {project_id}")
    
    print("2. Creating test job...")
    job_data = {
        "pipeline_type": "RELIEF",
        "printer_profile_id": "pp_default_fdm"  # Use the actual ID from init_db.py
    }
    
    # First check what printer profiles exist
    print("Checking available printer profiles...")
    profiles_resp = requests.get("http://localhost:8000/api/v1/printer-profiles")
    if profiles_resp.status_code == 404:
        print("No printer profiles endpoint - using hardcoded ID")
    else:
        print(f"Profiles response: {profiles_resp.status_code} - {profiles_resp.text}")
        if profiles_resp.status_code == 200:
            profiles = profiles_resp.json()
            if profiles:
                job_data["printer_profile_id"] = profiles[0]["id"]
                print(f"Using profile: {profiles[0]['id']}")
    
    resp = requests.post(f"http://localhost:8000/api/v1/projects/{project_id}/jobs", json=job_data)
    print(f"Job response: {resp.status_code}")
    if resp.status_code != 201:
        print(f"Error: {resp.text}")
        return
    
    job = resp.json()
    job_id = job["id"]
    print(f"Created job: {job_id}")
    
    print("3. Testing file upload...")
    # Create a small test file
    test_content = b"fake image content for testing"
    files = {"file": ("test.jpg", test_content, "image/jpeg")}
    data = {"artifact_type": "RAW_IMAGE"}
    
    # Test the exact same endpoint the frontend uses
    print("Testing via Next.js proxy route...")
    resp = requests.post(f"http://localhost:3000/api/v1/uploads/file/{job_id}", files=files, data=data)
    print(f"Frontend proxy response: {resp.status_code}")
    print(f"Response body: {resp.text}")
    
    if resp.status_code == 422:
        try:
            error_detail = resp.json()
            print(f"Frontend validation error: {json.dumps(error_detail, indent=2)}")
        except:
            print("Could not parse error JSON")
    
    print("\nTesting direct backend...")
    resp = requests.post(f"http://localhost:8000/api/v1/uploads/file/{job_id}", files=files, data=data)
    print(f"Direct backend response: {resp.status_code}")
    print(f"Response body: {resp.text}")
    
    print("\n4. Testing job submission...")
    submit_resp = requests.post(f"http://localhost:8000/api/v1/jobs/{job_id}/submit")
    print(f"Job submit response: {submit_resp.status_code}")
    print(f"Submit response body: {submit_resp.text}")
    
    if submit_resp.status_code == 422:
        try:
            error_detail = submit_resp.json()
            print(f"Job submit validation error: {json.dumps(error_detail, indent=2)}")
        except:
            print("Could not parse submit error JSON")

if __name__ == "__main__":
    test_upload()
