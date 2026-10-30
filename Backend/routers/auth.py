import sqlite3
from fastapi import APIRouter, Depends, HTTPException, status
from mail import (
    OTP_MAX_ATTEMPTS,
    OTP_RESEND_COOLDOWN_SECONDS,
    OTP_TTL_SECONDS,
    generate_otp_code,
    make_stored_hash,
    send_otp_email,
    verify_otp_code,
)
from auth import create_token, current_user, hash_password, verify_password
from database import get_db
from models import (
    OtpNotice,
    TokenResponse,
    UserForgotPassword,
    UserLogin,
    UserPublic,
    UserRegister,
    UserResetPassword,
    UserVerifyConfirm,
    UserVerifyRequest,
)

router = APIRouter(prefix='/api/auth', tags=['Authentication'])

PURPOSE_LABELS = {
    'password_reset': 'password reset',
    'email_verify': 'email verification',
}


def _public_user(user) -> dict:
    """Row -> login/register-style user payload (keeps 'verified' visible)."""
    return {
        'id': user['id'],
        'name': user['name'],
        'email': user['email'],
        'role': user['role'],
        'verified': bool(user['verified']) if 'verified' in user.keys() else False,
        'created_at': user['created_at'],
    }


def create_purpose_otp(conn, email: str, purpose: str) -> str:
    """Store a fresh hashed OTP for (email, purpose) and return the plain code.

    Raises 429 during the resend cooldown window - let callers decide whether
    that error should surface.
    """
    recent = conn.execute(
        "SELECT (julianday('now') - julianday(created_at)) * 86400 AS seconds_ago "
        'FROM email_otps WHERE email=? AND purpose=?',
        (email, purpose),
    ).fetchone()
    if recent is not None and recent['seconds_ago'] is not None and recent['seconds_ago'] < OTP_RESEND_COOLDOWN_SECONDS:
        raise HTTPException(status_code=429, detail='Please wait a minute before requesting another code')
    code = generate_otp_code()
    code_hash, _salt = make_stored_hash(code)
    conn.execute(
        '''INSERT INTO email_otps(email, purpose, code_hash, attempts, created_at, expires_at)
           VALUES(?, ?, ?, 0, strftime('%Y-%m-%dT%H:%M:%fZ','now'),
                  strftime('%Y-%m-%dT%H:%M:%fZ','now', ?))
           ON CONFLICT(email, purpose) DO UPDATE SET code_hash=excluded.code_hash, attempts=0,
                 created_at=excluded.created_at, expires_at=excluded.expires_at''',
        (email, purpose, code_hash, f'+{OTP_TTL_SECONDS} seconds'),
    )
    return code


def send_purpose_otp(email: str, code: str, purpose: str) -> bool:
    """Deliver the OTP by email; returns False when SMTP is unavailable."""
    return send_otp_email(email, code, PURPOSE_LABELS.get(purpose, purpose))


@router.post('/register', response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister):
    try:
        with get_db() as conn:
            cursor = conn.execute(
                "INSERT INTO users(name,email,password_hash,role,email_verified) VALUES(?,?,?,'user',0)",
                (payload.name.strip(), payload.email.lower(), hash_password(payload.password)),
            )
            user = conn.execute('SELECT id,name,email,role,email_verified,created_at FROM users WHERE id=?', (cursor.lastrowid,)).fetchone()
            verification = None
            try:
                code = create_purpose_otp(conn, user['email'], 'email_verify')
            except Exception:
                code = None  # cooldown hit or delivery hiccup - it must never fail registration
            if code is not None:
                delivered = send_purpose_otp(user['email'], code, 'email_verify')
                verification = OtpNotice(delivery='email' if delivered else 'dev')
                if not delivered:
                    verification.otp = code  # dev fallback: show the code locally
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail='An account with this email already exists')
    return {
        'access_token': create_token(user['id']),
        'user': _public_user(user),
        'verification': verification,
    }

@router.post('/login', response_model=TokenResponse)
def login(payload: UserLogin):
    with get_db() as conn:
        user = conn.execute('SELECT * FROM users WHERE email=? COLLATE NOCASE', (payload.email,)).fetchone()
    if user is None or not verify_password(payload.password, user['password_hash']):
        raise HTTPException(status_code=401, detail='Incorrect email or password', headers={'WWW-Authenticate': 'Bearer'})
    return {'access_token': create_token(user['id']), 'user': _public_user(user)}

@router.get('/me', response_model=UserPublic)
def me(user=Depends(current_user)):
    return user

@router.post('/verify-request', status_code=status.HTTP_202_ACCEPTED)
def verify_request(payload: UserVerifyRequest):
    """Email a 6-digit code to verify the account address."""
    email = payload.email.strip().lower()
    with get_db() as conn:
        user = conn.execute('SELECT id, email_verified FROM users WHERE email=? COLLATE NOCASE', (email,)).fetchone()
        if user is None:
            raise HTTPException(status_code=404, detail='No account with this email')
        if user['email_verified']:
            raise HTTPException(status_code=400, detail='This email is already verified')
        code = create_purpose_otp(conn, email, 'email_verify')
    delivered = send_purpose_otp(email, code, 'email_verify')
    response = {'ok': True, 'delivery': 'email' if delivered else 'dev'}
    if not delivered:
        response['otp'] = code  # dev fallback: SMTP not configured
    return response


@router.post('/verify-confirm')
def verify_confirm(payload: UserVerifyConfirm):
    """Check the emailed code and mark the account as verified."""
    email = payload.email.strip().lower()
    with get_db() as conn:  # reads only - failure bookkeeping uses its own transactions
        row = conn.execute(
            'SELECT * FROM email_otps WHERE email=? AND purpose=?',
            (email, 'email_verify'),
        ).fetchone()
        user = conn.execute('SELECT id, email_verified FROM users WHERE email=? COLLATE NOCASE', (email,)).fetchone()
    if user is None:
        raise HTTPException(status_code=404, detail='No account with this email')
    if user['email_verified']:
        with get_db() as conn:
            conn.execute("DELETE FROM email_otps WHERE email=? AND purpose='email_verify'", (email,))
        raise HTTPException(status_code=400, detail='This email is already verified')
    if row is not None and row['attempts'] >= OTP_MAX_ATTEMPTS:
        # Burned code: delete it in a committed transaction (a rollback on the
        # HTTPException below would otherwise revive it).
        with get_db() as conn:
            conn.execute("DELETE FROM email_otps WHERE email=? AND purpose='email_verify'", (email,))
        raise HTTPException(status_code=400, detail='Too many attempts. Request a new code.')
    if row is None or row['created_at'] > row['expires_at']:
        raise HTTPException(status_code=400, detail='No active verification request. Request a new code.')
    if not verify_otp_code(payload.code, row['code_hash']):
        # Own committed transaction: a rollback here would wipe the attempt
        # counter and let codes be brute-forced forever.
        with get_db() as conn:
            conn.execute(
                "UPDATE email_otps SET attempts=attempts+1 WHERE email=? AND purpose='email_verify'", (email,)
            )
        raise HTTPException(status_code=400, detail='Incorrect code')
    with get_db() as conn:
        conn.execute('UPDATE users SET email_verified=1 WHERE id=?', (user['id'],))
        conn.execute("DELETE FROM email_otps WHERE email=? AND purpose='email_verify'", (email,))
    return {'ok': True, 'message': 'Email verified. Thanks for confirming your address.'}


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
        code = create_purpose_otp(conn, email, 'password_reset')
        existing = conn.execute('SELECT 1 FROM users WHERE email=? COLLATE NOCASE', (email,)).fetchone()
    delivered = False
    if existing is not None:
        delivered = send_purpose_otp(email, code, 'password_reset')
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
            "SELECT * FROM email_otps WHERE email=? AND purpose='password_reset'",
            (email,),
        ).fetchone()
    # Failure bookkeeping runs in its own committed transaction: a rollback on
    # HTTPException would otherwise wipe the attempt counter and let codes
    # be brute-forced forever.
    if row is not None and row['attempts'] >= OTP_MAX_ATTEMPTS:
        with get_db() as conn:
            conn.execute("DELETE FROM email_otps WHERE email=? AND purpose='password_reset'", (email,))
        raise HTTPException(status_code=400, detail='Too many attempts. Request a new code.')
    if row is None or row['created_at'] > row['expires_at']:
        raise HTTPException(status_code=400, detail='No active reset request. Request a new code.')
    if not verify_otp_code(payload.code, row['code_hash']):
        with get_db() as conn:
            conn.execute(
                "UPDATE email_otps SET attempts=attempts+1 WHERE email=? AND purpose='password_reset'", (email,)
            )
        raise HTTPException(status_code=400, detail='Incorrect code')
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET password_hash=? WHERE email=? COLLATE NOCASE",
            (hash_password(payload.new_password), email),
        )
        conn.execute("DELETE FROM email_otps WHERE email=? AND purpose='password_reset'", (email,))
    return {'ok': True, 'message': 'Password updated. Sign in with your new password.'}
