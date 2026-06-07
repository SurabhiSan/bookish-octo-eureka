from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, clones, documents, conversations

app = FastAPI(title="AI Clone Platform", version="0.1.0")

import os
_origins = [
    "http://localhost:3000",
    os.getenv("FRONTEND_URL", ""),
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in _origins if o],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(clones.router)
app.include_router(documents.router)
app.include_router(conversations.router)


@app.get("/health")
async def health():
    from app.db.session import get_engine
    from sqlalchemy import text
    async with get_engine().connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {"status": "ok"}
