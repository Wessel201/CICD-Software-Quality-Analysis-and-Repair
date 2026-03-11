import requests
import json

BASE_URL = "http://localhost:8002"
API_KEY = "default_secret_key"  # Adjust if you changed it in .env

HEADERS = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

def test_analyze():
    print("\n--- Testing /analyze ---")
    payload = {"repo_path": "/src"}
    try:
        response = requests.post(f"{BASE_URL}/analyze", headers=HEADERS, json=payload)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")

def test_repair():
    print("\n--- Testing /repair ---")
    # This should match a real file and line in your /src
    payload = {
        "file_path": "app/worker/test_sample.py",
        "line_number": 4,
        "fixed_code": "# This is the fix\nprint('Fixed!')",
        "repo_path": "/src"
    }
    try:
        response = requests.post(f"{BASE_URL}/repair", headers=HEADERS, json=payload)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")

def test_robustness():
    print("\n--- Testing Robustness (Query Params instead of Body) ---")
    # Sending params in query string instead of JSON body
    query_params = "file_path=app/worker/test_sample.py&line_number=4&fixed_code=QueryFix"
    try:
        response = requests.post(f"{BASE_URL}/repair?{query_params}", headers=HEADERS)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_analyze()
    test_repair()
    test_robustness()
