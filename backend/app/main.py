import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import close_db_pool, create_tables, init_db_pool
from app.routes.search import router as search_router
from app.routes.users import router as users_router
from app.routes.classify import router as classify_router
from app.routes.coupons import router as coupons_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db_pool()
    await create_tables()
    yield
    await close_db_pool()


app = FastAPI(title="Price Comparison API", lifespan=lifespan)

# Allowed browser origins. Local dev (Vite on 5173) is always allowed; add the
# deployed frontend origin(s) via CORS_ALLOW_ORIGINS (comma-separated), e.g.
# "http://40.114.239.40,http://buybot.example.com". When the frontend is served
# through the Nginx proxy as same-origin /api, CORS is not even triggered, but
# this keeps direct/cross-origin access working too.
_default_origins = ["http://localhost:5173", "http://localhost:3000"]
_env_origins = [
    o.strip()
    for o in os.getenv("CORS_ALLOW_ORIGINS", "").split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_default_origins + _env_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search_router, prefix="/api")
app.include_router(users_router, prefix="/api")
app.include_router(classify_router, prefix="/api")
app.include_router(coupons_router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok"}
