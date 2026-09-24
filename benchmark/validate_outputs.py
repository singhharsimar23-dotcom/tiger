"""
benchmark/validate_outputs.py — Pre-submission validator CLI wrapper.
Delegates directly to output.validator adhering strictly to official ground truth schema.
"""
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from output.validator import main

if __name__ == "__main__":
    main(sys.argv[1:] if len(sys.argv) > 1 else None)
