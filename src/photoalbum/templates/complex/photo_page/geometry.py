"""Complex reference geometries. One authoritative JSON definition per page family."""
from __future__ import annotations
import json
from pathlib import Path
DATA = json.loads(Path(__file__).with_name("geometry.json").read_text(encoding="utf-8"))
