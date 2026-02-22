import logging

import inngest.fast_api
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.settings import settings
from backend.routers import auth, chat, dishes, sessions
from backend.services.inngest_client import inngest_client
from pipeline.functions import cooking_pipeline

# Surface the Inngest SDK's internal logger so Cloud Run captures API-level
# failures (e.g. _get_batch / _get_steps auth errors) that would otherwise
# appear only as silent HTTP 500s with no Python traceback.
# INFO is sufficient: the SDK uses logger.error() for failures we care about.
logging.getLogger("inngest").setLevel(logging.INFO)

app = FastAPI(
    title="Moment Clone API",
    description="AI cooking coaching backend",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(dishes.router)
app.include_router(sessions.router)
app.include_router(chat.router)

# Mount Inngest durable pipeline at /api/inngest
inngest.fast_api.serve(app, inngest_client, [cooking_pipeline])


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}
