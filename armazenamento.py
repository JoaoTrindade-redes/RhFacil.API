"""Operações simples de armazenamento usadas pelo RH Fácil."""
from pathlib import Path

def safe_unlink(path):
    try:
        Path(path).unlink(missing_ok=True)
        return True
    except Exception:
        return False
