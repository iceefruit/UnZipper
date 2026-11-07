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


def calculate_optimal_chunk_size_mb(total_bytes: int, free_space_bytes: int = 0) -> int:
    """
    Calculates the mathematically optimal part/chunk size in MB.
    Balances:
    1. Network efficiency: TCP window saturation on fast connections (up to 1 Gbps / 125 MB/s).
    2. File-system efficiency: avoids file handle thrashing (e.g. 800 files for an 80GB game).
    3. Disk safety: ensures parts fit comfortably within available free disk space.
    """
    total_gb = total_bytes / (1024 ** 3)

    if total_gb < 1:
        recommended_mb = 100
    elif total_gb < 5:
        recommended_mb = 250
    elif total_gb < 20:
        recommended_mb = 500
    elif total_gb < 60:
        recommended_mb = 1024  # 1 GB
    else:
        recommended_mb = 1024  # 1 GB (or up to 2 GB for 100GB+ games)

    # If free disk space is known and extremely constrained, scale down safely
    if free_space_bytes > 0:
        safe_max_mb = int((free_space_bytes * 0.4) / (1024 * 1024))
        if safe_max_mb > 50:
            recommended_mb = min(recommended_mb, safe_max_mb)

    return max(50, recommended_mb)

