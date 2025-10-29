import os
import subprocess
import sys
from typing import Optional

from .constants import ADB_PATH_FILE, BASE_DIR

def find_adb_executable() -> Optional[str]:
    """Try previously saved path, common install locations, then PATH."""
    try:
        if os.path.exists(ADB_PATH_FILE):
            with open(ADB_PATH_FILE, "r", encoding="utf-8") as f:
                saved = f.read().strip()
            if saved and os.path.exists(saved):
                return saved
    except Exception:
        pass

    candidates = [
        os.path.join(BASE_DIR, "platform-tools", "adb.exe"),
        os.path.join(BASE_DIR, "platform-tools", "adb"),
        r"C:\Android\platform-tools\adb.exe",
        r"C:\Program Files (x86)\Android\android-sdk\platform-tools\adb.exe",
        r"C:\Program Files\Android\android-sdk\platform-tools\adb.exe",
    ]
    for p in candidates:
        if p and os.path.exists(p):
            return p
    for path_dir in os.getenv("PATH", "").split(os.pathsep):
        if not path_dir:
            continue
        for fn in ("adb.exe", "adb"):
            adb_candidate = os.path.join(path_dir.strip('"'), fn)
            if os.path.exists(adb_candidate):
                return adb_candidate
    return None

def run_cmd(cmd, timeout=30):
    """Run a command and return decoded stdout/stderr, similar to original _run."""
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=timeout)
        return out.decode(errors="ignore")
    except subprocess.CalledProcessError as e:
        return (e.output or b"").decode(errors="ignore")
    except Exception as e:
        return str(e)