"""Provider-independent opaque sessions, with legacy Telegram header support."""
import hashlib
import secrets
import time
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, insert, update, delete
from sqlalchemy.exc import IntegrityError
from app.config import SESSION_TTL
from app.db.session import db
from app.db.models import users, auth_identities, sessions
from app.integrations.telegram.auth import verify_init_data
from app.services.common import lang_of

router = APIRouter()

def check_user(row):
    if row is None: raise HTTPException(401, 'unauthorized')
    if row['banned']: raise HTTPException(403,'banned')
    if row['minor']: raise HTTPException(403,'minor')
    return dict(row)

def telegram_user(init_data):
    info = verify_init_data(init_data)
    with db(write=True) as c:
        identity = c.connection.execute(select(auth_identities).where(auth_identities.c.provider=='telegram',auth_identities.c.subject==str(info['id']))).mappings().first()
        if identity:
            user_id = identity['user_id']
        else:
            user_id = c.connection.execute(insert(users).values(name=info.get('first_name',''), username=info.get('username'),lang=lang_of(info.get('language_code'))).returning(users.c.id)).scalar_one()
            c.connection.execute(insert(auth_identities).values(user_id=user_id,provider='telegram',subject=str(info['id'])))
        c.connection.execute(update(users).where(users.c.id==user_id).values(name=info.get('first_name',''),username=info.get('username'),lang=lang_of(info.get('language_code'))))
        return check_user(c.connection.execute(select(users).where(users.c.id==user_id)).mappings().first())

def get_current_user(authorization: str = Header(''), x_init_data: str = Header('')):
    if authorization:
        scheme, _, token = authorization.partition(' ')
        if scheme.lower()!='bearer' or not token: raise HTTPException(401,'unauthorized')
        with db() as c:
            row = c.connection.execute(select(users).join(sessions).where(
                sessions.c.token_hash==hashlib.sha256(token.encode()).hexdigest(), sessions.c.expires_at>int(time.time()))).mappings().first()
        return check_user(row)
    if x_init_data:
        try: return telegram_user(x_init_data)
        except IntegrityError: return telegram_user(x_init_data)  # concurrent first login: transaction rolled back
    raise HTTPException(401,'unauthorized')

def ensure_ready(user):
    with db() as c:
        row = c.connection.execute(select(users.c.rules_ok,users.c.registered).where(users.c.id==user['id'])).mappings().one()
    if not row['rules_ok']: raise HTTPException(403,'rules')
    if not row['registered']: raise HTTPException(403,'register')

def issue_session(user):
    token = secrets.token_urlsafe(32)
    expires = int(time.time())+SESSION_TTL
    with db() as c:
        c.connection.execute(insert(sessions).values(token_hash=hashlib.sha256(token.encode()).hexdigest(),user_id=user['id'],expires_at=expires))
    return {'access_token':token,'token_type':'bearer','expires_at':expires,'user_id':user['id']}

class TelegramLogin(BaseModel):
    init_data: str = Field(max_length=20000)

@router.post('/api/auth/telegram')
def exchange_telegram(body: TelegramLogin):
    try: user = telegram_user(body.init_data)
    except IntegrityError: user = telegram_user(body.init_data)
    return issue_session(user)

@router.post('/api/auth/logout')
def logout(user: dict = Depends(get_current_user), authorization: str = Header('')):
    _,_,token = authorization.partition(' ')
    if token:
        with db() as c: c.connection.execute(delete(sessions).where(sessions.c.token_hash==hashlib.sha256(token.encode()).hexdigest(), sessions.c.user_id==user['id']))
    return {'ok':True}

# Email/password provides a standalone client entry point. Passwords never leave
# this module; scrypt hashes use per-password salts, and sessions store only hashes.
import base64
import hmac
import re
from threading import BoundedSemaphore

_hash_slots = BoundedSemaphore(2)

class EmailLogin(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)

class EmailRegister(EmailLogin):
    name: str = Field(min_length=1, max_length=80)


def normalize_email(value):
    value = value.strip().lower()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value): raise HTTPException(422,'invalid_email')
    return value

def password_hash(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    if not _hash_slots.acquire(blocking=False):
        raise HTTPException(429, 'slow')
    try:
        digest = hashlib.scrypt(password.encode(),salt=salt,n=2**17,r=8,p=1,maxmem=256*1024*1024)
    finally:
        _hash_slots.release()
    return 'scrypt$'+base64.b64encode(salt).decode()+'$'+base64.b64encode(digest).decode()

@router.post('/api/auth/register', status_code=201)
def email_register(body: EmailRegister):
    email = normalize_email(body.email)
    if not body.name.strip(): raise HTTPException(422, 'invalid_name')
    encoded = password_hash(body.password)
    try:
        with db(write=True) as c:
            user_id = c.connection.execute(insert(users).values(name=body.name.strip()).returning(users.c.id)).scalar_one()
            c.connection.execute(insert(auth_identities).values(user_id=user_id,provider='email',subject=email,password_hash=encoded))
    except IntegrityError:
        raise HTTPException(409,'email_in_use')
    return issue_session({'id':user_id})

@router.post('/api/auth/login')
def email_login(body: EmailLogin):
    email = normalize_email(body.email)
    with db() as c:
        row = c.connection.execute(select(auth_identities).where(auth_identities.c.provider=='email',auth_identities.c.subject==email)).mappings().first()
    salt = base64.b64decode(row['password_hash'].split('$')[1]) if row else b'\0'*16
    actual = password_hash(body.password,salt)
    if row is None or not hmac.compare_digest(actual,row['password_hash']): raise HTTPException(401,'invalid_credentials')
    with db() as c:
        user = check_user(c.connection.execute(select(users).where(users.c.id==row['user_id'])).mappings().first())
    return issue_session(user)

@router.post('/api/auth/link/telegram')
def link_telegram(body: TelegramLogin, user: dict = Depends(get_current_user)):
    info = verify_init_data(body.init_data)
    try:
        with db(write=True) as c:
            c.lock_user(user['id'])
            existing = c.connection.execute(select(auth_identities).where(
                auth_identities.c.provider=='telegram',auth_identities.c.subject==str(info['id']))).mappings().first()
            if existing and existing['user_id']!=user['id']: raise HTTPException(409,'identity_in_use')
            if not existing:
                # One Telegram account per internal user prevents ambiguous notification destinations.
                attached = c.connection.execute(select(auth_identities.c.id).where(auth_identities.c.user_id==user['id'],auth_identities.c.provider=='telegram')).first()
                if attached: raise HTTPException(409,'telegram_already_linked')
                c.connection.execute(insert(auth_identities).values(user_id=user['id'],provider='telegram',subject=str(info['id'])))
    except IntegrityError: raise HTTPException(409,'identity_in_use')
    return {'ok':True}
