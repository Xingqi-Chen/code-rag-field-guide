"""Keep a paid reproduction separate from the published immutable results."""
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(os.environ.get('CODE_RAG_RESULTS_DIR',str(ROOT/'research/pilot/results')))
if not OUT.is_absolute():OUT=ROOT/OUT

SUPPLEMENT=Path(os.environ.get('CODE_RAG_SUPPLEMENT_DIR',str(OUT/'budget-supplement')))
if not SUPPLEMENT.is_absolute():SUPPLEMENT=ROOT/SUPPLEMENT
