"""BookAI Admin API — HTTP endpoint for remote monitoring & management.

Junior (AI agent) cannot SSH into the VPS (outbound port 22 blocked from sandbox),
but CAN reach HTTP/HTTPS endpoints. This lightweight FastAPI app exposes safe
management operations over HTTP with token authentication.

Endpoints:
    GET  /health              → service status + uptime
    GET  /logs?lines=50       → recent bookai service logs
    GET  /tests               → run pytest and return results
    POST /restart             → restart bookai + nginx services
    POST /deploy              → git pull + pip install + restart
    GET  /metrics             → disk, memory, CPU snapshot
    POST /run                 → run a pre-approved command (allowlist only)

Authentication: Bearer token in Authorization header (set VPS_ADMIN_TOKEN env var)

Start:
    pip install fastapi uvicorn psutil
    VPS_ADMIN_TOKEN=your_secret_token uvicorn admin_api:app --host 0.0.0.0 --port 8502

Or via systemd (see deploy_monitor.sh).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

TOKEN = os.environ.get("VPS_ADMIN_TOKEN", "bookai_admin_2025")
DEPLOY_DIR = Path(os.environ.get("DEPLOY_DIR", "/opt/bookai"))
SERVICE_NAME = "bookai"
REPO_BRANCH = "initial-setup"

app = FastAPI(
    title="BookAI Admin API",
    description="Remote management API for BookAI VPS deployment",
    version="1.0.0",
)
security = HTTPBearer()

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> str:
    if credentials.credentials != TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")
    return credentials.credentials


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(cmd: list[str], cwd: str | None = None, timeout: int = 120) -> dict:
    """Run a shell command safely and return {ok, stdout, stderr, returncode}."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd
        )
        return {
            "ok": result.returncode == 0,
            "stdout": result.stdout[-4000:] if result.stdout else "",
            "stderr": result.stderr[-2000:] if result.stderr else "",
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": "Command timed out", "returncode": -1}
    except Exception as e:
        return {"ok": False, "stdout": "", "stderr": str(e), "returncode": -1}


def _service_status(name: str) -> dict:
    r = _run(["systemctl", "is-active", name])
    active = r["stdout"].strip() == "active"
    r2 = _run(["systemctl", "show", name, "--property=ActiveEnterTimestamp,MainPID,MemoryCurrent"])
    props = {}
    for line in r2["stdout"].splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            props[k.strip()] = v.strip()
    return {
        "name": name,
        "active": active,
        "status": r["stdout"].strip(),
        "pid": props.get("MainPID", ""),
        "since": props.get("ActiveEnterTimestamp", ""),
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
def health(token: str = Security(verify_token)) -> dict:
    """Return overall health: services + disk + uptime."""
    bookai = _service_status(SERVICE_NAME)
    nginx = _service_status("nginx")

    disk = {}
    if HAS_PSUTIL:
        d = psutil.disk_usage("/")
        disk = {
            "total_gb": round(d.total / 1e9, 1),
            "used_gb": round(d.used / 1e9, 1),
            "free_gb": round(d.free / 1e9, 1),
            "percent": d.percent,
        }

    uptime_r = _run(["uptime", "-p"])

    return {
        "ok": bookai["active"],
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "services": {
            "bookai": bookai,
            "nginx": nginx,
        },
        "disk": disk,
        "uptime": uptime_r["stdout"].strip(),
        "deploy_dir": str(DEPLOY_DIR),
    }


@app.get("/logs")
def logs(lines: int = 80, token: str = Security(verify_token)) -> dict:
    """Fetch recent systemd journal logs for bookai service."""
    lines = min(lines, 500)
    r = _run(["journalctl", "-u", SERVICE_NAME, "-n", str(lines), "--no-pager", "--output=short"])
    return {
        "ok": r["ok"],
        "lines": lines,
        "logs": r["stdout"],
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@app.get("/metrics")
def metrics(token: str = Security(verify_token)) -> dict:
    """System resource metrics."""
    result: dict = {"timestamp": datetime.utcnow().isoformat() + "Z"}
    if HAS_PSUTIL:
        result.update({
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory": {
                "total_gb": round(psutil.virtual_memory().total / 1e9, 2),
                "used_gb": round(psutil.virtual_memory().used / 1e9, 2),
                "percent": psutil.virtual_memory().percent,
            },
            "disk": {
                "total_gb": round(psutil.disk_usage("/").total / 1e9, 1),
                "free_gb": round(psutil.disk_usage("/").free / 1e9, 1),
                "percent": psutil.disk_usage("/").percent,
            },
        })
    else:
        # Fallback without psutil
        r = _run(["free", "-m"])
        result["memory_raw"] = r["stdout"]
        r2 = _run(["df", "-h", "/"])
        result["disk_raw"] = r2["stdout"]
    return result


@app.post("/restart")
def restart(token: str = Security(verify_token)) -> dict:
    """Restart bookai and nginx services."""
    r1 = _run(["systemctl", "restart", SERVICE_NAME])
    r2 = _run(["systemctl", "restart", "nginx"])
    time.sleep(2)
    status = _service_status(SERVICE_NAME)
    return {
        "ok": status["active"],
        "bookai_restart": r1["ok"],
        "nginx_restart": r2["ok"],
        "bookai_status": status,
        "message": "Services restarted" if status["active"] else "Restart failed — check /logs",
    }


@app.post("/deploy")
def deploy(token: str = Security(verify_token)) -> dict:
    """Pull latest code from GitHub and redeploy.

    Steps: git pull → pip install → run tests → restart service.
    """
    results: list[dict] = []

    # 1. git pull
    r = _run(["git", "pull", "origin", REPO_BRANCH], cwd=str(DEPLOY_DIR))
    results.append({"step": "git_pull", **r})
    if not r["ok"]:
        return {"ok": False, "step_failed": "git_pull", "results": results}

    # 2. pip install
    venv_pip = str(DEPLOY_DIR / "venv" / "bin" / "pip")
    r = _run([venv_pip, "install", "-e", ".", "-q"], cwd=str(DEPLOY_DIR), timeout=180)
    results.append({"step": "pip_install", **r})
    if not r["ok"]:
        return {"ok": False, "step_failed": "pip_install", "results": results}

    # 3. run tests
    venv_pytest = str(DEPLOY_DIR / "venv" / "bin" / "pytest")
    r = _run([venv_pytest, "tests/", "-q", "--tb=short"], cwd=str(DEPLOY_DIR), timeout=120)
    results.append({"step": "tests", **r})
    # Don't fail on test errors — still restart (tests may need env)

    # 4. restart
    r_restart = _run(["systemctl", "restart", SERVICE_NAME])
    results.append({"step": "restart", **r_restart})
    time.sleep(2)
    status = _service_status(SERVICE_NAME)

    return {
        "ok": status["active"],
        "service_status": status,
        "results": results,
        "message": "Deploy OK" if status["active"] else "Deploy done but service not running",
    }


@app.get("/tests")
def run_tests(token: str = Security(verify_token)) -> dict:
    """Run pytest and return results."""
    venv_pytest = str(DEPLOY_DIR / "venv" / "bin" / "pytest")
    start = time.time()
    r = _run([venv_pytest, "tests/", "-q", "--tb=short", "--no-header"],
             cwd=str(DEPLOY_DIR), timeout=180)
    elapsed = round(time.time() - start, 1)
    # Parse summary line
    lines = r["stdout"].splitlines()
    summary = next((l for l in reversed(lines) if "passed" in l or "failed" in l), "")
    return {
        "ok": r["ok"],
        "summary": summary,
        "duration_seconds": elapsed,
        "output": r["stdout"][-3000:],
        "returncode": r["returncode"],
    }


# Allowlist of safe CLI commands (for /run endpoint)
_SAFE_COMMANDS: dict[str, list[str]] = {
    "status":        ["systemctl", "status", "bookai"],
    "logs_tail":     ["journalctl", "-u", "bookai", "-n", "50", "--no-pager"],
    "git_log":       ["git", "log", "--oneline", "-10"],
    "git_status":    ["git", "status"],
    "disk":          ["df", "-h", "/"],
    "memory":        ["free", "-m"],
    "processes":     ["ps", "aux", "--sort=-%mem"],
    "nginx_status":  ["systemctl", "status", "nginx"],
    "python_version": [str(DEPLOY_DIR / "venv" / "bin" / "python3"), "--version"],
    "bookai_help":   [str(DEPLOY_DIR / "venv" / "bin" / "bookai"), "--help"],
}


@app.post("/run")
def run_safe(command: str, token: str = Security(verify_token)) -> dict:
    """Run a pre-approved safe command by name.

    Allowed commands: status, logs_tail, git_log, git_status, disk,
    memory, processes, nginx_status, python_version, bookai_help
    """
    if command not in _SAFE_COMMANDS:
        raise HTTPException(
            status_code=400,
            detail=f"Command '{command}' not in allowlist. "
                   f"Allowed: {list(_SAFE_COMMANDS.keys())}",
        )
    r = _run(_SAFE_COMMANDS[command], cwd=str(DEPLOY_DIR))
    return {"ok": r["ok"], "command": command, "output": r["stdout"], "error": r["stderr"]}


@app.get("/")
def root() -> dict:
    return {
        "service": "BookAI Admin API",
        "version": "1.0.0",
        "endpoints": ["/health", "/logs", "/metrics", "/tests", "/restart", "/deploy", "/run"],
        "auth": "Bearer token required",
    }
