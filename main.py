"""
Entry point for the hiring agent.

Usage:
    python main.py <pdf_path>        # score a single resume
    python main.py <folder_path>     # score all PDFs in a folder
"""

import sys
import os
from hiring_agent.main import main, main_batch

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <pdf_path|folder_path>")
        sys.exit(1)

    path = sys.argv[1]

    if not os.path.exists(path):
        print(f"Error: Path '{path}' does not exist.")
        sys.exit(1)

    if os.path.isdir(path):
        main_batch(path)
    else:
        main(path)
