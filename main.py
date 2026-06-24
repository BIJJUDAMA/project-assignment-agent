"""
Entry point for the hiring agent.

Usage:
    python main.py <pdf_path>                              # score a single resume
    python main.py <folder_path>                           # score all PDFs in a folder
    python main.py --resumes <path> --projects <path>      # assign candidates to projects
"""

import sys
import os
import argparse
from hiring_agent.main import main, main_batch, main_assignment

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hiring Agent Entry Point")
    parser.add_argument("--resumes", help="Path to resumes PDF or folder containing resume PDFs")
    parser.add_argument("--projects", help="Path to projects PDF or folder containing project PDFs")
    parser.add_argument("legacy_path", nargs="?", help="Legacy path (single resume PDF or folder of resumes)")
    args = parser.parse_args()

    if args.resumes and args.projects:
        main_assignment(args.resumes, args.projects)
    elif args.legacy_path:
        if not os.path.exists(args.legacy_path):
            print(f"Error: Path '{args.legacy_path}' does not exist.")
            sys.exit(1)
        if os.path.isdir(args.legacy_path):
            main_batch(args.legacy_path)
        else:
            main(args.legacy_path)
    else:
        parser.print_help()
        sys.exit(1)

