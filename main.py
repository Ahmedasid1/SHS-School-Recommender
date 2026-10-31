from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.api.routes import router

app = FastAPI(title="SHS School Recommender")
app.include_router(router)


@app.get("/", include_in_schema=False)
def chat_page():
    return FileResponse(Path(__file__).parent / "app" / "static" / "chat.html")


@app.get("/health")
def health():
    return {"status": "ok"}
