import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .config import get_settings
from .db import get_engine, session_factory
from .routes import agent, auth, mail
from .seed import create_tables, seed_users

log = logging.getLogger("trainmate")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        create_tables()
        with session_factory()() as db:
            seed_users(db)
        log.info("Database ready")
    except Exception as exc:  # keep the API up so the error shows in /api/health
        log.error("Database setup failed: %s", exc)
    yield


app = FastAPI(title="TrainMate Backend", lifespan=lifespan)

origins = [o.strip() for o in get_settings().cors_origins.split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(SQLAlchemyError)
async def database_unavailable(_: Request, exc: SQLAlchemyError):
    log.error("Database error: %s", exc)
    return JSONResponse(status_code=503, content={"detail": "Database is unavailable. Check DATABASE_URL in backend/.env."})


app.include_router(auth.router)
app.include_router(mail.router)
app.include_router(agent.router)


@app.get("/api/health")
def health():
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as exc:
        return {"status": "degraded", "database": str(exc)}
