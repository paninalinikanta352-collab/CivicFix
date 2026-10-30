import os
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from database import get_db

SECRET_KEY = os.getenv('CIVICFIX_SECRET_KEY', 'local-dev-secret-change-before-deployment')
ALGORITHM = 'HS256'
TOKEN_MINUTES = int(os.getenv('CIVICFIX_TOKEN_MINUTES', '1440'))
password_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/api/auth/login')

def hash_password(password: str) -> str:
    return password_context.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    return password_context.verify(password, password_hash)

def create_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({'sub': str(user_id), 'iat': now, 'exp': now + timedelta(minutes=TOKEN_MINUTES)}, SECRET_KEY, algorithm=ALGORITHM)

def current_user(token: str = Depends(oauth2_scheme)):
    invalid = HTTPException(status_code=401, detail='Invalid or expired access token', headers={'WWW-Authenticate': 'Bearer'})
    try:
        user_id = int(jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM]).get('sub', ''))
    except (JWTError, ValueError, TypeError):
        raise invalid
    with get_db() as conn:
        user = conn.execute('SELECT id,name,email,role,created_at FROM users WHERE id=?', (user_id,)).fetchone()
    if user is None:
        raise invalid
    return dict(user)

def require_role(*roles):
    def dependency(user=Depends(current_user)):
        if user['role'] not in roles:
            raise HTTPException(status_code=403, detail='You do not have permission to perform this action')
        return user
    return dependency
