from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from database import engine, SessionLocal, Base

app = FastAPI()

# Create tables on startup
Base.metadata.create_all(bind=engine)


# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Root endpoint (VERY IMPORTANT for Render health check)
@app.get("/")
def read_root():
    return {"status": "NeuroVault AI backend is running 🚀"}


# Simple DB test endpoint
@app.get("/test-db")
def test_db(db: Session = Depends(get_db)):
    return {"message": "Database connection successful ✅"}