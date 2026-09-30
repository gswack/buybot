from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.search import router as search_router

app = FastAPI(title="Price Comparison API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search_router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok"}
