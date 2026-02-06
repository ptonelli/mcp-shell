import os
from app.config import WORKDIR

def is_safe_path(path: str) -> bool:
    """Check if the path is within the WORKDIR"""
    try:
        common = os.path.commonpath([WORKDIR, os.path.abspath(path)])
        return common == WORKDIR
    except (ValueError, Exception):
        return False
