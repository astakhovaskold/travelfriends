"""Telegram Mini App verification; does not create users or sessions."""
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl
from fastapi import HTTPException
from app.config import BOT_TOKEN


def verify_init_data(init_data):
    try:
        pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
        if len({k for k, _ in pairs}) != len(pairs): raise ValueError()
        data = dict(pairs)
        got = data.pop('hash')
        check = '\n'.join(f'{k}={v}' for k,v in sorted(data.items()))
        secret = hmac.new(b'WebAppData', BOT_TOKEN.encode(), hashlib.sha256).digest()
        expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        timestamp = int(data['auth_date'])
        if not BOT_TOKEN or not hmac.compare_digest(expected, got) or not -30 <= time.time()-timestamp <= 86400:
            raise ValueError()
        user = json.loads(data['user'])
        if not isinstance(user,dict) or type(user.get('id')) is not int or user['id'] <= 0: raise ValueError()
        return user
    except (ValueError, KeyError, TypeError, OverflowError):
        raise HTTPException(401, 'invalid_telegram_data')
