import os
import uuid
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware
from passlib.context import CryptContext

from database import SessionLocal, engine
import models
from models import Chat
from groq import Groq

# --------------------------------------------------
# BASE DIR
# --------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Load .env ONLY locally
if os.getenv("RENDER") is None:
    load_dotenv(os.path.join(BASE_DIR, ".env"))

# --------------------------------------------------
# ENV VARIABLES
# --------------------------------------------------

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SESSION_SECRET = os.getenv("SESSION_SECRET")

if not SESSION_SECRET:
    raise RuntimeError("SESSION_SECRET not set")

# --------------------------------------------------
# APP INIT
# --------------------------------------------------

app = FastAPI()

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET
)

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# --------------------------------------------------
# PASSWORD HASHING
# --------------------------------------------------

pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto"
)

# --------------------------------------------------
# GROQ CLIENT
# --------------------------------------------------

client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
MODEL = "llama-3.1-8b-instant"

# --------------------------------------------------
# DATABASE STARTUP
# --------------------------------------------------

@app.on_event("startup")
def on_startup():
    try:
        models.Base.metadata.create_all(bind=engine)
        print("✅ Database connected successfully")
    except Exception as e:
        print("❌ Database connection failed:", e)

# --------------------------------------------------
# DB DEPENDENCY
# --------------------------------------------------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --------------------------------------------------
# ROUTES
# --------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def landing(request: Request):
    return templates.TemplateResponse("landing.html", {"request": request})


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/register")
def register(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    username = username.strip()
    password = password.strip()

    existing = db.query(models.User).filter(models.User.username == username).first()
    if existing:
        return RedirectResponse("/login", status_code=302)

    hashed = pwd_context.hash(password)

    user = models.User(username=username, password=hashed)
    db.add(user)
    db.commit()
    db.refresh(user)

    request.session["user_id"] = user.id
    return RedirectResponse("/chat_page", status_code=302)


@app.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.username == username).first()

    if not user or not pwd_context.verify(password, user.password):
        return RedirectResponse("/login", status_code=302)

    request.session["user_id"] = user.id
    return RedirectResponse("/chat_page", status_code=302)


@app.get("/chat_page", response_class=HTMLResponse)
def chat_page(request: Request):
    if not request.session.get("user_id"):
        return RedirectResponse("/login")
    return templates.TemplateResponse("chat.html", {"request": request})


@app.post("/chat")
def chat(
    request: Request,
    message: str = Form(...),
    conversation_id: str = Form(...),
    db: Session = Depends(get_db)
):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401)

    db.add(Chat(user_id=user_id, role="user", message=message, conversation_id=conversation_id))
    db.commit()

    history = db.query(Chat).filter(
        Chat.user_id == user_id,
        Chat.conversation_id == conversation_id
    ).all()

    messages = [{
        "role": "system",
        "content": "You are NeuroVault AI. Focus on finance, productivity, health and planning."
    }]

    for msg in history:
        messages.append({"role": msg.role, "content": msg.message})

    if not client:
        raise HTTPException(status_code=500, detail="Groq client not configured")

    completion = client.chat.completions.create(
        model=MODEL,
        messages=messages
    )

    reply = completion.choices[0].message.content

    db.add(Chat(user_id=user_id, role="assistant", message=reply, conversation_id=conversation_id))
    db.commit()

    return JSONResponse({"response": reply})


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=302)
@app.get("/conversations")
def get_conversations(request: Request, db: Session = Depends(get_db)):

    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401)

    conversations = db.query(Chat.conversation_id).filter(
        Chat.user_id == user_id
    ).distinct().all()

    result = []

    for conv in conversations:
        first_msg = db.query(Chat).filter(
            Chat.user_id == user_id,
            Chat.conversation_id == conv[0],
            Chat.role == "user"
        ).first()

        title = first_msg.message[:30] if first_msg else "New Chat"
        result.append({"id": conv[0], "title": title})

    return {"conversations": result}