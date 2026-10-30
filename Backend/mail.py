"""Email delivery + OTP generation/verification for CivicFix.

OTP codes (password reset and email verification) are 6 digits, stored
hashed (sha256 of code plus a per-row random salt) with a 10-minute expiry
and a 5-attempt limit. One active OTP per email per purpose; the latest
send replaces older rows for the same (email, purpose).

SMTP is fully env-driven:
  CIVICFIX_SMTP_HOST     - e.g. smtp-relay.brevo.com (Brevo) or smtp.gmail.com
  CIVICFIX_SMTP_PORT     - 465 (implicit SSL) or 587 (STARTTLS)
  CIVICFIX_SMTP_USER     - SMTP account / API key login
  CIVICFIX_SMTP_PASSWORD - SMTP password / API key
  CIVICFIX_SMTP_FROM     - verified sender address, e.g. CivicFix <no-reply@x.com>

When SMTP is not configured the caller knows delivery fell back to dev mode
and may show the code in the response for local/demo workflows only.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import smtplib
from email.message import EmailMessage

CIVICFIX_BRAND = os.getenv('CIVICFIX_BRAND', 'CivicFix')

OTP_TTL_SECONDS = 10 * 60
OTP_MAX_ATTEMPTS = 5
OTP_RESEND_COOLDOWN_SECONDS = 60
OTP_LENGTH = 6


def generate_otp_code() -> str:
    return str(secrets.randbelow(10 ** OTP_LENGTH)).zfill(OTP_LENGTH)


def hash_otp_code(code: str, salt: str) -> str:
    return hashlib.sha256((salt + code).encode()).hexdigest()


def verify_otp_code(code: str, stored: str) -> bool:
    """Constant-time check against a 'salt$hexdigest' record."""
    salt, _, digest = stored.partition('$')
    if not digest:
        return False
    return hmac.compare_digest(hash_otp_code(code, salt), digest)


def make_stored_hash(code: str) -> tuple[str, str]:
    """Return (stored_value, salt) where stored_value = salt$hexdigest."""
    salt = secrets.token_hex(8)
    return f'{salt}${hash_otp_code(code, salt)}', salt


def smtp_configured() -> bool:
    return all(os.getenv(key) for key in ('CIVICFIX_SMTP_HOST', 'CIVICFIX_SMTP_USER', 'CIVICFIX_SMTP_PASSWORD'))


def send_email(to_email: str, subject: str, body: str) -> bool:
    """Send plain-text mail. Returns False when SMTP is unconfigured or fails."""
    host = os.getenv('CIVICFIX_SMTP_HOST')
    user = os.getenv('CIVICFIX_SMTP_USER')
    password = os.getenv('CIVICFIX_SMTP_PASSWORD')
    sender = os.getenv('CIVICFIX_SMTP_FROM', user or '')
    if not (host and user and password):
        return False
    try:
        port = int(os.getenv('CIVICFIX_SMTP_PORT', '587'))
        message = EmailMessage()
        message['Subject'] = subject
        message['From'] = sender
        message['To'] = to_email
        message.set_content(body)
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=10) as smtp:
                smtp.login(user, password)
                smtp.send_message(message)
        else:
            with smtplib.SMTP(host, port, timeout=10) as smtp:
                smtp.starttls()
                smtp.login(user, password)
                smtp.send_message(message)
        return True
    except Exception:
        return False


def send_otp_email(to_email: str, code: str, purpose: str = 'password_reset') -> bool:
    body = (
        f'Your CivicFix {purpose} code is: {code}\n\n'
        f'This code expires in {OTP_TTL_SECONDS // 60} minutes and can be used '
        f'{OTP_MAX_ATTEMPTS} times.\nIf you did not request this, ignore this email.'
    )
    return send_email(to_email, f'{CIVICFIX_BRAND} - your verification code', body)
