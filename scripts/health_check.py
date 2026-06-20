#!/usr/bin/env python3
"""
Production Health Check Script
================================
Checks all critical services and dependencies for the AI Outreach Platform.

Usage:
    python scripts/health_check.py
    python scripts/health_check.py --url http://your-server:8000
    python scripts/health_check.py --json          # Machine-readable JSON output

Exit codes:
    0 = All critical services healthy
    1 = One or more critical services are degraded or unreachable
"""

import argparse
import asyncio
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _get(url: str, timeout: float = 8.0) -> tuple[int, dict]:
    """Synchronous HTTP GET with JSON response parsing."""
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read())
        except Exception:
            body = {"error": str(e)}
        return e.code, body
    except urllib.error.URLError as e:
        return 0, {"error": str(e.reason)}
    except Exception as e:
        return 0, {"error": str(e)}


# ─── Check functions ──────────────────────────────────────────────────────────

def check_backend_health(base_url: str) -> dict[str, Any]:
    t0 = time.monotonic()
    status, data = _get(f"{base_url}/health")
    elapsed = round((time.monotonic() - t0) * 1000)

    ok = status == 200 and data.get("status") == "healthy"
    return {
        "name": "Backend API",
        "ok": ok,
        "status_code": status,
        "latency_ms": elapsed,
        "detail": data if not ok else data.get("version", "healthy"),
        "critical": True,
    }


def check_auth_endpoint(base_url: str) -> dict[str, Any]:
    """POST to /api/auth/login with bad creds — expect 401, not 500."""
    t0 = time.monotonic()
    try:
        body = json.dumps({"email": "health@check.local", "password": "invalid"}).encode()
        req = urllib.request.Request(
            f"{base_url}/api/auth/login",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            status = resp.status
    except urllib.error.HTTPError as e:
        status = e.code
    except Exception as e:
        elapsed = round((time.monotonic() - t0) * 1000)
        return {"name": "Auth API", "ok": False, "status_code": 0, "latency_ms": elapsed, "detail": str(e), "critical": True}

    elapsed = round((time.monotonic() - t0) * 1000)
    # 401 = auth works (credential rejected, not server error)
    ok = status in (401, 422)
    return {
        "name": "Auth API",
        "ok": ok,
        "status_code": status,
        "latency_ms": elapsed,
        "detail": "Login endpoint responding correctly" if ok else f"Unexpected status {status}",
        "critical": True,
    }


def check_integrations_health(base_url: str) -> dict[str, Any]:
    """GET /api/integrations/health/all — expects 200 or 401."""
    t0 = time.monotonic()
    status, data = _get(f"{base_url}/api/integrations/health/all")
    elapsed = round((time.monotonic() - t0) * 1000)

    # 403 means route registered but auth required — still OK
    ok = status in (200, 401, 403)
    return {
        "name": "Integrations Health",
        "ok": ok,
        "status_code": status,
        "latency_ms": elapsed,
        "detail": data if not ok else "Endpoint registered",
        "critical": False,
    }


def check_openapi_spec(base_url: str) -> dict[str, Any]:
    """Verify the OpenAPI spec is reachable and has expected paths."""
    t0 = time.monotonic()
    status, data = _get(f"{base_url}/openapi.json")
    elapsed = round((time.monotonic() - t0) * 1000)

    if status != 200:
        return {"name": "OpenAPI Spec", "ok": False, "status_code": status, "latency_ms": elapsed, "detail": "Could not load spec", "critical": False}

    paths = list(data.get("paths", {}).keys())
    expected = ["/api/auth/login", "/api/campaigns", "/api/leads", "/api/outreach-tracker"]
    missing = [p for p in expected if p not in paths]

    ok = len(missing) == 0
    return {
        "name": "OpenAPI Spec",
        "ok": ok,
        "status_code": status,
        "latency_ms": elapsed,
        "detail": f"{len(paths)} routes registered" if ok else f"Missing routes: {missing}",
        "critical": False,
    }


def check_frontend(frontend_url: str) -> dict[str, Any]:
    t0 = time.monotonic()
    status, _ = _get(frontend_url)
    elapsed = round((time.monotonic() - t0) * 1000)
    ok = status in (200, 304)
    return {
        "name": "Frontend (Next.js)",
        "ok": ok,
        "status_code": status,
        "latency_ms": elapsed,
        "detail": "Responding" if ok else f"Status {status}",
        "critical": False,
    }


def check_env_vars() -> dict[str, Any]:
    required = ["MONGODB_URL", "JWT_SECRET"]
    recommended = ["GROQ_API_KEY", "GROQ_MODEL", "COOKIE_ENCRYPTION_KEY"]
    
    missing_required = [v for v in required if not os.environ.get(v)]
    missing_recommended = [v for v in recommended if not os.environ.get(v)]
    
    ok = len(missing_required) == 0
    detail_parts = []
    if missing_required:
        detail_parts.append(f"MISSING REQUIRED: {', '.join(missing_required)}")
    if missing_recommended:
        detail_parts.append(f"Missing recommended: {', '.join(missing_recommended)}")
    if ok and not missing_recommended:
        detail_parts.append("All environment variables present")

    return {
        "name": "Environment Variables",
        "ok": ok,
        "status_code": 0,
        "latency_ms": 0,
        "detail": " | ".join(detail_parts) or "OK",
        "critical": True,
    }


# ─── Report rendering ─────────────────────────────────────────────────────────

PASS = "\033[92m✓\033[0m"  # green
FAIL = "\033[91m✗\033[0m"  # red
WARN = "\033[93m⚠\033[0m"  # yellow
BOLD = "\033[1m"
RESET = "\033[0m"


def render_text(results: list[dict], total_ms: float) -> None:
    print(f"\n{BOLD}AI Outreach Platform — Health Check{RESET}")
    print(f"  Timestamp : {datetime.now(timezone.utc).isoformat()}")
    print(f"  Duration  : {round(total_ms)}ms\n")
    print(f"  {'Service':<35} {'Status':<10} {'HTTP':<6} {'Latency'}")
    print("  " + "─" * 65)

    for r in results:
        icon = PASS if r["ok"] else (FAIL if r["critical"] else WARN)
        status_label = "OK" if r["ok"] else ("CRITICAL" if r["critical"] else "DEGRADED")
        http_label = str(r["status_code"]) if r["status_code"] else "—"
        lat_label = f"{r['latency_ms']}ms" if r["latency_ms"] else "—"
        print(f"  {icon} {r['name']:<33} {status_label:<10} {http_label:<6} {lat_label}")
        if not r["ok"]:
            print(f"    └─ {r['detail']}")

    print()
    critical_failures = [r for r in results if not r["ok"] and r["critical"]]
    if critical_failures:
        print(f"  {FAIL} {len(critical_failures)} critical service(s) FAILED. Platform may be degraded.\n")
    else:
        non_critical = [r for r in results if not r["ok"]]
        if non_critical:
            print(f"  {WARN} {len(non_critical)} non-critical service(s) degraded. Core platform healthy.\n")
        else:
            print(f"  {PASS} All services healthy.\n")


def render_json(results: list[dict], total_ms: float) -> None:
    overall_ok = all(r["ok"] for r in results if r["critical"])
    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall_ok": overall_ok,
        "duration_ms": round(total_ms),
        "checks": results,
    }
    print(json.dumps(output, indent=2))


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="AI Outreach Platform health check")
    parser.add_argument("--url", default="http://localhost:8000", help="Backend base URL (default: http://localhost:8000)")
    parser.add_argument("--frontend-url", default="http://localhost:3000", help="Frontend URL")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Output machine-readable JSON")
    parser.add_argument("--no-env", action="store_true", help="Skip environment variable checks (for CI)")
    args = parser.parse_args()

    t0 = time.monotonic()

    checks = [
        lambda: check_backend_health(args.url),
        lambda: check_auth_endpoint(args.url),
        lambda: check_integrations_health(args.url),
        lambda: check_openapi_spec(args.url),
        lambda: check_frontend(args.frontend_url),
    ]
    if not args.no_env:
        checks.append(check_env_vars)

    results = [c() for c in checks]
    total_ms = (time.monotonic() - t0) * 1000

    if args.json_output:
        render_json(results, total_ms)
    else:
        render_text(results, total_ms)

    # Exit 1 if any critical check failed
    critical_ok = all(r["ok"] for r in results if r["critical"])
    return 0 if critical_ok else 1


if __name__ == "__main__":
    sys.exit(main())
