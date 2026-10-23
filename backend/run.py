import argparse
import uvicorn
from src.market_bot.config import Settings

if __name__ == "__main__":
    settings = Settings.load()
    parser = argparse.ArgumentParser(description="CMCB Market Improvement Bot Backend Server")
    parser.add_argument("--host", type=str, default=settings.server_host, help="Server bind host")
    parser.add_argument("--port", type=int, default=settings.server_port, help="Server bind port")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    args = parser.parse_args()

    browser_host = "127.0.0.1" if args.host in ("0.0.0.0", "::", "[::]") else args.host
    if ":" in browser_host and not browser_host.startswith("["):
        browser_host = f"[{browser_host}]"
    browser_url = f"http://{browser_host}:{args.port}"

    print("=" * 65)
    print(f" CMCB MARKET IMPROVEMENT BOT — FASTAPI SERVER")
    print("=" * 65)
    print(f" Environment : {settings.environment.upper()}")
    print(f" Database    : {settings.db_path}")
    print(f" Bind address: {args.host}:{args.port}")
    print(f" Dashboard   : {browser_url}/")
    print(f" API Docs    : {browser_url}/docs")
    print("=" * 65)

    uvicorn.run("src.market_bot.app:app", host=args.host, port=args.port, reload=args.reload)
