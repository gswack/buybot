from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import close_db_pool, init_db_pool
from app.embeddings import load_model
from app.routes.search import router as search_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: load the CLIP model once and open the DB pool
    load_model()
    await init_db_pool()
    yield
    # Shutdown
    await close_db_pool()


app = FastAPI(title="Price Comparison API", lifespan=lifespan)

# Allow the local Vite dev server (and any origin, for this PoC) to call the API.
# Tighten this to specific origins before deploying anywhere public.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search_router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok"}