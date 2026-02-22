from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import init_db
from contextlib import asynccontextmanager

from app.core.watcher import watcher

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    watcher.start()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

from app.middleware.privacy import PIIRedactionMiddleware

# Set all CORS enabled origins
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.add_middleware(PIIRedactionMiddleware)

@app.get("/health")
def health_check():
    return {"status": "ok", "app": settings.PROJECT_NAME}

@app.get("/")
def root():
    return {"message": "Welcome to Viyugam - The Boardroom is Open."}

# Import Routers
from app.api.v1.endpoints import agents, tasks, domains, projects, ops, finance

app.include_router(agents.router, prefix=f"{settings.API_V1_STR}/agents", tags=["agents"])
app.include_router(tasks.router, prefix=f"{settings.API_V1_STR}/tasks", tags=["tasks"])
app.include_router(domains.router, prefix=f"{settings.API_V1_STR}/domains", tags=["domains"])
app.include_router(projects.router, prefix=f"{settings.API_V1_STR}/projects", tags=["projects"])
app.include_router(finance.router, prefix=f"{settings.API_V1_STR}/finance", tags=["finance"])
app.include_router(ops.router, prefix=f"{settings.API_V1_STR}/ops", tags=["ops"])

