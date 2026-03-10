import requests
import json

BASE_URL = "http://localhost:8002"
API_KEY = "default_secret_key"

HEADERS = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

def run_test(name, payload):
    print(f"\n--- Testing: {name} ---")
    try:
        response = requests.post(f"{BASE_URL}/repair", headers=HEADERS, json=payload)
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"Error: {e}")

def test_flat_params():
    payload = {
        "file_path": "app/worker/test_sample.py",
        "line_number": 4,
        "fixed_code": "# Flat fix\nprint('Flat!')"
    }
    run_test("Flat Parameters", payload)

def test_openai_tool_calls_string():
    payload = {
        "tool_calls": [
            {
                "type": "function",
                "function": {
                    "name": "functions.repair_code_issue",
                    "arguments": json.dumps({
                        "file_path": "app/worker/test_sample.py",
                        "line_number": 4,
                        "fixed_code": "# OpenAI String fix\nprint('OpenAI String!')"
                    })
                }
            }
        ]
    }
    run_test("OpenAI Tool Calls (String Arguments)", payload)

def test_openai_tool_calls_dict():
    payload = {
        "tool_calls": [
            {
                "type": "function",
                "function": {
                    "name": "functions.repair_code_issue",
                    "arguments": {
                        "file_path": "app/worker/test_sample.py",
                        "line_number": 4,
                        "fixed_code": "# OpenAI Dict fix\nprint('OpenAI Dict!')"
                    }
                }
            }
        ]
    }
    run_test("OpenAI Tool Calls (Dict Arguments)", payload)

def test_direct_function_wrapper():
    payload = {
        "function": {
            "name": "functions.repair_code_issue",
            "arguments": {
                "file_path": "app/worker/test_sample.py",
                "line_number": 4,
                "fixed_code": "# Direct Function fix\nprint('Direct Function!')"
            }
        }
    }
    run_test("Direct Function Wrapper", payload)

def test_validation_error():
    payload = {
        "file_path": "app/worker/test_sample.py"
        # missing line_number and fixed_code
    }
    run_test("Validation Error (Missing Fields)", payload)

if __name__ == "__main__":
    test_flat_params()
    test_openai_tool_calls_string()
    test_openai_tool_calls_dict()
    test_direct_function_wrapper()
    test_validation_error()
