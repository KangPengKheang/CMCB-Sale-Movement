"""Vercel FastAPI entrypoint; the CLI runner remains backend/run.py."""
from src.market_bot.app import app

__all__ = ["app"]
