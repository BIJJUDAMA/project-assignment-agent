"""
Package entry point.
Enables:  python -m hiring_agent <pdf_path>
"""

import sys
import os
from hiring_agent.main import main

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m hiring_agent <pdf_path>")
        sys.exit(1)

    pdf_path = sys.argv[1]

    if not os.path.exists(pdf_path):
        print(f"Error: File '{pdf_path}' does not exist.")
        sys.exit(1)

    main(pdf_path)
