from fastapi import FastAPI

from app.routers import upload

app = FastAPI(title="Rag Service")
app.include_router(upload.router)

@app.get("/")
async def root():
    return { "status": "ok" }