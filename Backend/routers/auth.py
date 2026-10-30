import sqlite3
from fastapi import APIRouter, Depends, HTTPException, status
from auth import create_token, current_user, hash_password, verify_password
from database import get_db
from models import TokenResponse, UserLogin, UserPublic, UserRegister

router = APIRouter(prefix='/api/auth', tags=['Authentication'])

@router.post('/register', response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister):
    try:
        with get_db() as conn:
            cursor = conn.execute('INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)', (payload.name.strip(), payload.email.lower(), hash_password(payload.password), 'user'))
            user = conn.execute('SELECT id,name,email,role,created_at FROM users WHERE id=?', (cursor.lastrowid,)).fetchone()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail='An account with this email already exists')
    return {'access_token': create_token(user['id']), 'user': dict(user)}

@router.post('/login', response_model=TokenResponse)
def login(payload: UserLogin):
    with get_db() as conn:
        user = conn.execute('SELECT * FROM users WHERE email=? COLLATE NOCASE', (payload.email,)).fetchone()
    if user is None or not verify_password(payload.password, user['password_hash']):
        raise HTTPException(status_code=401, detail='Incorrect email or password', headers={'WWW-Authenticate': 'Bearer'})
    return {'access_token': create_token(user['id']), 'user': {key: user[key] for key in ('id','name','email','role','created_at')}}

@router.get('/me', response_model=UserPublic)
def me(user=Depends(current_user)):
    return user
