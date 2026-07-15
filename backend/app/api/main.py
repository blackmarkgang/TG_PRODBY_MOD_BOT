from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import applications, health, participants, whitelist
from app.core.config import settings
from app.db.session import SessionLocal
from app.services.bootstrap import seed_defaults


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with SessionLocal() as session:
        await seed_defaults(session)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(applications.router, prefix="/applications", tags=["applications"])
app.include_router(participants.router, prefix="/participants", tags=["participants"])
app.include_router(whitelist.router, prefix="/whitelist", tags=["whitelist"])
