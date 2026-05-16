import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from src.routes.quiz_routes import router as quiz_router
import uvicorn

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]

app = FastAPI(
    title="AI Quiz Learning Intelligence API",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(quiz_router, prefix="/quiz")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def read_website():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)


@app.get("/health")
def read_root():
    return {
        "status": "ok",
        "service": "AI Quiz Learning Intelligence API",
        "endpoints": {
            "generate": "/quiz/generate",
            "evaluate": "/quiz/evaluate",
            "upload": "/quiz/upload",
        },
    }


if __name__ == "__main__":
    # Use import string so uvicorn's --reload works correctly when started from a runner
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
