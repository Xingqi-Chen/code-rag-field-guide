"""Keep a paid reproduction separate from the published immutable results."""
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(os.environ.get('CODE_RAG_RESULTS_DIR',str(ROOT/'research/pilot/results')))
if not OUT.is_absolute():OUT=ROOT/OUT
