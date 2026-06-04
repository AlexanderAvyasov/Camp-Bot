from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.sessions import router as sessions_router
from app.api.squads import router as squads_router
from app.api.staff import router as staff_router

app = FastAPI(title="Camp Bot API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(staff_router)
app.include_router(sessions_router)
app.include_router(squads_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
