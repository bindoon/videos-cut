"""Explicit job directories keep experiments away from the delivered film."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def output_directory(*, protect_delivery=False):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    output = parser.parse_args().output.resolve()
    if protect_delivery and (output / "杭州-一城山水千年生长.mp4").exists():
        parser.error("This directory already contains a delivered film; choose a new --output")
    output.mkdir(parents=True, exist_ok=True)
    return output
