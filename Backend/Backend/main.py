import os
from pathlib import Path
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

load_dotenv(Path(__file__).resolve().parent / '.env')
from auth import hash_password
from database import get_db, init_db
from routers import admin, auth, issues, worker

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Optional first-admin bootstrap. Set both variables before the first run.
    admin_email = os.getenv('CIVICFIX_ADMIN_EMAIL')
    admin_password = os.getenv('CIVICFIX_ADMIN_PASSWORD')
    if admin_email and admin_password:
        with get_db() as conn:
            exists = conn.execute('SELECT 1 FROM users WHERE email=? COLLATE NOCASE', (admin_email,)).fetchone()
            if not exists:
                conn.execute("INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,'admin')", (os.getenv('CIVICFIX_ADMIN_NAME', 'CivicFix Admin'), admin_email, hash_password(admin_password)))
    yield

app = FastAPI(title='CivicFix API', description='Report civic issues, assign workers, and track resolution progress.', version='1.1.0', lifespan=lifespan)
UPLOAD_DIR = Path(__file__).resolve().parent.parent / 'uploads'
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount('/uploads', StaticFiles(directory=UPLOAD_DIR), name='uploads')
origins = [item.strip() for item in os.getenv('CIVICFIX_CORS_ORIGINS', 'http://localhost:3000,http://localhost:5173').split(',') if item.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=['GET','POST','PATCH','DELETE','OPTIONS'], allow_headers=['Authorization','Content-Type'])
app.include_router(auth.router)
app.include_router(issues.router)
app.include_router(admin.router)
app.include_router(worker.router)

@app.get('/api/health', tags=['Health'])
def health():
    return {'status': 'ok', 'service': 'civicfix-api'}
