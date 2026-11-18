"""Make project-root match.py and apply_proposals.py importable from tests/."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
