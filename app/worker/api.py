from fastapi import FastAPI, HTTPException, Security, Depends, Request
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, ConfigDict, ValidationError
from typing import Optional
import os
import json
from main import run_worker
from analyzer import Analyzer
from repairman import Repairman

app = FastAPI(title="QC Worker Extension API")

# Middleware to log incoming requests for debugging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Log basic request info safely
    print(f"DEBUG: {request.method} {request.url}")
    # We avoid reading request.body() here to prevent issues with downstream 
    # route handlers. Body logging is done inside extract_params.
    response = await call_next(request)
    return response

@app.get("/openapi.json")
async def get_openapi_spec():
    from fastapi.openapi.utils import get_openapi
    return get_openapi(
        title=app.title,
        version=app.version,
        routes=app.routes,
    )

API_KEY = os.getenv("WORKER_API_KEY", "default_secret_key")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def get_api_key(api_key: Optional[str] = Security(api_key_header)):
    if api_key == API_KEY:
        return api_key
    print(f"DEBUG: API Key Mismatch. Received: {api_key}, Expected: {API_KEY}")
    raise HTTPException(status_code=403, detail="Could not validate credentials")

# Models for documentation and validation
class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    repo_path: str = "/src"

class RepairRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    file_path: str
    line_number: int
    fixed_code: str
    repo_path: str = "/src"

@app.get("/")
async def root():
    return {"message": "QC Worker API is running"}

@app.post("/")
async def root_post():
    return {
        "error": "Method Not Allowed on root",
        "hint": "You are calling the root URL. Please append '/analyze' or '/repair' to your API endpoint in the UvA Extension settings.",
        "example": "https://your-url.ngrok-free.app/analyze"
    }

async def extract_params(request: Request):
    """Robustly extract params from JSON body, Form data, or Query params."""
    params = {}
    
    # 1. Query Parameters (lowest priority)
    params.update(dict(request.query_params))
    
    # Check content type to decide how to parse body
    content_type = request.headers.get("Content-Type", "")
    
    try:
        raw_body = await request.body()
        content_type = request.headers.get("Content-Type", "")
        print(f"DEBUG: Content-Type: {content_type}")
        if raw_body:
            body_str = raw_body.decode('utf-8', errors='ignore')
            print(f"DEBUG: Raw Body (first 1000 chars): {body_str[:1000]}")
            
            # 2. Try JSON
            try:
                json_data = json.loads(raw_body)
                if isinstance(json_data, dict):
                    # Check for nested tool call formats
                    # 1. Direct flat params (highest priority)
                    if all(k in json_data for k in ["file_path", "line_number", "fixed_code"]):
                        params.update(json_data)
                    # 2. OpenAI-style tool_calls
                    elif "tool_calls" in json_data and isinstance(json_data["tool_calls"], list):
                        for call in json_data["tool_calls"]:
                            if "function" in call and "arguments" in call["function"]:
                                args = call["function"]["arguments"]
                                if isinstance(args, str):
                                    try:
                                        params.update(json.loads(args))
                                    except: pass
                                elif isinstance(args, dict):
                                    params.update(args)
                    # 3. Direct function wrapper
                    elif "function" in json_data and "arguments" in json_data["function"]:
                        args = json_data["function"]["arguments"]
                        if isinstance(args, str):
                            try:
                                params.update(json.loads(args))
                            except: pass
                        elif isinstance(args, dict):
                            params.update(args)
                    else:
                        # Fallback: just merge everything
                        params.update(json_data)
            except json.JSONDecodeError:
                pass
                
            # 3. Try Form Data (if applicable)
            if "form" in content_type:
                try:
                    form_data = await request.form()
                    params.update(dict(form_data))
                except:
                    pass
    except Exception as e:
        print(f"DEBUG: Body extraction error: {e}")
        
    return params

@app.api_route("/analyze", methods=["GET", "POST"])
async def analyze(request: Request, api_key: str = Depends(get_api_key)):
    """
    Runs the full analysis suite. 
    Handles Body, Form, and Query params for max compatibility.
    """
    params = await extract_params(request)
    print(f"DEBUG: Resolved /analyze params: {params}")

    try:
        # Validate using Pydantic
        req_data = AnalysisRequest(**params)
        repo_path = req_data.repo_path or "/src"
        
        print(f"DEBUG: Analyzing path: {repo_path}")
        analyzer = Analyzer(repo_path)
        results = analyzer.run_all()
        return results
    except ValidationError as ve:
        print(f"DEBUG: Validation Error in /analyze: {ve.json()}")
        raise HTTPException(status_code=422, detail=ve.errors())
    except Exception as e:
        print(f"DEBUG: Error in /analyze: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.api_route("/repair", methods=["GET", "POST"])
async def repair(request: Request, api_key: Optional[str] = Depends(get_api_key)):
    """
    Repairs a specific issue using a provided fix.
    Handles Body, Form, and Query params for max compatibility.
    """
    params = await extract_params(request)
    print(f"DEBUG: Resolved /repair params: {params}")

    # Manual validation to avoid framework 422 and provide clear errors
    errors = {}
    if "file_path" not in params or not params["file_path"]:
        errors["file_path"] = "missing or empty"
    if "line_number" not in params:
        errors["line_number"] = "missing"
    else:
        try:
            params["line_number"] = int(params["line_number"])
        except ValueError:
            errors["line_number"] = "must be an integer"
    if "fixed_code" not in params or not params["fixed_code"]:
        errors["fixed_code"] = "missing or empty"

    if errors:
        print(f"DEBUG: Validation failed for /repair: {errors}")
        return {
            "status": "error",
            "error": {
                "type": "BadRequest",
                "message": "Missing or invalid required parameters.",
                "details": errors
            }
        }

    try:
        file_path = params["file_path"]
        line_number = params["line_number"]
        fixed_code = params["fixed_code"]
        repo_path = params.get("repo_path", "/src")

        repairman = Repairman()
        full_path = (
            file_path
            if os.path.isabs(file_path)
            else os.path.join(repo_path, file_path)
        )

        print(f"DEBUG: Repairing snippet in {full_path} at line {line_number}")
        snippet_data = repairman.isolate_snippet(full_path, line_number)
        
        if not snippet_data:
            return {
                "status": "error",
                "file_path": file_path,
                "line_number": line_number,
                "error": {
                    "type": "FileNotFound",
                    "message": f"File or snippet not found at {file_path}:{line_number}",
                    "details": f"Attempted path: {full_path}"
                }
            }

        repairman.apply_fix(
            full_path,
            snippet_data["start_line"],
            snippet_data["end_line"],
            fixed_code,
        )

        return {
            "status": "ok",
            "file_path": file_path,
            "line_number": line_number,
            "applied_region": {
                "start_line": snippet_data["start_line"],
                "end_line": snippet_data["end_line"]
            },
            "summary": f"Successfully applied fix to {file_path} at line {line_number}.",
            "test_results": {
                "tests_run": False,
                "message": "Automatic testing not yet implemented for this project."
            }
        }
    except Exception as e:
        print(f"DEBUG: Error in /repair: {str(e)}")
        return {
            "status": "error",
            "file_path": params.get("file_path"),
            "line_number": params.get("line_number"),
            "error": {
                "type": "WorkerException",
                "message": str(e),
                "details": "Unexpected exception while applying fix."
            }
        }

@app.api_route("/debug", methods=["GET", "POST"])
async def debug_echo(request: Request):
    """Echoes EVERYTHING back for debugging integration."""
    params = await extract_params(request)
    headers = dict(request.headers)
    return {
        "headers": headers,
        "params": params,
        "method": request.method,
        "url": str(request.url),
        "api_key_configured": API_KEY[:3] + "..." if API_KEY else "None"
    }

if __name__ == "__main__":
    import uvicorn
    # Use reload=True for easier dev, and ensure the module name is correct
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
