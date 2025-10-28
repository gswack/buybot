from fastapi import FastAPI
from core.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION)

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "environment": settings.ENVIRONMENT,
        "debug": settings.DEBUG,
    }
