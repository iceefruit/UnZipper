import os
import shutil
from pathlib import Path


def format_bytes(size_bytes: int) -> str:
    """Format bytes to human-readable string (KB, MB, GB, TB)."""
    if size_bytes < 0:
        return f"-{format_bytes(-size_bytes)}"
    if size_bytes == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    idx = 0
    val = float(size_bytes)
    while val >= 1024.0 and idx < len(units) - 1:
        val /= 1024.0
        idx += 1
    return f"{val:.2f} {units[idx]}"


def get_free_disk_space(target_path: str) -> int:
    """Return free disk space in bytes for the drive containing target_path."""
    try:
        resolved = os.path.abspath(target_path)
        while not os.path.exists(resolved) and resolved != os.path.dirname(resolved):
            resolved = os.path.dirname(resolved)
        return shutil.disk_usage(resolved).free
    except Exception:
        return 0


def is_safe_path(base_dir: str, target_path: str) -> bool:
    """Guard against Zip-Slip path traversal attacks."""
    base = os.path.abspath(base_dir)
    target = os.path.abspath(target_path)
    return os.path.commonpath([base]) == os.path.commonpath([base, target])
