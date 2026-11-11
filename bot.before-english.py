"""Portals Check bot.

Set BOT_TOKEN, WEBAPP_URL and LOG_CHAT_ID as environment variables.
The Partner API key is deliberately never written to the log chat.
"""
import asyncio
import json
import logging
import os
from html import escape
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)

load_dotenv(Path(__file__).with_name(".env"))
TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")
LOG_CHAT_ID = os.getenv("LOG_CHAT_ID")
VIDEO = Path(__file__).with_name("portals-card-ru-60fps.mp4")

if not TOKEN or not WEBAPP_URL or not WEBAPP_URL.startswith("https://") or not LOG_CHAT_ID:
    raise SystemExit("Set BOT_TOKEN, WEBAPP_URL (HTTPS), and LOG_CHAT_ID before starting the bot.")

try:
    LOG_CHAT_ID = int(LOG_CHAT_ID)
except ValueError as exc:
    raise SystemExit("LOG_CHAT_ID must be a numeric Telegram chat ID.") from exc

dp = Dispatcher()
TEXT = {
    "ru": {
        "caption": "<b><tg-emoji emoji-id=\"5938252440926163756\">✅</tg-emoji> Portals Check</b>\n\nПривет! Покажу, сколько реально стоит твой профиль на Portals.\n\n<tg-emoji emoji-id=\"6037175527846975726\">🎁</tg-emoji> Ликвидность каждого подарка\n<tg-emoji emoji-id=\"5890848474563352982\">💰</tg-emoji> Что продать сейчас — и за сколько\n<tg-emoji emoji-id=\"5836866396419530588\">⚒</tg-emoji> Что лучше придержать",
        "open": "Открыть Portals Check",
        "language": "🇬🇧 English",
    },
    "en": {
        "caption": "<b><tg-emoji emoji-id=\"5938252440926163756\">✅</tg-emoji> Portals Check</b>\n\nHi! I’ll show you what your Portals profile is really worth.\n\n<tg-emoji emoji-id=\"6037175527846975726\">🎁</tg-emoji> Liquidity of each gift\n<tg-emoji emoji-id=\"5890848474563352982\">💰</tg-emoji> What to sell now — and for how much\n<tg-emoji emoji-id=\"5836866396419530588\">⚒</tg-emoji> What to hold",
        "open": "Open Portals Check",
        "language": "🇷🇺 Русский",
    },
}


def keyboard(lang: str) -> InlineKeyboardMarkup:
    other = "en" if lang == "ru" else "ru"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=TEXT[lang]["open"], web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton(text=TEXT[lang]["language"], callback_data=f"lang:{other}")],
    ])


def user_line(message: Message) -> str:
    user = message.from_user
    username = f"@{user.username}" if user and user.username else "без username"
    name = user.full_name if user else "неизвестный пользователь"
    user_id = user.id if user else "?"
    return f"{escape(name)} ({escape(username)}, ID: <code>{user_id}</code>)"


async def write_log(bot: Bot, title: str, message: Message, extra: str = "") -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    body = f"<b>{title}</b>\n{user_line(message)}\nВремя: <code>{now}</code>"
    if extra:
        body += f"\n{extra}"
    await bot.send_message(LOG_CHAT_ID, body)


@dp.message(CommandStart())
async def start(message: Message, bot: Bot) -> None:
    await write_log(bot, "🚀 Запуск Portals Check", message)
    lang = "ru"
    if VIDEO.exists():
        await message.answer_animation(
            BufferedInputFile(VIDEO.read_bytes(), filename=VIDEO.name),
            caption=TEXT[lang]["caption"],
            reply_markup=keyboard(lang),
        )
    else:
        await message.answer(TEXT[lang]["caption"], reply_markup=keyboard(lang))


@dp.callback_query(F.data.startswith("lang:"))
async def language(callback: CallbackQuery) -> None:
    lang = callback.data.split(":", 1)[1]
    if lang not in TEXT or not callback.message:
        await callback.answer()
        return
    if callback.message.video or callback.message.animation:
        await callback.message.edit_caption(caption=TEXT[lang]["caption"], reply_markup=keyboard(lang))
    else:
        await callback.message.edit_text(TEXT[lang]["caption"], reply_markup=keyboard(lang))
    await callback.answer()


@dp.message(F.web_app_data)
async def web_app_data(message: Message, bot: Bot) -> None:
    try:
        data = json.loads(message.web_app_data.data)
    except (TypeError, json.JSONDecodeError):
        data = {}
    if data.get("event") != "liquidity_requested":
        return
    username = str(data.get("username", "")).strip()
    # Never include api_key or any secret value in this message.
    await write_log(
        bot,
        "🔎 Запрос проверки ликвидности",
        message,
        f"Username из формы: <code>{escape(username or 'не указан')}</code>\nPartner API key: <b>не передаётся в лог</b>",
    )
    await message.answer("⏳ Запрос принят. Загружаем ликвидность…")


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    async with Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML)) as bot:
        await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
