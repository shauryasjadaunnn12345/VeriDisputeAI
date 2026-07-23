from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import Base, engine
from backend.routers import dashboard, disputes, health, items

app = FastAPI(title="Backend API")

# Allow the local Vite dev server to call the API during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(items.router)
app.include_router(disputes.router)
app.include_router(dashboard.router)


@app.on_event("startup")
def on_startup():
    """Create all tables if they don't already exist (SQLite dev DB by
    default; set DATABASE_URL for Postgres/etc in other environments)."""
    Base.metadata.create_all(bind=engine)


@app.get("/")
def root():
    return {"message": "Backend API is running"}
