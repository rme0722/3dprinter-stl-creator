import httpx
import json

base_url = "http://localhost:8000/api/v1/projects/proj_60f1044d395f/jobs"

resp = httpx.get(base_url)
jobs = resp.json()
latest_job = jobs[-1]
print(json.dumps(latest_job, indent=2))
