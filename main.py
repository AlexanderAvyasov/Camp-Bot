"""
Entry point: starts both the FastAPI server and the Telegram bot in one process.
For production on Railway, set START_MODE env var to 'bot' or 'api' to run separately.
"""
import asyncio
import os

import uvicorn

from app.api.app import app as fastapi_app


def run_api():
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(fastapi_app, host="0.0.0.0", port=port)


async def run_bot():
    from app.bot.bot import main as bot_main
    await bot_main()


async def run_both():
    import threading
    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()
    await run_bot()


if __name__ == "__main__":
    mode = os.environ.get("START_MODE", "both")
    if mode == "api":
        run_api()
    elif mode == "bot":
        asyncio.run(run_bot())
    else:
        asyncio.run(run_both())
