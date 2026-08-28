from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from app.config import get_settings
from app.database import engine, init_db
from app.routers import (
    anomalies,
    audit,
    auth,
    cases,
    communications,
    evidence,
    faces,
    graph,
    reports,
    search,
    timeline,
    transcripts,
    tts,
)
from app.seed import seed_demo_users

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with Session(engine) as session:
        seed_demo_users(session)
    yield


app = FastAPI(title="NetSherlock", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(cases.router)
app.include_router(evidence.router)
app.include_router(communications.router)
app.include_router(faces.router)
app.include_router(transcripts.router)
app.include_router(search.router)
app.include_router(timeline.router)
app.include_router(graph.router)
app.include_router(anomalies.router)
app.include_router(reports.router)
app.include_router(tts.router)
app.include_router(audit.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
