import sqlite3
from fastapi import APIRouter, Depends, HTTPException, status
from mail import (
    OTP_MAX_ATTEMPTS,
    OTP_RESEND_COOLDOWN_SECONDS,
    OTP_TTL_SECONDS,
    generate_otp_code,
    make_stored_hash,
    send_otp_email,
    smtp_configured,
    verify_otp_code,
)
from auth import create_token, current_user, hash_password, verify_password
from database import get_db
from models import (
    TokenResponse,
    UserForgotPassword,
    UserLogin,
    UserPublic,
    UserRegister,
    UserResetPassword,
)

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


@router.post('/forgot-password', status_code=status.HTTP_202_ACCEPTED)
def forgot_password(payload: UserForgotPassword):
    """Start a password reset by emailing a 6-digit OTP.

    The response never reveals whether the email is registered. Delivery is
    real SMTP when configured; otherwise dev fallback returns the code so
    local flows and demos keep working.
    """
    email = payload.email.strip().lower()
    existing = None
    with get_db() as conn:
        # Cooldown: at most one send per email per cooldown window.
        recent = conn.execute(
            "SELECT (julianday('now') - julianday(created_at)) * 86400 AS seconds_ago "
            'FROM password_reset_otps WHERE email=?',
            (email,),
        ).fetchone()
        if recent is not None and recent['seconds_ago'] is not None and recent['seconds_ago'] < OTP_RESEND_COOLDOWN_SECONDS:
            raise HTTPException(status_code=429, detail='Please wait a minute before requesting another code')
        code = generate_otp_code()
        code_hash, _salt = make_stored_hash(code)
        conn.execute(
            '''INSERT INTO password_reset_otps(email, code_hash, attempts, created_at, expires_at)
               VALUES(?, ?, 0, strftime('%Y-%m-%dT%H:%M:%fZ','now'),
                      strftime('%Y-%m-%dT%H:%M:%fZ','now', ?))
               ON CONFLICT(email) DO UPDATE SET code_hash=excluded.code_hash, attempts=0,
                     created_at=excluded.created_at, expires_at=excluded.expires_at''',
            (email, code_hash, f'+{OTP_TTL_SECONDS} seconds'),
        )
        existing = conn.execute('SELECT 1 FROM users WHERE email=? COLLATE NOCASE', (email,)).fetchone()
    delivered = False
    if existing is not None:
        delivered = send_otp_email(email, code)
    else:
        delivered = True  # uniform response: never reveal whether the email is registered
    response = {'ok': True, 'delivery': 'email' if delivered else 'dev'}
    if not delivered:
        # SMTP unconfigured (or send failed): surface the code for local/demo only.
        response['otp'] = code
    return response


@router.post('/reset-password')
def reset_password(payload: UserResetPassword):
    """Verify the emailed OTP and set the new password (invalidates the OTP)."""
    email = payload.email.strip().lower()
    with get_db() as conn:
        row = conn.execute(
            'SELECT * FROM password_reset_otps WHERE email=?',
            (email,),
        ).fetchone()
    # Failure bookkeeping runs in its own committed transaction: a rollback on
    # HTTPException would otherwise wipe the attempt counter and let codes
    # be brute-forced forever.
    if row is not None and row['attempts'] >= OTP_MAX_ATTEMPTS:
        with get_db() as conn:
            conn.execute('DELETE FROM password_reset_otps WHERE email=?', (email,))
        raise HTTPException(status_code=400, detail='Too many attempts. Request a new code.')
    if row is None or row['created_at'] > row['expires_at']:
        raise HTTPException(status_code=400, detail='No active reset request. Request a new code.')
    if not verify_otp_code(payload.code, row['code_hash']):
        with get_db() as conn:
            conn.execute('UPDATE password_reset_otps SET attempts=attempts+1 WHERE email=?', (email,))
        raise HTTPException(status_code=400, detail='Incorrect code')
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET password_hash=? WHERE email=? COLLATE NOCASE",
            (hash_password(payload.new_password), email),
        )
        conn.execute('DELETE FROM password_reset_otps WHERE email=?', (email,))
    return {'ok': True, 'message': 'Password updated. Sign in with your new password.'}
