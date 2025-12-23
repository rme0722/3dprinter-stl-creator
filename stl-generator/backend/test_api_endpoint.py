"""
Test the actual API endpoints with timeout handling.
"""
import requests
import time

BASE_URL = "http://localhost:8001/api/v1"

def test_with_timeout(name, method, url, timeout=5, **kwargs):
    """Test an API endpoint with timeout."""
    print(f"\n[TEST] {name}...")
    try:
        start = time.time()
        if method == "GET":
            response = requests.get(url, timeout=timeout, **kwargs)
        elif method == "POST":
            response = requests.post(url, timeout=timeout, **kwargs)
        elapsed = time.time() - start
        
        if response.status_code < 400:
            print(f"  ✓ PASSED - Status {response.status_code} in {elapsed:.2f}s")
            return response
        else:
            print(f"  ✗ FAILED - Status {response.status_code}: {response.text[:100]}")
            return None
    except requests.exceptions.Timeout:
        print(f"  ✗ FAILED - Timed out after {timeout}s")
        return None
    except requests.exceptions.ConnectionError as e:
        print(f"  ✗ FAILED - Connection error: {e}")
        return None

def main():
    print("=" * 60)
    print("API ENDPOINT TESTS")
    print("=" * 60)
    
    # Test 1: Health check
    test_with_timeout("Health check", "GET", f"{BASE_URL}/../health")
    
    # Test 2: List projects
    test_with_timeout("List projects", "GET", f"{BASE_URL}/projects")
    
    # Test 3: Create project (THE KEY TEST)
    response = test_with_timeout(
        "Create project",
        "POST",
        f"{BASE_URL}/projects",
        json={"name": "API Test Project", "description": "Testing API"}
    )
    
    if response:
        project = response.json()
        project_id = project.get("id")
        print(f"  Created project: {project_id}")
        
        # Test 4: Get project
        test_with_timeout("Get project", "GET", f"{BASE_URL}/projects/{project_id}")
        
        # Test 5: Create job
        job_response = test_with_timeout(
            "Create job",
            "POST",
            f"{BASE_URL}/projects/{project_id}/jobs",
            json={
                "pipeline_type": "RELIEF",
                "printer_profile_id": "pp_default_fdm",
                "config": {}
            }
        )
        
        if job_response:
            job = job_response.json()
            print(f"  Created job: {job.get('id')}")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    main()
