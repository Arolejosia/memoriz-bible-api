from fastapi import FastAPI
from game_routes import router as game_router # type: ignore
from duel_routes import router as duel_router # type: ignore

app = FastAPI()

# Endpoint de santé pour UptimeRobot
@app.get("/health")
def health():
    return {"status": "ok"}

# Inclure les routes
app.include_router(game_router)
app.include_router(duel_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

 