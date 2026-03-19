#!/usr/bin/env python3
"""Quick endpoint probe for the Code Quality API.

Usage:
  python app/api/scripts/check_endpoints.py \
    --base-url http://code-quality-alb-1526530698.eu-central-1.elb.amazonaws.com \
    --api-key "$API_KEY"
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass
class EndpointCheck:
    name: str
    method: str
    path: str
    expected_statuses: tuple[int, ...]
    json_body: dict[str, Any] | None = None


def request_json(
    base_url: str,
    api_key: str,
    check: EndpointCheck,
    timeout: int,
) -> tuple[int | None, str]:
    url = f"{base_url.rstrip('/')}{check.path}"
    body = None
    headers: dict[str, str] = {
        "Accept": "application/json",
    }

    if check.path.startswith("/api/"):
        headers["x-api-key"] = api_key

    if check.json_body is not None:
        body = json.dumps(check.json_body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url=url, data=body, method=check.method, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status = response.getcode()
            text = response.read().decode("utf-8", errors="replace")
            return status, text[:300]
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        return exc.code, text[:300]
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Check key API endpoints quickly.")
    parser.add_argument("--base-url", required=True, help="API base URL, e.g. http://localhost:8000")
    parser.add_argument("--api-key", required=True, help="API key for x-api-key")
    parser.add_argument("--timeout", type=int, default=15, help="Request timeout in seconds (default: 15)")
    args = parser.parse_args()

    checks = [
        EndpointCheck("Health", "GET", "/health", (200,)),
        EndpointCheck("List jobs", "GET", "/api/v1/jobs", (200,)),
        EndpointCheck("Get upload URL", "POST", "/api/v1/jobs/upload-url", (200,), {"filename": "probe.zip"}),
        EndpointCheck(
            "Create job validation",
            "POST",
            "/api/v1/jobs",
            (400,),
            {"auto_repair": True},
        ),
        EndpointCheck("Get status (missing)", "GET", "/api/v1/jobs/job_nonexistent", (404,)),
        EndpointCheck("Get results (missing)", "GET", "/api/v1/jobs/job_nonexistent/results", (404, 409)),
        EndpointCheck("Get artifacts (missing)", "GET", "/api/v1/jobs/job_nonexistent/artifacts", (404,)),
        EndpointCheck(
            "Download artifact (missing)",
            "GET",
            "/api/v1/jobs/job_nonexistent/artifacts/1/download",
            (404,),
        ),
        EndpointCheck(
            "Trigger repair (missing)",
            "POST",
            "/api/v1/jobs/job_nonexistent/repair",
            (404, 409),
        ),
        EndpointCheck("Delete job (missing)", "DELETE", "/api/v1/jobs/job_nonexistent", (204, 404)),
        EndpointCheck(
            "Source archive (missing)",
            "GET",
            "/api/v1/jobs/job_nonexistent/source/archive?phase=before",
            (404,),
        ),
        EndpointCheck(
            "Source file (missing)",
            "GET",
            "/api/v1/jobs/job_nonexistent/source?file=/tmp/nope.py&phase=before",
            (404, 403),
        ),
    ]

    total = len(checks)
    passed = 0

    print(f"Probing {total} endpoints against {args.base_url} ...")
    for check in checks:
        status, preview = request_json(
            base_url=args.base_url,
            api_key=args.api_key,
            check=check,
            timeout=args.timeout,
        )

        if status is None:
            print(f"[FAIL] {check.name}: request error -> {preview}")
            continue

        if status in check.expected_statuses:
            passed += 1
            print(f"[PASS] {check.name}: status={status}")
        else:
            print(
                f"[FAIL] {check.name}: status={status}, expected={check.expected_statuses}, body={preview}"
            )

    print(f"\nSummary: {passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
