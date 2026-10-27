import sys
from pathlib import Path

SERVER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER))
sys.path.insert(0, str(SERVER / "scam_check"))

FIXTURES = Path(__file__).resolve().parent / "fixtures"
