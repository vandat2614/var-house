"""
FastAPI Application Entry Point.

- Creates the FastAPI app and registers routers.
- Serves the Match Center web app via StaticFiles at /.
- On startup, warms up the Iceberg catalog connection.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from src.api.deps import _get_repository, warmup

logger = logging.getLogger("uvicorn.error")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")



def run_warmup_with_logs():
    import time
    logger.info("Started warmup process...")
    start = time.time()
    try:
        warmup()
        logger.info(f"Warmup completed successfully in {time.time() - start:.2f}s")
    except Exception as e:
        logger.error(f"Warmup failed after {time.time() - start:.2f}s: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio, concurrent.futures
    logger.info("API starting up - warming cache in background thread...")
    # Run warmup in thread pool so it doesn't block the event loop
    loop = asyncio.get_event_loop()
    loop.run_in_executor(concurrent.futures.ThreadPoolExecutor(max_workers=1), run_warmup_with_logs)
    yield
    logger.info("API shutting down.")


app = FastAPI(
    title="Football Match Center API",
    description="Real-time football match data powered by Apache Iceberg + DuckDB.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

from src.api.controllers.match_controller import router as match_router
from src.api.controllers.league_controller import router as league_router
from src.api.controllers.dashboard_controller import router as dashboard_router

app.include_router(match_router)
app.include_router(league_router)
app.include_router(dashboard_router)


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
async def serve_index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


# Mount remaining static assets (JS, CSS, images if any) at /static
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
