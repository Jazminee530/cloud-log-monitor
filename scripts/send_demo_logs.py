"""Submit synthetic sample events; safe to share publicly on GitHub."""

import json
import os
from urllib.request import Request, urlopen
from uuid import uuid4

BASE_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

sample_events = [
    {"source": "demo-web", "level": "INFO", "message": "Routine health check passed"},
    {"source": "demo-auth", "level": "WARNING", "message": "Failed login for user demo_user"},
    {"source": "demo-app", "level": "ERROR", "message": "Permission denied while reading configuration"},
    {"source": "demo-db", "level": "ERROR", "message": "Connection refused when contacting database"},
]

for event in sample_events:
    event["event_id"] = str(uuid4())
    request = Request(
        f"{BASE_URL}/logs",
        data=json.dumps(event).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        print(response.status, json.loads(response.read()))

print(f"\nView logs: {BASE_URL}/logs")
print(f"View alerts: {BASE_URL}/alerts (may take a few seconds)")
