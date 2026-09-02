#!/usr/bin/env python3
"""
Run both frontend and backend locally for development.
This script starts the NextJS frontend and FastAPI backend in parallel.
"""

import os
import re
import sys
import subprocess
import signal
import time
import urllib.error
import urllib.request
from pathlib import Path

# On Windows, npm/node are .cmd files and need shell=True to be found
IS_WINDOWS = sys.platform == "win32"

# Track subprocesses for cleanup
processes = []


def cleanup(signum=None, frame=None):
    """Clean up all subprocess on exit"""
    print("\n🛑 Shutting down services...")
    for proc in processes:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except:
            proc.kill()
    sys.exit(0)


# Register cleanup handlers
signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)


def check_requirements():
    """Check if required tools are installed"""
    checks = []

    # Check Node.js
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True)
        node_version = result.stdout.strip()
        checks.append(f"✅ Node.js: {node_version}")
    except FileNotFoundError:
        checks.append("❌ Node.js not found - please install Node.js")

    # Check npm
    try:
        result = subprocess.run(
            ["npm", "--version"], capture_output=True, text=True, shell=IS_WINDOWS
        )
        npm_version = result.stdout.strip()
        checks.append(f"✅ npm: {npm_version}")
    except FileNotFoundError:
        checks.append("❌ npm not found - please install npm")

    # Check uv (which manages Python for us)
    try:
        result = subprocess.run(["uv", "--version"], capture_output=True, text=True)
        uv_version = result.stdout.strip()
        checks.append(f"✅ uv: {uv_version}")
    except FileNotFoundError:
        checks.append("❌ uv not found - please install uv")

    print("\n📋 Prerequisites Check:")
    for check in checks:
        print(f"  {check}")

    # Exit if any critical tools are missing
    if any("❌" in check for check in checks):
        print("\n⚠️  Please install missing dependencies and try again.")
        sys.exit(1)


def check_env_files():
    """Check if environment files exist"""
    project_root = Path(__file__).parent.parent

    root_env = project_root / ".env"
    frontend_env = project_root / "frontend" / ".env.local"

    missing = []

    if not root_env.exists():
        missing.append(".env (root project file)")
    if not frontend_env.exists():
        missing.append("frontend/.env.local")

    if missing:
        print("\n⚠️  Missing environment files:")
        for file in missing:
            print(f"  - {file}")
        print("\nPlease create these files with the required configuration.")
        print("The root .env should have all backend variables from Parts 1-7.")
        print("The frontend/.env.local should have Clerk keys.")
        sys.exit(1)

    print("✅ Environment files found")


def start_backend():
    """Start the FastAPI backend"""
    backend_dir = Path(__file__).parent.parent / "backend" / "api"

    print("\n🚀 Starting FastAPI backend...")

    # Check if dependencies are installed
    if not (backend_dir / ".venv").exists() and not (backend_dir / "uv.lock").exists():
        print("  Installing backend dependencies...")
        subprocess.run(["uv", "sync"], cwd=backend_dir, check=True)

    # Start the backend with uvicorn so the FastAPI app actually boots
    proc = subprocess.Popen(
        [
            "uv",
            "run",
            "uvicorn",
            "main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
            "--reload",
            "--log-level",
            "debug",
        ],
        cwd=backend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    processes.append(proc)

    # Wait for backend to start
    print("  Waiting for backend to start...")
    for _ in range(30):  # 30 second timeout
        try:
            with urllib.request.urlopen("http://localhost:8000/docs", timeout=1) as response:
                if response.status == 200:
                    print("  ✅ Backend running at http://localhost:8000")
                    print("     API docs: http://localhost:8000/docs")
                    return proc
        except Exception:
            time.sleep(1)

    # Surface logs before giving up so the root cause is visible
    print("  ❌ Backend failed to start")
    try:
        for _ in range(10):
            line = proc.stdout.readline()
            if line:
                print(f"    Backend: {line.strip()}")
            else:
                break
    except Exception:
        pass
    cleanup()


def start_frontend():
    """Start the NextJS frontend"""
    frontend_dir = Path(__file__).parent.parent / "frontend"

    print("\n🚀 Starting NextJS frontend...")

    # Check if dependencies are installed
    if not (frontend_dir / "node_modules").exists():
        print("  Installing frontend dependencies...")
        subprocess.run(
            ["npm", "install"], cwd=frontend_dir, check=True, shell=IS_WINDOWS
        )

    # Start the frontend
    proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=frontend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # Combine stderr with stdout
        text=True,
        bufsize=1,
        shell=IS_WINDOWS,
    )
    processes.append(proc)

    # Wait for frontend to start
    print("  Waiting for frontend to start...")
    import threading

    # Read frontend output in a background thread (select.select doesn't work on Windows pipes)
    started_flag = {"started": False}
    detected_port = {"value": None}

    def read_output():
        for line in proc.stdout:
            text = line.strip()
            print(f"    Frontend: {text}")
            match = re.search(r"http://localhost:(\d+)", text)
            if match:
                detected_port["value"] = int(match.group(1))
            if (
                "ready" in text.lower()
                or "compiled" in text.lower()
                or "started server" in text.lower()
            ):
                started_flag["started"] = True

    reader = threading.Thread(target=read_output, daemon=True)
    reader.start()

    candidate_ports = [3000, 3001, 3002, 3003, 3004]
    for i in range(30):  # 30 second timeout
        port = detected_port["value"] or (3000 if i < 5 else 3001)
        if started_flag["started"] or i > 5:
            for candidate in [detected_port["value"], *[p for p in candidate_ports if p != detected_port["value"]]]:
                if candidate is None:
                    continue
                try:
                    with urllib.request.urlopen(f"http://localhost:{candidate}", timeout=1) as response:
                        if response.status == 200:
                            print(f"  ✅ Frontend running at http://localhost:{candidate}")
                            return proc
                except Exception:
                    pass

        time.sleep(1)

    print("  ❌ Frontend failed to start")
    cleanup()


def monitor_processes():
    """Monitor running processes and show their output"""
    print("\n" + "=" * 60)
    print("🎯 Alex Financial Advisor - Local Development")
    print("=" * 60)
    print("\n📍 Services:")
    print("  Frontend: http://localhost:3000")
    print("  Backend:  http://localhost:8000")
    print("  API Docs: http://localhost:8000/docs")
    print("\n📝 Logs will appear below. Press Ctrl+C to stop.\n")
    print("=" * 60 + "\n")

    # Monitor processes
    while True:
        for proc in processes:
            # Some dev servers (npm/next, uvicorn with reloader) spawn child processes and
            # the wrapper process can exit while the service itself remains healthy.
            # Avoid stopping the whole script on that normal wrapper exit pattern.
            exit_code = proc.poll()
            if exit_code is not None:
                print(f"\nℹ️  Wrapped process exited with code {exit_code}; service may continue in background.")

            # Read any available output
            try:
                line = proc.stdout.readline()
                if line:
                    print(f"[LOG] {line.strip()}")
            except Exception:
                pass

        time.sleep(0.1)


def main():
    """Main entry point"""
    print("\n🔧 Alex Financial Advisor - Local Development Setup")
    print("=" * 50)

    # Check prerequisites
    check_requirements()
    check_env_files()

    # Start services
    backend_proc = start_backend()
    frontend_proc = start_frontend()

    # Monitor processes
    try:
        monitor_processes()
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    main()
