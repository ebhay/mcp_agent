import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError

from .config import get_settings
from .db import get_db
from .routes import agent, auth, mail
from .seed import create_indexes, seed_users

log = logging.getLogger("trainmate")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        db = get_db()
        create_indexes(db)
        seed_users(db)
        log.info("MongoDB ready")
    except Exception as exc:  # keep the API up so the error shows in /api/health
        log.error("MongoDB setup failed: %s", exc)
    yield


app = FastAPI(title="TrainMate Backend", lifespan=lifespan)

origins = [o.strip() for o in get_settings().cors_origins.split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])

@app.exception_handler(PyMongoError)
async def database_unavailable(_: Request, exc: PyMongoError):
    log.error("Database error: %s", exc)
    return JSONResponse(status_code=503, content={"detail": "Database is unavailable. Check MONGO_URI and network access."})


app.include_router(auth.router)
app.include_router(mail.router)
app.include_router(agent.router)


@app.get("/api/health")
def health():
    try:
        get_db().command("ping")
        return {"status": "ok", "database": "connected"}
    except Exception as exc:
        return {"status": "degraded", "database": str(exc)}
