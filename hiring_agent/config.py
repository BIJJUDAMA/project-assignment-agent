"""
Central configuration for hiring_agent.
Loads environment variables and defines all model parameters.
Single source of truth — replaces root config.py and prompt.py.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Runtime flags ──────────────────────────────────────────────────────────────
DEVELOPMENT_MODE: bool = True

# ── Default model ──────────────────────────────────────────────────────────────
DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "gemma3:4b")

# ── Per-model inference parameters ────────────────────────────────────────────
MODEL_PARAMETERS: dict = {
    "qwen3:1.7b": {"temperature": 0.0, "top_p": 0.9},
    "gemma3:1b":  {"temperature": 0.0, "top_p": 0.9},
    "qwen3:4b":   {"temperature": 0.1, "top_p": 0.4},
    "gemma3:4b":  {"temperature": 0.1, "top_p": 0.9},
    "gemma3:12b": {"temperature": 0.1, "top_p": 0.9},
    "mistral:7b": {"temperature": 0.1, "top_p": 0.9},
}

# ── GitHub ─────────────────────────────────────────────────────────────────────
GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
