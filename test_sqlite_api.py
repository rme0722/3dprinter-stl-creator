import requests

print("Testing project creation with SQLite backend...")
try:
    response = requests.post(
        'http://localhost:8000/api/v1/projects',
        json={'name': 'SQLite Test Project', 'description': 'Testing SQLite'},
        timeout=5
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
except requests.exceptions.Timeout:
    print("ERROR: Request timed out after 5 seconds")
except Exception as e:
    print(f"ERROR: {e}")
