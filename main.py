from fastapi import FastAPI, Request 
from fastapi.middleware.cors import CORSMiddleware
from game_routes import router as game_router # type: ignore
from duel_routes import router as duel_router # type: ignore

app = FastAPI()

# ✅ CORS - AJOUTER CECI EN PREMIER
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://memorizbible.web.app",
        "https://memorizbible.firebaseapp.com",
    ],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware langue
@app.middleware("http")
async def add_language_to_request(request: Request, call_next):
    language = request.headers.get("Accept-Language", "fr")
    if language.startswith("en"):
        request.state.language = "en"
    else:
        request.state.language = "fr"
    response = await call_next(request)
    return response

@app.get("/health")
def health():
    return {"status": "ok"}

app.include_router(game_router)
app.include_router(duel_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
