from fastapi import FastAPI
from database import engine
import models

app = FastAPI()

@app.on_event("startup")
def startup():
    try:
        models.Base.metadata.create_all(bind=engine)
        print("✅ Database initialized successfully")
    except Exception as e:
        print("❌ Database failed:", e)

@app.get("/")
def home():
    return {"status": "Database layer working"}