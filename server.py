"""Verified Telegram Mini App event endpoint; never accepts API keys."""
import hashlib
import hmac
import json
import logging
import os
import time
from html import escape
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from aiohttp import web
from aiogram import Bot
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name('.env'))
TOKEN = os.getenv('BOT_TOKEN', '')
CHAT = os.getenv('LOG_CHAT_ID', '')
ORIGIN = os.getenv('WEBAPP_ORIGIN', '').rstrip('/')
if not TOKEN or not CHAT or not ORIGIN:
    raise SystemExit('Configure BOT_TOKEN, LOG_CHAT_ID and WEBAPP_ORIGIN in .env')
try:
    CHAT = int(CHAT)
    origin = urlsplit(ORIGIN)
    if origin.scheme != 'https' or not origin.netloc or origin.path or origin.query or origin.fragment:
        raise ValueError('invalid origin')
except ValueError as exc:
    raise SystemExit('LOG_CHAT_ID must be numeric; WEBAPP_ORIGIN must be an HTTPS origin without a path') from exc


def verified_user(init_data):
    pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
    if len({key for key, _ in pairs}) != len(pairs):
        raise ValueError('duplicate fields')
    fields = dict(pairs)
    received = fields.pop('hash')
    check = '\n'.join(f'{key}={value}' for key, value in sorted(fields.items()))
    secret = hmac.new(b'WebAppData', TOKEN.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        raise ValueError('invalid signature')
    age = time.time() - int(fields['auth_date'])
    if age < -60 or age > 86400:
        raise ValueError('expired data')
    user = json.loads(fields['user'])
    if not isinstance(user.get('id'), int):
        raise ValueError('invalid user')
    return user


def cors(request, response):
    if request.headers.get('Origin') == ORIGIN:
        response.headers['Access-Control-Allow-Origin'] = ORIGIN
        response.headers['Vary'] = 'Origin'
    return response


async def event(request):
    if request.headers.get('Origin') != ORIGIN:
        return web.Response(status=403)
    try:
        data = await request.json()
        if not isinstance(data, dict) or set(data) != {'initData'} or not isinstance(data['initData'], str) or len(data['initData']) > 8192:
            raise ValueError('invalid payload')
        user = verified_user(data['initData'])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return cors(request, web.json_response({'ok': False}, status=401))
    username = user.get('username')
    username = '@' + username if isinstance(username, str) and username else 'не указан'
    try:
        await request.app['bot'].send_message(CHAT, f'🔎 Начата проверка ликвидности\nTelegram: {escape(username)}\nID: {user["id"]}', parse_mode='HTML')
    except Exception:
        logging.exception('Could not send group event')
        return cors(request, web.json_response({'ok': False}, status=502))
    return cors(request, web.json_response({'ok': True}))


async def options(request):
    response = cors(request, web.Response(status=204))
    response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response


async def lifecycle(app):
    app['bot'] = Bot(TOKEN)
    yield
    await app['bot'].session.close()


app = web.Application(client_max_size=16384)
app.cleanup_ctx.append(lifecycle)
app.router.add_post('/api/liquidity-request', event)
app.router.add_options('/api/liquidity-request', options)
web.run_app(app, host='0.0.0.0', port=int(os.getenv('PORT', '8080')))
