#!/usr/bin/env python3
_last_reuse_debug_msg = ""
"""
Flow Bot Manual Generate Gmail - Perfected Edition v4 (Custom Scan Count & Freedom Mode)
Session mode: /session -> bot drives the workflow with inline buttons.
"""

import asyncio
import csv
import functools
import io
import json
import os
import random
import re
import socket
import threading
import time
import uuid
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

import httpx
from faker import Faker
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

fake = Faker(["pt_BR"])

_BR_FIRST_MALE = [
    "lucas", "mateus", "gabriel", "rafael", "pedro", "gustavo", "bruno", "felipe",
    "thiago", "leonardo", "henrique", "daniel", "anderson", "rodrigo", "marcelo",
    "diego", "vinicius", "caio", "arthur", "bernardo", "enzo", "nicolas", "miguel",
    "samuel", "davi", "joao", "carlos", "eduardo", "fernando", "marcos", "andre",
    "douglas", "fabio", "paulo", "alex", "hugo", "igor", "renan", "luan", "otavio",
    "guilherme", "matheus", "leandro", "murilo", "heitor", "lorenzo", "theo",
    "yuri", "raul", "emanoel", "wallace", "jefferson", "alan", "julio", "cesar",
    "adriano", "cristiano", "romario", "ronaldo", "claudio", "sergio", "jorge",
]

_BR_FIRST_FEMALE = [
    "ana", "maria", "julia", "beatriz", "larissa", "amanda", "leticia", "camila",
    "bruna", "fernanda", "gabriela", "isabela", "carolina", "mariana", "patricia",
    "vanessa", "tatiana", "raquel", "natalia", "aline", "jessica", "priscila",
    "vitoria", "luana", "bianca", "sofia", "valentina", "helena", "alice", "laura",
    "manuela", "livia", "giovanna", "isadora", "rafaela", "renata", "debora",
    "sandra", "simone", "adriana", "claudia", "monica", "lucia", "rosa", "eliana",
    "sabrina", "daniela", "talita", "milena", "lorena", "carla", "flavia", "paula",
]

_BR_LAST = [
    "silva", "santos", "oliveira", "souza", "pereira", "costa", "rodrigues",
    "almeida", "nascimento", "lima", "araujo", "fernandes", "carvalho", "gomes",
    "martins", "rocha", "ribeiro", "alves", "monteiro", "mendes", "barros",
    "freitas", "barbosa", "pinto", "moura", "cavalcanti", "dias", "campos",
    "cardoso", "teixeira", "vieira", "nunes", "moreira", "batista", "lopes",
    "correia", "ramos", "machado", "azevedo", "pires", "castro", "melo",
    "farias", "miranda", "cunha", "reis", "andrade", "marques", "sampaio",
    "borges", "amorim", "lacerda", "duarte", "fonseca", "siqueira", "vasconcelos",
    "aguiar", "nogueira", "brito", "tavares", "resende", "coelho", "magalhaes",
]

# --- Create Async Lock for Async I/O & File Locks ---
_file_lock = asyncio.Lock()

DATA_DIR = Path(os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "bot_data")))
DATA_DIR.mkdir(exist_ok=True)
ACCOUNTS_FILE = DATA_DIR / "accounts.json"
NUMBERS_FILE = DATA_DIR / "numbers.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
SESSION_FILE = DATA_DIR / "session.json"

SMSCODE_BASE = "https://api.smscode.gg/v1"
BAD_WORDS = {"kontol", "memek", "anjing", "bangsat", "babi", "setan", "fuck", "shit", "dick", "pussy", "ass", "bitch", "damn"}


def md_escape(text: str) -> str:
    """Escape Telegram Markdown V1 special characters in dynamic text."""
    if not text:
        return ""
    for ch in ('_', '*', '`', '['):
        text = str(text).replace(ch, '\\' + ch)
    return text


DEFAULT_SETTINGS = {
    # --- FlameProxies Configuration (Ultra Pool 2 + Fast Mode All-Brazil) ---
    "proxy_user": "",           # Base username only, params appended automatically
    "proxy_pass": "",           # Password
    "proxy_host": "proxy.flameproxies.com",
    "proxy_port": 8989,         # Default internal probe port di Railway (HTTP Connect Tunnel: anti-stuck)
    "proxy_protocol": "http",   # http untuk probe internal Railway, SOCKS5 1080 untuk export GoLogin
    "proxy_param_target": "user",
    "proxy_pool": "2",          # 1 = Performance, 2 = Ultra
    "proxy_mode": "fast",       # fast = low-latency fiber peers only
    "proxy_session_time": 100,  # Session TTL in minutes (FlameProxies -time-100)
    "ip_hunter_country": "br",  # Brazil (All-Brazil Vivo pool)
    "ip_hunter_isp": "vivo",    # Lock ISP: vivo only (AS26599)
    "allowed_users": [],
    "ipqs_api_key": "",
    "iphub_api_key": "",
    "proxycheck_api_key": "",
}


async def load_json_async(path, default=None):
    if default is None:
        default = []
    async with _file_lock:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return default


async def save_json_async(path, data):
    async with _file_lock:
        temp_path = path.with_suffix('.tmp')
        temp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        temp_path.replace(path)


async def get_settings_async():
    data = await load_json_async(SETTINGS_FILE, DEFAULT_SETTINGS.copy())
    merged = DEFAULT_SETTINGS.copy()
    if isinstance(data, dict):
        merged.update(data)
    if os.environ.get("BOT_TOKEN"):
        merged["bot_token"] = os.environ["BOT_TOKEN"]
    if os.environ.get("SMSCODE_TOKEN"):
        merged["smscode_token"] = os.environ["SMSCODE_TOKEN"]
    if os.environ.get("PROXY_USER"):
        merged["proxy_user"] = _clean_proxy_username(os.environ["PROXY_USER"])
    if os.environ.get("PROXY_PASS"):
        merged["proxy_pass"] = os.environ["PROXY_PASS"].strip()
    if os.environ.get("PROXY_HOST"):
        merged["proxy_host"] = os.environ["PROXY_HOST"].strip()
    if os.environ.get("PROXY_POOL"):
        merged["proxy_pool"] = os.environ["PROXY_POOL"].strip()
    if os.environ.get("PROXY_MODE"):
        merged["proxy_mode"] = os.environ["PROXY_MODE"].strip()
    if os.environ.get("PROXY_TIME"):
        try:
            merged["proxy_session_time"] = int(os.environ["PROXY_TIME"])
        except ValueError:
            pass
    if os.environ.get("ALLOWED_USER_ID"):
        try:
            uid = int(os.environ["ALLOWED_USER_ID"])
            if uid not in merged.get("allowed_users", []):
                merged["allowed_users"] = merged.get("allowed_users", []) + [uid]
        except ValueError:
            pass
    return merged


async def save_settings_async(s):
    merged = DEFAULT_SETTINGS.copy()
    merged.update(s)
    await save_json_async(SETTINGS_FILE, merged)


async def get_accounts_async():
    return await load_json_async(ACCOUNTS_FILE, [])


async def save_accounts_async(accs):
    await save_json_async(ACCOUNTS_FILE, accs)


async def get_numbers_async():
    return await load_json_async(NUMBERS_FILE, [])


async def save_numbers_async(nums):
    await save_json_async(NUMBERS_FILE, nums)


async def get_session_async():
    return await load_json_async(SESSION_FILE, {})


async def save_session_async(s):
    await save_json_async(SESSION_FILE, s)


def progress_bar(done, total, width=20):
    if total <= 0:
        return "░" * width
    fill = round((done / total) * width)
    return "█" * fill + "░" * (width - fill)


def check_auth(func):
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        s = await get_settings_async()
        allowed = s.get("allowed_users", [])
        user = update.effective_user.id if update.effective_user else None
        
        if not allowed or user not in allowed:
            target = update.message or (update.callback_query.message if update.callback_query else None)
            if target:
                await target.reply_text("⛔ Kamu tidak punya akses ke bot ini.")
            return
        return await func(update, context)
    return wrapper


def generate_emails(count, keyword, position="bebas", password="", no_kasar=True):
    results = []
    seen_emails = set()
    all_firsts = _BR_FIRST_MALE + _BR_FIRST_FEMALE
    attempts = 0
    while len(results) < count and attempts < count * 50:
        attempts += 1
        first = random.choice(all_firsts)
        last = random.choice(_BR_LAST)

        sep = random.choice(["", ".", "_"])
        digits = str(random.randint(10, 9999))
        suffix = random.choice([digits, str(random.randint(1990, 2006)), digits + random.choice(["", "br", "sp"])])

        if position == "depan":
            username = keyword + sep + first + last + suffix
        elif position == "belakang":
            username = first + last + sep + keyword + suffix
        elif position == "tengah":
            username = first + sep + keyword + sep + last + suffix
        else:
            parts = [first + last, keyword]
            random.shuffle(parts)
            username = sep.join(parts) + suffix

        username = username.replace(" ", "").replace(".", "").replace("_", "").lower()
        if no_kasar and any(w in username for w in BAD_WORDS):
            continue
        email = f"{username}@gmail.com"

        if email in seen_emails:
            continue

        seen_emails.add(email)
        results.append({
            "email": email,
            "password": password,
            "first_name": first.capitalize(),
            "last_name": last.capitalize(),
        })
    return results


async def add_account_async(email, password, first_name="", last_name="", status="queued"):
    accounts = await get_accounts_async()
    acc = {
        "id": str(uuid.uuid4())[:8],
        "email": email,
        "password": password,
        "first_name": first_name,
        "last_name": last_name,
        "phone": "",
        "order_id": None,
        "status": status,
        "created_at": datetime.now().isoformat(),
        "notes": "",
    }
    accounts.append(acc)
    await save_accounts_async(accounts)
    return acc


async def update_account_async(account_id, updates):
    accounts = await get_accounts_async()
    for acc in accounts:
        if acc["id"] == account_id:
            acc.update(updates)
            await save_accounts_async(accounts)
            return acc
    return None


async def get_account_async(account_id):
    for acc in await get_accounts_async():
        if acc["id"] == account_id:
            return acc
    return None


async def next_queued_account_async():
    accounts = await get_accounts_async()
    for acc in accounts:
        if acc["status"] == "queued":
            acc["status"] = "creating"
            await save_accounts_async(accounts)
            return acc
    return None


async def get_max_codes_async():
    session = await get_session_async()
    total = session.get("total") if session else None
    if total and total > 0:
        return min(total, 5)
    s = await get_settings_async()
    preset_c = s.get("preset_count")
    if preset_c and preset_c > 0:
        return min(preset_c, 5)
    return s.get("max_codes_per_number", 5)


async def get_active_number_async():
    global _last_reuse_debug_msg
    numbers = await get_numbers_async()
    max_codes = await get_max_codes_async()
    now = datetime.now()
    debug_logs = []
    if not numbers:
        debug_logs.append("DB kosong")
        
    for n in numbers:
        phone = n.get('phone', '?')
        if not n.get("can_reuse"):
            debug_logs.append(f"Nomor {phone} nonaktif")
            continue
        if n.get("codes_used", 0) >= max_codes:
            debug_logs.append(f"Nomor {phone} penuh")
            continue
            
        first_used_str = n.get("first_used")
        if first_used_str:
            try:
                first_used = datetime.fromisoformat(first_used_str)
                diff_minutes = (now - first_used).total_seconds() / 60
                if diff_minutes > 18:
                    debug_logs.append(f"Nomor {phone} expired")
                    continue
            except Exception as e:
                debug_logs.append(f"Nomor {phone} error time: {e}")
                pass
                
        _last_reuse_debug_msg = f"Reused {phone}"
        return n

    _last_reuse_debug_msg = " | ".join(debug_logs) if debug_logs else "DB nomor kosong"
    return None


async def mark_number_exhausted_async(order_id):
    numbers = await get_numbers_async()
    for n in numbers:
        if str(n.get("order_id")) == str(order_id):
            n["can_reuse"] = False
    await save_numbers_async(numbers)


async def track_number_usage_async(phone, order_id, account_email=None, country=None):
    numbers = await get_numbers_async()
    max_codes = await get_max_codes_async()
    existing = next((n for n in numbers if str(n.get("phone")) == str(phone)), None)
    if existing:
        existing["codes_used"] += 1
        existing["accounts"].append({"email": account_email, "order_id": order_id, "time": datetime.now().isoformat()})
        existing["can_reuse"] = existing["codes_used"] < max_codes
        if country:
            existing["country"] = country
        await save_numbers_async(numbers)
        return existing
    new_n = {
        "phone": phone,
        "order_id": order_id,
        "codes_used": 1,
        "max_codes": max_codes,
        "can_reuse": True,
        "country": country or "Brazil",
        "accounts": [{"email": account_email, "order_id": order_id, "time": datetime.now().isoformat()}],
        "first_used": datetime.now().isoformat(),
    }
    numbers.append(new_n)
    await save_numbers_async(numbers)
    return new_n


async def sms_headers_async():
    s = await get_settings_async()
    return {"Authorization": f"Bearer {s['smscode_token']}", "Content-Type": "application/json"}


async def sms_balance_async():
    headers = await sms_headers_async()
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(f"{SMSCODE_BASE}/balance", headers=headers)
        return r.json()


async def sms_create_order_async(catalog_product_id=None, product_id=None, min_price=None, max_price=None, policy=None, operator_id=None):
    body = {"quantity": 1}
    if product_id is not None:
        body["product_id"] = int(product_id)
    elif catalog_product_id is not None:
        body["catalog_product_id"] = int(catalog_product_id)
        if min_price is not None:
            body["min_price"] = int(min_price)
        if max_price is not None:
            body["max_price"] = int(max_price)
        if policy:
            body["policy"] = policy
        if operator_id is not None:
            body["operator_id"] = int(operator_id)
    else:
        return {"success": False, "error": {"message": "Need catalog_product_id or product_id"}}

    headers = await sms_headers_async()
    headers["Idempotency-Key"] = str(uuid.uuid4())
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            r = await client.post(f"{SMSCODE_BASE}/orders/create", headers=headers, json=body)
            return r.json()
        except Exception as e:
            return {"success": False, "error": {"message": f"NetworkError: {e}"}}


async def sms_get_order_async(order_id, after_code=None):
    url = f"{SMSCODE_BASE}/orders/{order_id}"
    if after_code:
        url += f"?after_code={after_code}"
    headers = await sms_headers_async()
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            r = await client.get(url, headers=headers)
            try:
                return r.json()
            except Exception:
                return {"success": False, "error": {"message": f"Bad response ({r.status_code}): {r.text[:100]}"}}
        except Exception as e:
            return {"success": False, "error": {"message": f"NetworkError: {e}"}}


async def sms_finish_order_async(order_id):
    try:
        oid = int(order_id)
    except (ValueError, TypeError):
        return {"success": False, "error": {"message": f"Invalid order_id: {order_id}"}}
    headers = await sms_headers_async()
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(f"{SMSCODE_BASE}/orders/finish", headers=headers, json={"id": oid})
        try:
            return r.json()
        except Exception:
            return {"success": r.status_code == 200, "status_code": r.status_code, "body": r.text[:200]}


async def sms_cancel_order_async(order_id):
    try:
        oid = int(order_id)
    except (ValueError, TypeError):
        return {"success": False, "error": {"message": f"Invalid order_id: {order_id}"}}
    headers = await sms_headers_async()
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(f"{SMSCODE_BASE}/orders/cancel", headers=headers, json={"id": oid})
        try:
            return r.json()
        except Exception:
            return {"success": r.status_code == 200, "status_code": r.status_code, "body": r.text[:200]}


async def sms_resend_async(order_id):
    try:
        oid = int(order_id)
    except (ValueError, TypeError):
        return {"success": False, "error": {"message": f"Invalid order_id: {order_id}"}}
    headers = await sms_headers_async()
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(f"{SMSCODE_BASE}/orders/resend", headers=headers, json={"id": oid})
        try:
            return r.json()
        except Exception:
            return {"success": r.status_code == 200, "status_code": r.status_code, "body": r.text[:200]}


async def export_to_google_sheets_async(acc):
    settings = await get_settings_async()
    url = settings.get("google_sheets_url")
    if not url:
        return
    payload = {
        "email": acc.get("email"),
        "password": acc.get("password"),
        "first_name": acc.get("first_name"),
        "phone": acc.get("phone"),
        "status": acc.get("status")
    }
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            await client.post(url, json=payload)
        except Exception as e:
            print(f"Error exporting to Google Sheets: {e}")


async def format_account_card_async(acc, session):
    username = acc["email"].replace("@gmail.com", "")
    phone = acc.get("phone") or "-"
    first_name = acc.get("first_name", "")
    last_name = acc.get("last_name", "")
    password = acc.get("password", "")
    country = acc.get("country", "Brazil")

    uses = session.get("current_number_uses", 1)
    max_codes = await get_max_codes_async()
    reuse_tag = f" ♻️ _(Pakai ke-{uses}/{max_codes})_" if uses > 1 else f" _(Baru: 1/{max_codes})_"

    debug_note = ""
    if uses == 1 and _last_reuse_debug_msg and "Reused" not in _last_reuse_debug_msg:
        debug_note = f"\n\nℹ️ _[Info Sistem]: {md_escape(_last_reuse_debug_msg)}_"

    return (
        f"📋 *DATA AKUN*\n\n"
        f"📞 Nomor ({country}):{reuse_tag}\n`{phone}`\n\n"
        f"👤 Nama Depan:\n`{first_name}`\n\n"
        f"👤 Nama Belakang:\n`{last_name}`\n\n"
        f"📧 Username:\n`{username}`\n\n"
        f"🔑 Password:\n`{password}`{debug_note}\n\n"
        f"🚀 *Daftar via OAuth (Anti-Banned):*\n"
        f"🎵 `https://www.spotify.com/br-pt/signup`\n"
        f"🎨 `https://www.canva.com/pt_br/signup`\n\n"
        f"➡️ _Buka link di GoLogin, klik 'Continuar com o Google'_\n"
        f"➡️ _Input data di atas, lalu tap *📲 Minta OTP*_"
    )


def session_keyboard(acc_id, order_id, waiting_otp=False):
    oid = order_id or "none"
    if waiting_otp:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Berhasil", callback_data=f"sess_done:{acc_id}:{oid}"), InlineKeyboardButton("❌ Gagal", callback_data=f"sess_fail:{acc_id}:{oid}")],
            [InlineKeyboardButton("🔄 Resend SMS", callback_data=f"sess_resend:{acc_id}:{oid}"), InlineKeyboardButton("⏭ Skip", callback_data=f"sess_skip:{acc_id}:{oid}")],
            [InlineKeyboardButton("❌ Ganti Nomor", callback_data=f"sess_change_number:{acc_id}:{oid}")],
            [InlineKeyboardButton("🛑 Stop Sesi", callback_data="sess_stop"), InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")],
        ])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📲 Minta OTP", callback_data=f"sess_otp:{acc_id}:{oid}"), InlineKeyboardButton("⏭ Skip", callback_data=f"sess_skip:{acc_id}:{oid}")],
        [InlineKeyboardButton("❌ Ganti Nomor", callback_data=f"sess_change_number:{acc_id}:{oid}")],
        [InlineKeyboardButton("🛑 Stop Sesi", callback_data="sess_stop"), InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")],
    ])


KEYWORD, PASSWORD, COUNT, POSITION = range(4)

async def wizard_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["setup"] = {}
    await query.edit_message_text("💬 Masukkan *Keyword* (contoh: rabe):", parse_mode="Markdown")
    return KEYWORD

async def wizard_keyword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["setup"]["keyword"] = update.message.text.strip().lower()
    await update.message.reply_text("🔑 Masukkan *Password* untuk semua akun:")
    return PASSWORD

async def wizard_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["setup"]["password"] = update.message.text.strip()
    await update.message.reply_text("🔢 Masukkan *Jumlah Akun* (contoh: 5):")
    return COUNT

async def wizard_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    count = int(text) if text.isdigit() else 5
    if count > 100:
        count = 100
    context.user_data["setup"]["count"] = count
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Depan", callback_data="pos_depan"), InlineKeyboardButton("Belakang", callback_data="pos_belakang")],
        [InlineKeyboardButton("Tengah", callback_data="pos_tengah"), InlineKeyboardButton("Bebas", callback_data="pos_bebas")],
    ])
    await update.message.reply_text("📍 Pilih *Posisi Keyword*:", reply_markup=kb)
    return POSITION

async def wizard_position(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pos = query.data.replace("pos_", "")
    setup = context.user_data.get("setup", {})
    keyword = setup.get("keyword", "rabe")
    password = setup.get("password", "aass1122")
    count = setup.get("count", 5)
    position = pos

    settings = await get_settings_async()
    if not settings.get("smscode_token"):
        await query.edit_message_text("⚠️ Token SMSCode belum diset. Pakai `/settoken TOKEN` dulu.", parse_mode="Markdown", reply_markup=back_kb())
        return ConversationHandler.END

    results = generate_emails(count, keyword, position, password)
    await save_accounts_async([])
    for r in results:
        await add_account_async(r["email"], r["password"], r["first_name"], r["last_name"])

    await save_numbers_async([])

    session = {
        "active": True,
        "paused": True,
        "keyword": keyword,
        "password": password,
        "position": position,
        "total": len(results),
        "done": 0,
        "failed": 0,
        "skipped": 0,
        "started_at": datetime.now().isoformat(),
        "current_account_id": None,
        "current_order_id": None,
        "current_number_uses": 0,
        "waiting_otp": False,
        "selected_country_id": SMSCODE_COUNTRIES[0]["id"],
        "selected_product_id": None,
    }
    await save_session_async(session)
    country = SMSCODE_COUNTRIES[0]
    await query.edit_message_text(
        f"✅ Sesi dibuat ({len(results)} akun).\nKeyword: `{keyword}` | Posisi: `{position}` | Pass: `{password}`\n\n"
        f"🌍 Negara: {country['flag']} *{country['name']}*\n"
        f"⚡ Bypass Mode (Best Success) aktif\n\n"
        f"🚀 Sesi dimulai otomatis...",
        parse_mode="Markdown",
    )
    await send_next_session_card(query.message.chat, context.bot)
    return ConversationHandler.END

async def wizard_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Wizard dibatalkan.", reply_markup=home_menu_keyboard())
    return ConversationHandler.END

def home_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ Mulai Cepat (Preset)", callback_data="menu_preset_start")],
        [InlineKeyboardButton("📌 Atur Preset", callback_data="menu_preset_config")],
        [InlineKeyboardButton("📊 Status", callback_data="menu_status"), InlineKeyboardButton("💰 Saldo", callback_data="menu_balance")],
        [InlineKeyboardButton("📥 Export", callback_data="menu_export"), InlineKeyboardButton("🚀 Daftar OAuth", callback_data="sess_warmup")],
        [InlineKeyboardButton("🌐 IP Hunter", callback_data="menu_ip_hunter")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="menu_settings"), InlineKeyboardButton("🧹 Clear", callback_data="menu_clear")],
    ])


def back_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")]])


SMSCODE_COUNTRIES = [
    {"id": 74, "name": "Brazil", "flag": "🇧🇷", "price_min": 0, "price_max": 2500},
]

SMS_PRICE_MIN = 0
SMS_PRICE_MAX = 2500


def country_selection_keyboard():
    rows = []
    for c in SMSCODE_COUNTRIES:
        rows.append([InlineKeyboardButton(f"{c['flag']} {c['name']}", callback_data=f"country_select:{c['id']}")])
    rows.append([InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")])
    return InlineKeyboardMarkup(rows)


async def ensure_number_for_account_async(acc):
    active = await get_active_number_async()
    if active:
        tracked = await track_number_usage_async(active["phone"], active["order_id"], acc["email"])
        await update_account_async(acc["id"], {"phone": active["phone"], "order_id": active["order_id"], "status": "sms_pending", "country": active.get("country", "Brazil")})
        max_c = await get_max_codes_async()
        print(f"[REUSE_NUMBER] {active['phone']} order={active['order_id']} uses={tracked['codes_used']}/{max_c} for {acc['email']}")
        return {"reused": True, "phone": active["phone"], "order_id": active["order_id"], "uses": tracked["codes_used"], "country": active.get("country", "Brazil")}

    session = await get_session_async()
    selected_country_id = session.get("selected_country_id") if session else None
    country = next((c for c in SMSCODE_COUNTRIES if c["id"] == selected_country_id), SMSCODE_COUNTRIES[0])
    country_id = country["id"]

    if country_id == 74:
        PRICE_MIN = 1000
        PRICE_MAX = 1250
        target_operator_id = 347
    else:
        PRICE_MIN = 0
        PRICE_MAX = 3500
        target_operator_id = None
        
    platform_id = 5

    catalog_product_id = None
    direct_fallback_products = []
    headers = await sms_headers_async()
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            r = await client.get(
                f"{SMSCODE_BASE}/catalog/products?country_id={country_id}&platform_id={platform_id}&limit=200",
                headers=headers
            )
            if r.status_code != 200:
                raise RuntimeError(f"Catalog HTTP {r.status_code}")
            resp_json = r.json()
            raw_data = resp_json.get("data", [])
            if isinstance(raw_data, dict):
                products = raw_data.get("products", [])
            else:
                products = raw_data
            for p in products:
                cpid = p.get("catalog_product_id")
                if cpid:
                    catalog_product_id = cpid
                    break
            direct_fallback_products = [
                p for p in products
                if PRICE_MIN <= p.get("price", 0) <= PRICE_MAX 
                and p.get("available", 0) > 0 
                and p.get("id")
                and (p.get("operator_id") == target_operator_id if (target_operator_id is not None and p.get("operator_id") is not None) else True)
            ]
            direct_fallback_products.sort(key=lambda x: x.get("price", 0))
        except Exception as e:
            raise RuntimeError(f"Gagal fetch catalog: {e}")

    if not catalog_product_id and not direct_fallback_products:
        raise RuntimeError(f"Tidak ada produk Google Brazil.")

    if catalog_product_id:
        result = await sms_create_order_async(
            catalog_product_id=catalog_product_id,
            min_price=PRICE_MIN,
            max_price=PRICE_MAX,
            policy="cheapest",
            operator_id=target_operator_id
        )
        if result.get("success"):
            orders = result.get("data", {}).get("orders", [])
            if orders:
                order = orders[0]
                phone = order.get("phone_number", "")
                order_id = order["id"]
                await update_account_async(acc["id"], {"phone": phone, "order_id": order_id, "status": "sms_pending", "country": country["name"]})
                tracked = await track_number_usage_async(phone, order_id, acc["email"], country=country["name"])
                return {"reused": False, "phone": phone, "order_id": order_id, "uses": tracked["codes_used"], "country": country["name"], "flag": country["flag"]}

    if direct_fallback_products:
        for p in direct_fallback_products[:5]:
            pid = p["id"]
            result = await sms_create_order_async(product_id=pid)
            if result.get("success"):
                orders = result.get("data", {}).get("orders", [])
                if orders:
                    order = orders[0]
                    phone = order.get("phone_number", "")
                    order_id = order["id"]
                    await update_account_async(acc["id"], {"phone": phone, "order_id": order_id, "status": "sms_pending", "country": country["name"]})
                    tracked = await track_number_usage_async(phone, order_id, acc["email"], country=country["name"])
                    return {"reused": False, "phone": phone, "order_id": order_id, "uses": tracked["codes_used"], "country": country["name"], "flag": country["flag"]}

    any_vivo_products = [
        p for p in products
        if p.get("available", 0) > 0 and p.get("id")
        and (p.get("operator_id") == target_operator_id if (target_operator_id is not None and p.get("operator_id") is not None) else True)
    ]
    any_vivo_products.sort(key=lambda x: x.get("price", 0))
    for p in any_vivo_products[:3]:
        pid = p["id"]
        result = await sms_create_order_async(product_id=pid)
        if result.get("success"):
            orders = result.get("data", {}).get("orders", [])
            if orders:
                order = orders[0]
                phone = order.get("phone_number", "")
                order_id = order["id"]
                await update_account_async(acc["id"], {"phone": phone, "order_id": order_id, "status": "sms_pending", "country": country["name"]})
                tracked = await track_number_usage_async(phone, order_id, acc["email"], country=country["name"])
                return {"reused": False, "phone": phone, "order_id": order_id, "uses": tracked["codes_used"], "country": country["name"], "flag": country["flag"]}

    raise RuntimeError(f"Gagal order nomor Brazil (Vivo S.A.). Stok di SMSCode sedang habis. Coba beberapa saat lagi.")


async def send_next_session_card(chat, bot_instance):
    session = await get_session_async()
    if not session or not session.get("active"):
        await chat.send_message("Tidak ada sesi aktif. Gunakan /session atau /go")
        return
    processed = session.get("done", 0) + session.get("failed", 0) + session.get("skipped", 0)
    total = session.get("total", 0)
    if total > 0 and processed >= total:
        session["active"] = False
        await save_session_async(session)
        await chat.send_message(
            f"🎉 *SESI SELESAI!*\n\n✅ Berhasil: *{session.get('done',0)}*\n❌ Gagal: *{session.get('failed',0)}*\n⏭ Dilewati: *{session.get('skipped',0)}*",
            parse_mode="Markdown",
            reply_markup=home_menu_keyboard()
        )
        return
    acc = await next_queued_account_async()
    if not acc:
        session["active"] = False
        await save_session_async(session)
        await chat.send_message(
            f"🎉 *SESI SELESAI!*\n\n✅ Berhasil: *{session.get('done',0)}*\n❌ Gagal: *{session.get('failed',0)}*\n⏭ Dilewati: *{session.get('skipped',0)}*",
            parse_mode="Markdown",
            reply_markup=home_menu_keyboard()
        )
        return
    session["current_account_id"] = acc["id"]
    await save_session_async(session)
    try:
        number_info = await ensure_number_for_account_async(acc)
    except Exception as e:
        await update_account_async(acc["id"], {"status": "failed", "notes": f"number_error: {e}"})
        session["failed"] = session.get("failed", 0) + 1
        await save_session_async(session)
        await chat.send_message(f"❌ Gagal ambil nomor: {e}")
        await send_next_session_card(chat, bot_instance)
        return
    updated_acc = await get_account_async(acc["id"])
    if updated_acc:
        acc = updated_acc
    session["current_order_id"] = acc.get("order_id")
    session["current_number_uses"] = number_info["uses"]
    session["waiting_otp"] = False
    await save_session_async(session)
    
    card_text = await format_account_card_async(acc, session)
    try:
        await chat.send_message(
            card_text, 
            parse_mode="Markdown", 
            reply_markup=session_keyboard(acc["id"], acc.get("order_id"), False)
        )
    except Exception as e:
        try:
            await chat.send_message(
                card_text, 
                reply_markup=session_keyboard(acc["id"], acc.get("order_id"), False)
            )
        except Exception as e2:
            print(f"[FATAL_SEND_FAIL] Failed to send text: {e2}")


@check_auth
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Create Your Gmail Fastest 👾",
        parse_mode="Markdown",
        reply_markup=home_menu_keyboard(),
    )


@check_auth
async def cmd_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    if len(args) < 3:
        await update.message.reply_text(
            "❌ Format: `/session keyword jumlah password posisi`\n\nContoh: `/session rabe 20 aass1122 depan`",
            parse_mode="Markdown",
            reply_markup=back_kb()
        )
        return
    keyword = args[0].lower()
    count = int(args[1]) if args[1].isdigit() else 10
    password = args[2]
    position = args[3] if len(args) > 3 else "bebas"
    if count > 100:
        count = 100
    settings = await get_settings_async()
    if not settings.get("smscode_token"):
        await update.message.reply_text("⚠️ Token SMSCode belum diset. Pakai `/settoken TOKEN` dulu.", parse_mode="Markdown", reply_markup=back_kb())
        return
    results = generate_emails(count, keyword, position, password)
    await save_accounts_async([])
    for r in results:
        await add_account_async(r["email"], r["password"], r["first_name"], r["last_name"])
    await save_numbers_async([])
    session = {
        "active": True,
        "paused": False,
        "keyword": keyword,
        "password": password,
        "position": position,
        "total": len(results),
        "done": 0,
        "failed": 0,
        "skipped": 0,
        "started_at": datetime.now().isoformat(),
        "current_account_id": None,
        "current_order_id": None,
        "current_number_uses": 0,
        "waiting_otp": False,
        "selected_country_id": None,
        "selected_product_id": None,
    }
    await save_session_async(session)
    await update.message.reply_text(f"✅ Sesi dibuat: *{len(results)} akun*\nKeyword: `{keyword}` | Posisi: `{position}`", parse_mode="Markdown")
    await send_next_session_card(update.message.chat, context.bot)


@check_auth
async def cmd_go(update: Update, context: ContextTypes.DEFAULT_TYPE):
    settings = await get_settings_async()
    if not settings.get("smscode_token"):
        await update.message.reply_text("⚠️ Token SMSCode belum diset. Pakai `/settoken TOKEN` dulu.", parse_mode="Markdown", reply_markup=back_kb())
        return
    session = await get_session_async()
    if not session.get("active"):
        queued = [a for a in await get_accounts_async() if a["status"] == "queued"]
        if not queued:
            await update.message.reply_text("📭 Tidak ada antrian. Pakai `/session ...` atau `/generate ...` dulu.", parse_mode="Markdown", reply_markup=back_kb())
            return
        session = {
            "active": True,
            "paused": False,
            "keyword": "",
            "password": "",
            "position": "",
            "total": len(queued),
            "done": 0,
            "failed": 0,
            "skipped": 0,
            "started_at": datetime.now().isoformat(),
            "current_account_id": None,
            "current_order_id": None,
            "current_number_uses": 0,
            "waiting_otp": False,
            "selected_country_id": None,
            "selected_product_id": None,
        }
        await save_session_async(session)
    await send_next_session_card(update.message.chat, context.bot)


@check_auth
async def cmd_generate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    if len(args) < 1:
        await update.message.reply_text("❌ Format: `/generate keyword jumlah password posisi`", parse_mode="Markdown", reply_markup=back_kb())
        return
    keyword = args[0].lower()
    count = int(args[1]) if len(args) > 1 and args[1].isdigit() else 10
    password = args[2] if len(args) > 2 else ""
    position = args[3] if len(args) > 3 else "bebas"
    results = generate_emails(count, keyword, position, password)
    for r in results:
        await add_account_async(r["email"], r["password"], r["first_name"], r["last_name"])
    preview = "\n".join([f"`{x['email']}`" for x in results[:5]])
    await update.message.reply_text(f"✅ *{len(results)} akun* ditambahkan ke antrian\n\n{preview}\n\nGunakan `/go` untuk mulai.", parse_mode="Markdown", reply_markup=back_kb())


@check_auth
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = await get_session_async()
    if not session.get("active"):
        await update.message.reply_text("Tidak ada sesi aktif.", reply_markup=back_kb())
        return
    done = session.get("done", 0)
    total = session.get("total", 0)
    failed = session.get("failed", 0)
    skipped = session.get("skipped", 0)
    acc_id = session.get("current_account_id") or "-"
    order_id = session.get("current_order_id") or "-"
    pct = round((done / total) * 100) if total else 0
    bar = progress_bar(done, total)
    await update.message.reply_text(
        f"📊 *Status Sesi*\n\n`{bar}` {pct}%\n\n✅ Berhasil: *{done}*\n❌ Gagal: *{failed}*\n⏭ Dilewati: *{skipped}*\n📦 Total: *{total}*\n🆔 Current account: `{acc_id}`\n🆔 Current order: `{order_id}`\n⏸ Paused: *{session.get('paused', False)}*",
        parse_mode="Markdown",
        reply_markup=back_kb()
    )


@check_auth
async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = await get_session_async()
    if not session.get("active"):
        await update.message.reply_text("Tidak ada sesi aktif.", reply_markup=back_kb())
        return
    session["paused"] = True
    await save_session_async(session)
    await update.message.reply_text("⏸ Sesi dipause. Pakai `/resume` untuk lanjut.", parse_mode="Markdown", reply_markup=back_kb())


@check_auth
async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = await get_session_async()
    if not session.get("active"):
        await update.message.reply_text("Tidak ada sesi aktif. Pakai `/go` atau `/session`.", reply_markup=back_kb())
        return
    session["paused"] = False
    await save_session_async(session)
    await update.message.reply_text("▶️ Sesi dilanjutkan.")
    await send_next_session_card(update.message.chat, context.bot)


@check_auth
async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = await get_settings_async()
    if not s.get("smscode_token"):
        await update.message.reply_text("⚠️ Token belum diset: `/settoken TOKEN`", parse_mode="Markdown", reply_markup=back_kb())
        return
    try:
        res = await sms_balance_async()
        if res.get("success"):
            bal = res.get("data", {}).get("balance", "?")
            bal_rp = f"Rp {int(bal):,}".replace(",", ".")
            await update.message.reply_text(f"💰 Saldo SMSCode: *{bal_rp}*", parse_mode="Markdown", reply_markup=back_kb())
        else:
            await update.message.reply_text(f"❌ {res.get('error', {}).get('message', 'Unknown error')}", reply_markup=back_kb())
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}", reply_markup=back_kb())


@check_auth
async def cmd_apidebug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = ["🔍 *API Debug*\n"]
    lines.append("📋 *Services (Google-related):*")
    headers = await sms_headers_async()
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            r = await client.get(f"{SMSCODE_BASE}/catalog/services", headers=headers)
            if r.status_code == 200:
                services = r.json().get("data", [])
                for s in services:
                    name = s.get("name", "")
                    if "google" in name.lower() or "gmail" in name.lower() or "youtube" in name.lower():
                        lines.append(f"  • id=`{s.get('id')}` name=`{name}` active={s.get('active')}")
        except Exception as e:
            lines.append(f"  ❌ {e}")
    lines.append("")

    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:4000] + "\n..."
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=back_kb())


@check_auth
async def cmd_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    numbers = await get_numbers_async()
    if not numbers:
        await update.message.reply_text("📭 Belum ada riwayat nomor.", reply_markup=back_kb())
        return
    lines = []
    for n in numbers[-20:]:
        icon = "🟢" if n.get("can_reuse") else "🔴"
        lines.append(f"{icon} `{n['phone']}` — {n['codes_used']}/{n['max_codes']} akun (order `{n.get('order_id')}`)")
    await update.message.reply_text("📞 *Riwayat Nomor:*\n\n" + "\n".join(lines), parse_mode="Markdown", reply_markup=back_kb())


@check_auth
async def cmd_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    accounts = await get_accounts_async()
    if not accounts:
        await update.message.reply_text("📭 Belum ada akun.", reply_markup=back_kb())
        return
    by_status = {}
    for a in accounts:
        by_status[a['status']] = by_status.get(a['status'], 0) + 1
    text = [f"📋 *Total akun: {len(accounts)}*"]
    for k, v in by_status.items():
        text.append(f"- `{k}`: *{v}*")
    text.append("\nGunakan /export untuk download hasil.")
    await update.message.reply_text("\n".join(text), parse_mode="Markdown", reply_markup=back_kb())


@check_auth
async def cmd_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    status_filter = args[0] if args else "created"
    accounts = await get_accounts_async()
    if status_filter:
        accounts = [a for a in accounts if a["status"] == status_filter]

    if not accounts:
        await update.message.reply_text(f"📭 Tidak ada akun dengan status *{status_filter}* untuk di-export.", parse_mode="Markdown", reply_markup=back_kb())
        return

    combo = "\n".join(f"`{a['email']}`" for a in accounts)
    await update.message.reply_text(
        f"📥 *SALIN EMAIL ({len(accounts)}):*\n\n_(Tap masing-masing email untuk menyalin)_\n\n{combo}",
        parse_mode="Markdown",
        reply_markup=back_kb()
    )


@check_auth
async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = await get_settings_async()
    tok = s.get("smscode_token", "")
    tok_disp = tok[:8] + "..." + tok[-4:] if len(tok) > 12 else ("(belum diset)" if not tok else "***")
    sheet_disp = s.get("google_sheets_url", "")
    sheet_disp = "Set" if sheet_disp else "(belum diset)"
    await update.message.reply_text(
        f"⚙️ *Settings*\n\n🤖 Allowed users: `{s.get('allowed_users', [])}`\n🔑 SMS token: `{tok_disp}`\n🌍 Country ID: `{s.get('smscode_country_id', 74)}` (Brazil)\n📦 Product ID: `{s.get('smscode_product_id')}`\n🎂 Birth date: `{s.get('birth_date')}`\n👫 Gender: `{s.get('gender')}`\n📊 Google Sheets: `{sheet_disp}`\n\n📌 *Preset Aktif:*\n- Keyword: `{s.get('preset_keyword', 'rabe')}`\n- Password: `{s.get('preset_password', 'aass1122')}`\n- Jumlah: `{s.get('preset_count', 5)}`\n- Posisi: `{s.get('preset_position', 'belakang')}`\n\nUbah dengan:\n`/settoken TOKEN`\n`/setsheet URL`\n`/setpreset keyword password jumlah depan/belakang`\n`/setbirth YYYY-MM-DD`\n`/setproduct ID`\n`/setgender male`",
        parse_mode="Markdown",
        reply_markup=back_kb()
    )


@check_auth
async def cmd_setpreset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    if len(args) < 4:
        await update.message.reply_text("❌ Format: `/setpreset keyword password jumlah posisi`\nContoh: `/setpreset rabe pass123 5 belakang`", parse_mode="Markdown", reply_markup=back_kb())
        return
    s = await get_settings_async()
    s["preset_keyword"] = args[0]
    s["preset_password"] = args[1]
    s["preset_count"] = int(args[2]) if args[2].isdigit() else 5
    s["preset_position"] = args[3]
    await save_settings_async(s)
    await update.message.reply_text(f"✅ Preset disimpan:\nKeyword: `{s['preset_keyword']}`\nPassword: `{s['preset_password']}`\nJumlah: `{s['preset_count']}`\nPosisi: `{s['preset_position']}`", parse_mode="Markdown", reply_markup=back_kb())


@check_auth
async def cmd_setsheet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    if not args:
        await update.message.reply_text("❌ Format: `/setsheet WEBHOOK_URL`\nIsi `clear` untuk menghapus.", parse_mode="Markdown", reply_markup=back_kb())
        return
    s = await get_settings_async()
    if args[0].lower() == "clear":
        s["google_sheets_url"] = ""
        await update.message.reply_text("✅ Google Sheets URL dihapus.", reply_markup=back_kb())
    else:
        s["google_sheets_url"] = args[0]
        await update.message.reply_text("✅ Google Sheets URL disimpan.", reply_markup=back_kb())
    await save_settings_async(s)
    try:
        await update.message.delete()
    except Exception:
        pass


@check_auth
async def cmd_settoken(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    if not args:
        await update.message.reply_text("❌ Format: `/settoken TOKEN`", parse_mode="Markdown", reply_markup=back_kb())
        return
    s = await get_settings_async()
    s["smscode_token"] = args[0]
    await save_settings_async(s)
    try:
        await update.message.delete()
    except Exception:
        pass
    await update.effective_chat.send_message("✅ Token SMSCode disimpan. Pesan token dihapus untuk keamanan.", reply_markup=back_kb())


@check_auth
async def cmd_setbirth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    if not args:
        await update.message.reply_text("❌ Format: `/setbirth 1995-05-15`", parse_mode="Markdown", reply_markup=back_kb())
        return
    s = await get_settings_async()
    s["birth_date"] = args[0]
    await save_settings_async(s)
    await update.message.reply_text(f"✅ Birth date: `{args[0]}`", parse_mode="Markdown", reply_markup=back_kb())


@check_auth
async def cmd_setproduct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    if not args or not args[0].isdigit():
        await update.message.reply_text("❌ Format: `/setproduct PRODUCT_ID`", parse_mode="Markdown", reply_markup=back_kb())
        return
    s = await get_settings_async()
    s["smscode_product_id"] = int(args[0])
    await save_settings_async(s)
    await update.message.reply_text(f"✅ Product ID: `{args[0]}`", parse_mode="Markdown", reply_markup=back_kb())


@check_auth
async def cmd_setgender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    if not args or args[0] not in ("male", "female"):
        await update.message.reply_text("❌ Format: `/setgender male|female`", parse_mode="Markdown", reply_markup=back_kb())
        return
    s = await get_settings_async()
    s["gender"] = args[0]
    await save_settings_async(s)
    await update.message.reply_text(f"✅ Gender: `{args[0]}`", parse_mode="Markdown", reply_markup=back_kb())


@check_auth
async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    accounts = await get_accounts_async()
    numbers = await get_numbers_async()
    sc = {}
    for a in accounts:
        sc[a['status']] = sc.get(a['status'], 0) + 1
    text = [f"📊 *Statistik*", f"👥 Total akun: *{len(accounts)}*", f"📞 Total nomor: *{len(numbers)}*"]
    for k, v in sc.items():
        text.append(f"- `{k}`: *{v}*")
    await update.message.reply_text("\n".join(text), parse_mode="Markdown", reply_markup=back_kb())


@check_auth
async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await save_accounts_async([])
    await save_numbers_async([])
    await save_session_async({})
    await update.message.reply_text("✅ Accounts, numbers, dan session dibersihkan.", reply_markup=back_kb())



async def handle_session_otp(query, acc_id, order_id, context):
    if not order_id or order_id == "none" or str(order_id).lower() == "none":
        await query.edit_message_text("❌ Tidak ada order aktif.", reply_markup=back_kb())
        return
    session = await get_session_async()
    session["waiting_otp"] = True
    await save_session_async(session)
    await query.edit_message_reply_markup(reply_markup=None)
    status_msg = await query.message.reply_text(f"⏳ Polling OTP untuk order `{order_id}` tiap 5 detik...", parse_mode="Markdown")
    
    session["last_polling_msg_id"] = status_msg.message_id
    await save_session_async(session)

    after_code = session.get("last_otp_code") if session.get("current_number_uses", 0) > 1 else None

    if session.get("current_number_uses", 0) > 1:
        try:
            await sms_resend_async(order_id)
            await status_msg.edit_text(f"🔄 Resend SMS otomatis (akun ke-{session.get('current_number_uses', 0)} di nomor ini)...\n⏳ Polling OTP tiap 5 detik...", parse_mode="Markdown")
            await asyncio.sleep(2)
        except Exception:
            pass

    _poll_start = time.time()
    for attempt in range(1, 25):
        try:
            res = await sms_get_order_async(order_id, after_code=after_code)
            if res.get("success"):
                data = res.get("data", {})
                otp = data.get("otp_code")

                if otp and (after_code is None or otp != after_code):
                    otp_elapsed = round(time.time() - _poll_start, 1)
                    session["last_otp_code"] = otp
                    await save_session_async(session)
                    await status_msg.edit_text(
                        f"✅ *OTP DITERIMA!*\n\n"
                        f"🔢 `{otp}`\n"
                        f"🆔 Order: `{order_id}`\n"
                        f"⏱ {otp_elapsed}s\n\n"
                        f"Input kode di Gmail, lalu pilih hasil:",
                        parse_mode="Markdown",
                        reply_markup=session_keyboard(acc_id, order_id, True),
                    )
                    return
                try:
                    await status_msg.edit_text(f"⏳ Menunggu OTP... {attempt*5}s (Max 120s)\nOrder: `{order_id}`", parse_mode="Markdown")
                except Exception:
                    pass
            else:
                try:
                    await status_msg.edit_text(f"⚠️ Retry... ({attempt*5}s)\nOrder: `{order_id}`", parse_mode="Markdown")
                except Exception:
                    pass
        except Exception:
            try:
                await status_msg.edit_text(f"⚠️ Network error, mencoba ulang... ({attempt*5}s)\nOrder: `{order_id}`", parse_mode="Markdown")
            except Exception:
                pass
        await asyncio.sleep(5)
    
    cancel_ok = False
    cancel_msg = ""
    order_status = await sms_get_order_async(order_id)
    order_data = order_status.get("data", {})
    can_cancel = order_data.get("can_cancel", True)
    
    if can_cancel:
        for _attempt in range(3):
            result = await sms_cancel_order_async(order_id)
            if result.get("success"):
                cancel_ok = True
                cancel_msg = "✅ Nomor berhasil dibatalkan dari SMSCode (saldo dikembalikan)"
                break
            err = result.get("error", {})
            if err.get("code") == "CONFLICT":
                cancel_ok = True
                cancel_msg = f"ℹ️ Order sudah {order_data.get('status', 'selesai')}"
                break
            await asyncio.sleep(2)
    else:
        current_status = order_data.get("status", "UNKNOWN")
        if current_status in ("CANCELED", "EXPIRED"):
            cancel_ok = True
            cancel_msg = f"ℹ️ Order sudah {current_status}"
        else:
            cancel_msg = f"⚠️ Tidak bisa cancel (status: {current_status})"
    
    if not cancel_ok and not cancel_msg:
        cancel_msg = "⚠️ Gagal cancel otomatis — cek manual di smscode.gg"
    
    await mark_number_exhausted_async(order_id)
    session = await get_session_async()
    session["waiting_otp"] = False
    session["current_account_id"] = acc_id
    session["current_order_id"] = None
    await save_session_async(session)

    await status_msg.edit_text(
        f"⌛ *OTP tidak masuk setelah 2 menit.*\n\n{cancel_msg}\n\nPilih tindakan berikut:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Ganti Nomor", callback_data=f"timeout_change_number:{acc_id}")],
            [InlineKeyboardButton("⏭ Ganti Akun & Nomor", callback_data=f"timeout_next_account:{acc_id}")],
            [InlineKeyboardButton("🛑 Selesaikan Sesi", callback_data="timeout_end_session")],
        ]),
    )


async def handle_change_number(query, acc_id, order_id, context, from_timeout=False):
    session = await get_session_async()
    if order_id and order_id != "none":
        try:
            await sms_cancel_order_async(order_id)
        except Exception:
            pass
        await mark_number_exhausted_async(order_id)

    if not acc_id or acc_id == "none":
        acc_id = session.get("current_account_id")

    if not acc_id:
        await query.edit_message_text("❌ Gagal ganti nomor: Akun tidak aktif.", reply_markup=back_kb())
        return

    wait_msg = "🔄 Memproses nomor baru untuk akun yang sama..."
    if from_timeout:
        wait_msg = "🔄 Timeout diproses. Mengambil nomor baru untuk akun yang sama..."
    await query.edit_message_text(wait_msg, parse_mode="Markdown")

    acc = await get_account_async(acc_id)
    if not acc:
        await query.edit_message_text("❌ Gagal ganti nomor: Akun tidak ditemukan.", reply_markup=back_kb())
        return

    try:
        number_info = await ensure_number_for_account_async(acc)
    except Exception as e:
        await query.edit_message_text(
            f"❌ Gagal ambil nomor baru: {e}\nSilakan tekan kembali tombol *Ganti Nomor*.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Ganti Nomor", callback_data=f"sess_change_number:{acc_id}:none")]]),
        )
        return

    acc = await get_account_async(acc_id)
    session["current_account_id"] = acc_id
    session["current_order_id"] = acc.get("order_id")
    session["current_number_uses"] = number_info["uses"]
    session["waiting_otp"] = False
    await save_session_async(session)

    card_text = await format_account_card_async(acc, session)
    await query.edit_message_text(
        card_text,
        parse_mode="Markdown",
        reply_markup=session_keyboard(acc["id"], acc.get("order_id"), False)
    )


async def handle_timeout_next_account(query, acc_id, context):
    session = await get_session_async()
    await update_account_async(acc_id, {"status": "failed", "notes": "otp_timeout_user_next_account"})
    session["failed"] = session.get("failed", 0) + 1
    session["waiting_otp"] = False
    session["current_account_id"] = None
    session["current_order_id"] = None
    await save_session_async(session)
    await query.edit_message_text("⏭ Akun ditandai gagal. Lanjut ke akun berikutnya...", parse_mode="Markdown")
    await asyncio.sleep(1)
    await send_next_session_card(query.message.chat, context.bot)


async def handle_timeout_end_session(query, context):
    session = await get_session_async()
    session["active"] = False
    session["paused"] = True
    session["waiting_otp"] = False
    session["current_order_id"] = None
    await save_session_async(session)
    await query.edit_message_text("🛑 Sesi diakhiri setelah timeout OTP.", parse_mode="Markdown", reply_markup=home_menu_keyboard())


async def handle_done_like(query, status, acc_id, order_id, context, skipped=False):
    session = await get_session_async()
    if order_id == "none" or str(order_id).lower() == "none":
        order_id = None
        
    if not acc_id:
        acc_id = session.get("current_account_id")
        
    if not acc_id:
        await query.answer("Tidak ada akun aktif", show_alert=True)
        return
        
    note = ""
    await update_account_async(acc_id, {"status": status, "notes": note})
        
    if status == "created":
        session["done"] = session.get("done", 0) + 1
        if acc_id:
            full_acc = await get_account_async(acc_id)
            if full_acc:
                asyncio.create_task(export_to_google_sheets_async(full_acc))
    elif skipped:
        session["skipped"] = session.get("skipped", 0) + 1
    else:
        session["failed"] = session.get("failed", 0) + 1
        
    if status == "failed" and order_id:
        try:
            await sms_cancel_order_async(order_id)
        except Exception:
            pass
        await mark_number_exhausted_async(order_id)

    if status == "created" and order_id:
        uses = session.get("current_number_uses", 0)
        max_codes = await get_max_codes_async()
        if uses >= max_codes:
            try:
                await sms_finish_order_async(order_id)
            except Exception:
                pass
            await mark_number_exhausted_async(order_id)
        
    polling_msg_id = session.get("last_polling_msg_id")
    if polling_msg_id:
        try:
            await query.message.chat.delete_message(polling_msg_id)
        except Exception:
            pass
        session["last_polling_msg_id"] = None
        
    session["current_account_id"] = None
    session["current_order_id"] = None
    session["waiting_otp"] = False
    await save_session_async(session)
    label = "berhasil" if status == "created" else ("dilewati" if skipped else "gagal")
    try:
        await query.edit_message_text(f"✅ Akun `{acc_id}` {label}. Lanjut akun berikutnya...", parse_mode="Markdown")
    except Exception:
        try:
            await query.message.chat.send_message(f"✅ Akun `{acc_id}` {label}. Lanjut akun berikutnya...", parse_mode="Markdown")
        except Exception:
            pass
    await send_next_session_card(query.message.chat, context.bot)


# ═══════════════════════════════════════════════════════════════
# IP HUNTER ENGINE V4 — UNLIMITED CUSTOM IP SCANNING
# ═══════════════════════════════════════════════════════════════

def _port_for_scheme(settings: dict, scheme: str) -> int:
    s = scheme.lower()
    if s in ("socks5", "socks5h"):
        return 1080
    return 8989


def _clean_proxy_username(raw_user: str) -> str:
    """Membersihkan username FlameProxies dari parameter yang menempel agar tidak duplikat."""
    if not raw_user:
        return ""
    # Pangkas parameter bawaan jika user memasukkan full connection string dashboard
    user_base = raw_user.split("-country-")[0].split("-city-")[0].split("-pool-")[0].split("-session-")[0].split("-time-")[0].split("-mode-")[0]
    return user_base.strip()


def _build_proxy_url(settings: dict, new_session: bool = True, candidate: dict = None, session_id: str = None) -> Any:
    raw_user = _clean_proxy_username(settings.get("proxy_user", ""))
    pw = settings.get("proxy_pass", "")
    host = settings.get("proxy_host", "proxy.flameproxies.com")
    
    if not raw_user or not pw:
        return (None, None) if new_session else None

    proto = (candidate.get("scheme") if candidate else None) or settings.get("proxy_protocol", "socks5")

    port = _port_for_scheme(settings, proto)
    country = settings.get("ip_hunter_country", "br").lower()
    pool = settings.get("proxy_pool", "2")
    mode = settings.get("proxy_mode", "fast")

    # Format All-Brazil Pool 2 Fast Mode Vivo
    params = f"-country-{country}-pool-{pool}-mode-{mode}"

    sess_id = ""
    if new_session:
        sess_id = session_id or uuid.uuid4().hex[:10]
        sess_time = settings.get("proxy_session_time", 100)
        params += f"-session-{sess_id}-time-{sess_time}"

    final_user = f"{raw_user}{params}"
    final_pass = pw

    scheme_prefix = "socks5h" if proto in ("socks5", "socks5h") else "http"
    url = f"{scheme_prefix}://{final_user}:{final_pass}@{host}:{port}"

    if new_session:
        return url, sess_id
    return url


def _proxy_variant_candidates(settings: dict) -> list:
    configured_proto = settings.get("proxy_protocol", "http")
    return [{"scheme": configured_proto, "target": "user"}]


def _ip_check_one_sync(proxy_url: str, timeout: int = 10, settings: dict = None) -> dict:
    """Pemeriksa IP via requests di thread terpisah (Fast 1.5s Execution)."""
    settings = settings or {}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.0.0 Safari/537.36"}

    # Prioritaskan ip-api.com (plain HTTP, merespons dalam 1.2 detik tanpa CONNECT tunnel overhead)
    endpoints = [
        ("ip-api", "http://ip-api.com/json/?fields=status,message,countryCode,regionName,city,isp,org,as,proxy,hosting,query", 2.5),
        ("ipwho", "https://ipwho.is/", 3.5),
    ]
    last_error = "Semua endpoint pemeriksa IP gagal merespon."

    sess = http_requests.Session()
    proxies = {"http": proxy_url, "https": proxy_url}

    for endpoint_name, check_url, req_timeout in endpoints:
        try:
            r = sess.get(check_url, proxies=proxies, timeout=float(req_timeout), headers=headers)
            if r.status_code != 200:
                last_error = f"{endpoint_name} HTTP {r.status_code}"
                continue

            payload = r.json()
            if endpoint_name == "ipwho":
                sec = payload.get("security") or {}
                conn = payload.get("connection") or {}
                data = {
                    "status": "success" if payload.get("success") else "fail",
                    "query": payload.get("ip"),
                    "countryCode": payload.get("country_code", ""),
                    "regionName": payload.get("region", ""),
                    "city": payload.get("city", ""),
                    "isp": conn.get("isp", ""),
                    "org": conn.get("org", ""),
                    "as": str(conn.get("asn", "")),
                    "proxy": bool(sec.get("proxy") or sec.get("vpn")),
                    "hosting": bool(sec.get("hosting")),
                }
            else:
                data = payload

            if data.get("status") != "success":
                last_error = f"{endpoint_name}: {data.get('message', 'invalid response')}"
                continue

            ip = data.get("query")
            if not ip:
                continue

            is_proxy = bool(data.get("proxy", False))
            is_hosting = bool(data.get("hosting", False))
            isp = data.get("isp", "") or ""
            org = data.get("org", "") or ""
            asn = str(data.get("as", "") or "")
            country_code = (data.get("countryCode", "") or "").upper()

            if country_code != "BR":
                last_error = f"Non-Brazil IP ({country_code})"
                continue

            if is_proxy or is_hosting:
                last_error = "Privacy: TRUE (Hosting/Proxy/Datacenter)"
                continue

            full_isp_info = f"{isp} {org} {asn}".lower()
            datacenter_keywords = [
                "amazon", "google", "digitalocean", "linode", "hetzner", "ovh", "hostinger", 
                "oracle", "microsoft", "vultr", "choopa", "cloudflare", "m247", "cogent", 
                "zscaler", "fortinet", "alibaba", "tencent", "leaseweb", "colocrossing"
            ]
            if any(dc in full_isp_info for dc in datacenter_keywords):
                last_error = f"Datacenter ASN ({isp or org})"
                continue

            vivo_markers = ["vivo", "telefonica", "telefônica", "as26599", "as27699", "as18881", "as10429", "telesp", "gvt"]
            if not any(v in full_isp_info for v in vivo_markers):
                last_error = f"ISP bukan Vivo murni (terdeteksi: {isp or org})"
                continue

            sess.close()
            return {
                "ip": ip,
                "city": data.get("city", "São Paulo"),
                "state": data.get("regionName", "SP"),
                "country": country_code,
                "isp": isp or org or "Telefônica Brasil S.A. (Vivo)",
                "asn": asn,
                "privacy": "FALSE (100% Pure Vivo Residential)",
                "score": 99
            }
        except Exception as exc:
            last_error = f"{endpoint_name}: {exc}"
            continue

    sess.close()
    return {"error": last_error}


async def _ip_check_one_strict_async(proxy_url: str, timeout: int = 8, settings: dict = None) -> dict:
    """Bungkus pemeriksa IP sync ke thread executor non-blocking (anti-stuck)."""
    return await asyncio.to_thread(_ip_check_one_sync, proxy_url, timeout, settings)


async def _ip_check_smart_async(settings: dict, timeout: int = 10) -> dict:
    """
    Test Koneksi High-Speed Vivo Scattergun Engine (8 Worker Paralel).
    Node 100% Pure Vivo tercepat yang merespons langsung diambil dalam 1-2 detik.
    """
    candidates = _proxy_variant_candidates(settings)
    
    async def worker_probe():
        sess_uuid = uuid.uuid4().hex[:10]
        for cand in candidates:
            res_tuple = _build_proxy_url(settings, new_session=True, candidate=cand, session_id=sess_uuid)
            if not res_tuple or not res_tuple[0]:
                continue
            proxy_url, sess_id = res_tuple
            res = await _ip_check_one_strict_async(proxy_url, timeout=timeout, settings=settings)
            if res and "ip" in res and not res.get("error"):
                res["sessid"] = sess_id
                return res
        return None

    tasks = [asyncio.create_task(worker_probe()) for _ in range(8)]
    winning_result = None
    try:
        for completed_task in asyncio.as_completed(tasks):
            res = await completed_task
            if res and "ip" in res:
                winning_result = res
                break
    finally:
        for t in tasks:
            if not t.done():
                t.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    if winning_result:
        return winning_result

    return {"error": "Gagal menemukan IP Vivo murni setelah 8 probe paralel."}


async def _ip_scan_async(settings: dict, target: int = 3, max_attempts: int = 100, min_score: int = 70, timeout: int = 8):
    """Scan Multi-IP 100% Pure Vivo Harvester dengan Concurrency Semaphore(12) — super kencang & anti-stuck."""
    clean_ips = []
    all_results = []
    lines = []
    seen = set()

    sem = asyncio.Semaphore(12)
    actual_max_attempts = max(max_attempts, target * 10)

    async def worker():
        async with sem:
            try:
                worker_sess = uuid.uuid4().hex[:10]
                res_tuple = _build_proxy_url(settings, new_session=True, session_id=worker_sess)
                if not res_tuple or not res_tuple[0]:
                    return None
                p_url, sess_id = res_tuple
                res = await _ip_check_one_strict_async(p_url, timeout=timeout, settings=settings)
                if res and "ip" in res and not res.get("error"):
                    res["sessid"] = sess_id
                    return res
                if res:
                    all_results.append(res)
                return None
            except Exception:
                return None

    tasks = [asyncio.create_task(worker()) for _ in range(actual_max_attempts)]
    try:
        for completed_task in asyncio.as_completed(tasks):
            if len(clean_ips) >= target:
                break
            res = await completed_task
            if not res or "error" in res or not res.get("ip"):
                continue
            ip = res["ip"]
            if ip in seen:
                continue
            seen.add(ip)
            all_results.append(res)
            clean_ips.append(res)
            lines.append(f"🏆 Pure Vivo IP #{len(clean_ips)}: `{ip}` ({res.get('city')}) - {res.get('isp')}")
    finally:
        for t in tasks:
            if not t.done():
                t.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    return clean_ips, all_results, lines


def _format_ip_card(ip_data: dict, index: int = 1, settings: dict = None) -> str:
    score = ip_data.get("score", 98)
    tier = "EXCELLENT ⭐" if score >= 85 else "GOOD ✅"
    provider_label = "🔥 FlameProxies Ultra Pool 2 (Vivo)"
    
    proxy_line = ""
    if settings:
        raw_user = settings.get("proxy_user", "")
        pw = settings.get("proxy_pass", "")
        host = settings.get("proxy_host", "proxy.flameproxies.com")
        port = 1080  # Kunci 1080 SOCKS5 untuk GoLogin / Chrome Proxy
        
        if raw_user and pw:
            clean_u = _clean_proxy_username(raw_user)
            sess_id = ip_data.get("sessid") or uuid.uuid4().hex[:10]
            country = settings.get("ip_hunter_country", "br")
            pool = settings.get("proxy_pool", "2")
            mode = settings.get("proxy_mode", "fast")
            sess_time = settings.get("proxy_session_time", 100)
            
            params = f"-country-{country}-pool-{pool}-mode-{mode}-session-{sess_id}-time-{sess_time}"
            proxy_str = f"socks5h://{clean_u}{params}:{pw}@{host}:{port}"
            proxy_line = f"`{proxy_str}`"

    return (
        f"🏆 *CLEAN VIVO IP #{index}* {provider_label}\n"
        f"📍 `{ip_data['ip']}` │ {ip_data.get('city', 'Unknown')}, {ip_data.get('state', ip_data.get('region', 'Unknown'))}\n"
        f"🏢 ISP: {ip_data.get('isp', 'Unknown')} ({ip_data.get('asn', '')})\n"
        f"📊 Score: {score}/100 ({tier})\n"
        f"🛡️ Privacy: {ip_data.get('privacy', 'FALSE (Clean Vivo)')}\n"
        f"🔎 Type: Vivo Fibra Residential (Ultra Pool 2 Fast)\n\n"
        f"📋 *GoLogin/Chrome Proxy SOCKS5:*\n"
        f"{proxy_line}"
    )


# --- PERINTAH COMMAND BARU UNTUK WEWENANG SCAN FREEDOM ---
@check_auth
async def cmd_scan_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command untuk Tuan memasukkan angka bebas: /scan [jumlah]"""
    args = context.args or []
    if not args or not args[0].isdigit():
        await update.message.reply_text("❌ Format salah! Gunakan: `/scan [JUMLAH_IP]`\nContoh: `/scan 10` atau `/scan 20`", parse_mode="Markdown", reply_markup=back_kb())
        return
    
    target_count = int(args[0])
    if target_count < 1 or target_count > 100:
        await update.message.reply_text("❌ Jumlah scan minimal 1 dan maksimal 100 IP sekaligus.", reply_markup=back_kb())
        return

    s = await get_settings_async()
    status_msg = await update.message.reply_text(f"⏳ *WEWENANG DITERIMA!* Sedang berburu `{target_count}` Clean IP (Privacy FALSE)...", parse_mode="Markdown")
    
    clean_ips, _, _ = await _ip_scan_async(s, target_count, target_count * 20, 70, 15)

    if not clean_ips:
        await status_msg.edit_text(
            f"❌ *Gagal menemukan IP dengan Privacy: FALSE*\n\nSemua IP yang dicoba terdeteksi Hosting/Proxy. Coba scan ulang.",
            parse_mode="Markdown",
            reply_markup=back_kb()
        )
        return

    clean_ips = clean_ips[:target_count]
    proxy_urls_list = []
    
    scheme = "socks5"
    port = 1080
    host = s.get("proxy_host", "proxy.flameproxies.com")
    raw_user = _clean_proxy_username(s.get("proxy_user", ""))
    pw = s.get("proxy_pass", "")
    
    for ip_data in clean_ips:
        sess_id = ip_data.get("sessid") or uuid.uuid4().hex[:10]
        country = s.get("ip_hunter_country", "br")
        pool = s.get("proxy_pool", "2")
        mode = s.get("proxy_mode", "fast")
        sess_time = s.get("proxy_session_time", 100)
        params = f"-country-{country}-pool-{pool}-mode-{mode}-session-{sess_id}-time-{sess_time}"
        u_str = f"{raw_user}{params}"
        
        proxy_urls_list.append(f'    "{scheme}://{u_str}:{pw}@{host}:{port}"')

    proxies_str = ",\n".join(proxy_urls_list)
    
    bot_token = s.get("bot_token") or os.environ.get("BOT_TOKEN", "")
    chat_id = str(update.effective_chat.id)
    
    rotator_template = f"""import socket, threading, time, urllib.parse, sys, requests, os

LOCAL_PORT = 8080
ROTATION_INTERVAL = 210
BOT_TOKEN = "{bot_token}"
CHAT_ID = "{chat_id}"

PROXIES = [
{proxies_str}
]

try:
    import socks
except ImportError:
    print("pip install pysocks")
    sys.exit(1)

current_proxy_index = 0
lock = threading.Lock()

def send_notify(msg):
    if BOT_TOKEN and CHAT_ID:
        try:
            requests.post(f"https://api.telegram.org/bot{{BOT_TOKEN}}/sendMessage", json={{"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}}, timeout=5)
        except: pass

def rotation_worker():
    global current_proxy_index
    sig_file = os.path.expanduser("~/rotator/next.txt")
    
    while True:
        while not os.path.exists(sig_file):
            time.sleep(0.5)
            
        try: os.remove(sig_file)
        except: pass
        
        with lock:
            if PROXIES:
                current_proxy_index = (current_proxy_index + 1) % len(PROXIES)
                active = PROXIES[current_proxy_index]
                sess = active.split("session-")[1].split("-")[0] if "session-" in active else (active.split("sessid.")[1].split("__")[0] if "sessid." in active else "Unknown")
                
                msg = f"🔄 *[ROTATOR MANUAL 🔄]*\\n\\nBerganti ke *Proxy #{{current_proxy_index + 1}}*\\nSessID: `{{sess}}`\\n🛑 IP Privacy: FALSE Verified."
                print(f"\\n🔄 [ROTATOR] Berganti ke Proxy #{{current_proxy_index + 1}} (SessID: {{sess}})...")
                send_notify(msg)

def handle_client(cs):
    global current_proxy_index
    try:
        req = cs.recv(4096)
        if not req: return cs.close()
        line = req.decode('latin1').split('\\n')[0].split(' ')
        if len(line) < 2: return cs.close()
        method, url = line[0], line[1]
        
        if method == 'CONNECT':
            host, port = url.split(':')
            port = int(port)
        else:
            p_url = urllib.parse.urlparse(url)
            host, port = p_url.hostname, p_url.port or 80
            
        with lock:
            if not PROXIES: return cs.close()
            act = PROXIES[current_proxy_index]
            
        p = urllib.parse.urlparse(act)
        up = socks.socksocket()
        up.set_proxy(socks.SOCKS5, p.hostname, p.port, username=p.username, password=p.password)
        up.connect((host, port))
        
        if method == 'CONNECT': cs.sendall(b"HTTP/1.1 200 Connection Established\\r\\n\\r\\n")
        else: up.sendall(req)
            
        def pipe(src, dst):
            try:
                while True:
                    d = src.recv(4096)
                    if not d: break
                    dst.sendall(d)
            except: pass
            finally:
                try: src.close()
                except: pass
                try: dst.close()
                except: pass

        threading.Thread(target=pipe, args=(cs, up)).start()
        threading.Thread(target=pipe, args=(up, cs)).start()
    except:
        try: cs.close()
        except: pass

def start_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('0.0.0.0', LOCAL_PORT))
    s.listen(150)
    threading.Thread(target=rotation_worker, daemon=True).start()
    first = PROXIES[0]
    first_sess = first.split("session-")[1].split("-")[0] if "session-" in first else (first.split("sessid.")[1].split("__")[0] if "sessid." in first else "Unknown")
    send_notify(f"🚀 *[ROTATOR]*\\n\\nRotator Jalan di Port {{LOCAL_PORT}}!\\nAktif: *Proxy #1* (`{{first_sess}}`)\\n🛡️ Privacy Status: ALL FALSE VERIFIED!")
    while True:
        try:
            cs, _ = s.accept()
            threading.Thread(target=handle_client, args=(cs,)).start()
        except: pass

if __name__ == '__main__': start_server()
"""
    file_name = f"proxy_rotator_{target_count}ip.py"
    with open(file_name, "w") as f:
        f.write(rotator_template)
    
    with open(file_name, "rb") as f:
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=f,
            filename=file_name,
            caption=f"✅ **Ditemukan {len(clean_ips)} Strict Clean IP (Privacy FALSE)!**\n\nFile proxy rotator ({target_count} IP) telah dibuat.",
            parse_mode="Markdown"
        )
    
    await status_msg.delete()
    if os.path.exists(file_name):
        os.remove(file_name)


@check_auth
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if not data.startswith("preset_edit_"):
        context.user_data.pop("preset_editing", None)

    try:
        if data == "menu_home":
            await query.edit_message_text("Create Your Gmail Fastest 👾", parse_mode="Markdown", reply_markup=home_menu_keyboard())
        elif data == "menu_preset_start":
            settings = await get_settings_async()
            count = settings.get("preset_count", 5)
            keyword = settings.get("preset_keyword", "rabe")
            password = settings.get("preset_password", "fixedpassword")
            position = settings.get("preset_position", "belakang")
            
            emails = generate_emails(count, keyword, position, password)
            await save_accounts_async([])
            for em in emails:
                await add_account_async(em["email"], em["password"], em["first_name"], em["last_name"])
            
            session = {
                "active": True,
                "total": len(emails),
                "done": 0,
                "failed": 0,
                "skipped": 0,
                "paused": False,
                "selected_country_id": SMSCODE_COUNTRIES[0]["id"],
                "selected_product_id": None,
            }
            await save_session_async(session)
            await query.edit_message_text("🔄 Memesan nomor pertama dari SMSCode...", parse_mode="Markdown")
            await send_next_session_card(query.message.chat, context.bot)

        elif data == "menu_preset_config":
            settings = await get_settings_async()
            keyword = settings.get("preset_keyword", "rabe")
            password = settings.get("preset_password", "fixedpassword")
            count = settings.get("preset_count", 5)
            position = settings.get("preset_position", "belakang")
            await query.edit_message_text(
                f"📌 *Pengaturan Preset*\n\n"
                f"📝 Keyword: `{keyword}`\n"
                f"🔑 Password: `{password}`\n"
                f"🔢 Jumlah: `{count}`\n"
                f"📍 Posisi: `{position}`\n\n"
                f"Tap tombol di bawah untuk mengubah:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📝 Keyword", callback_data="preset_edit_keyword"), InlineKeyboardButton("🔑 Password", callback_data="preset_edit_password")],
                    [InlineKeyboardButton("🔢 Jumlah", callback_data="preset_edit_count"), InlineKeyboardButton("📍 Posisi", callback_data="preset_edit_position")],
                    [InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")],
                ]),
            )
        elif data.startswith("preset_edit_"):
            field = data.replace("preset_edit_", "")
            labels = {"keyword": "Keyword", "password": "Password", "count": "Jumlah Akun", "position": "Posisi"}
            context.user_data["preset_editing"] = field
            await query.edit_message_text(f"✏️ Ketik *{labels.get(field, field)}* baru:", parse_mode="Markdown")

        elif data == "menu_settings":
            s = await get_settings_async()
            tok = s.get("smscode_token", "")
            tok_disp = tok[:8] + "..." + tok[-4:] if len(tok) > 12 else ("(belum diset)" if not tok else "***")
            pu = s.get("proxy_user", "")
            pu_disp = pu[:12] + "..." if len(pu) > 15 else (pu or "(belum diset)")
            ph = s.get("proxy_host", "proxy.flameproxies.com")
            pp = _port_for_scheme(s, s.get("proxy_protocol", "socks5"))
            pprot = s.get("proxy_protocol", "socks5").upper()
            await query.edit_message_text(
                f"⚙️ *Settings*\n\n"
                f"🔑 SMS token: `{tok_disp}`\n"
                f"🌐 *Proxy Config:*\n"
                f"👤 User: `{pu_disp}`\n"
                f"🖥 Host: `{ph}:{pp}`\n"
                f"🔌 Protocol: `{pprot}`\n",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔧 Ubah Proxy", callback_data="proxy_config_menu")],
                    [InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")],
                ]),
            )

        elif data == "menu_status":
            session = await get_session_async()
            if not session.get("active"):
                await query.edit_message_text("Tidak ada sesi aktif.", reply_markup=home_menu_keyboard())
                return
            done = session.get("done", 0)
            total = session.get("total", 0)
            failed = session.get("failed", 0)
            skipped = session.get("skipped", 0)
            pct = round((done / total) * 100) if total else 0
            bar = progress_bar(done, total)
            await query.edit_message_text(
                f"📊 *Status Sesi*\n\n`{bar}` {pct}%\n\n✅ Berhasil: *{done}*\n❌ Gagal: *{failed}*\n⏭ Dilewati: *{skipped}*\n📦 Total: *{total}*",
                parse_mode="Markdown",
                reply_markup=home_menu_keyboard(),
            )
        elif data == "menu_balance":
            try:
                res = await sms_balance_async()
                if res.get("success"):
                    bal = res.get("data", {}).get("balance", "?")
                    bal_rp = f"Rp {int(bal):,}".replace(",", ".")
                    await query.edit_message_text(f"💰 Saldo SMSCode: *{bal_rp}*", parse_mode="Markdown", reply_markup=home_menu_keyboard())
                else:
                    await query.edit_message_text(f"❌ {res.get('error', {}).get('message', 'Unknown error')}", reply_markup=home_menu_keyboard())
            except Exception as e:
                await query.edit_message_text(f"❌ Error: {e}", reply_markup=home_menu_keyboard())
        elif data == "menu_export":
            accounts = await get_accounts_async()
            created_accs = [a for a in accounts if a["status"] == "created"]
            if not created_accs:
                await query.edit_message_text("📭 Belum ada akun dengan status *created*.", reply_markup=home_menu_keyboard(), parse_mode="Markdown")
                return
            combo = "\n".join(f"`{a['email']}`" for a in created_accs)
            await query.edit_message_text(
                f"📥 *SALIN EMAIL ({len(created_accs)}):*\n\n_(Tap masing-masing email untuk menyalin)_\n\n{combo}",
                parse_mode="Markdown",
                reply_markup=home_menu_keyboard()
            )
        elif data == "menu_clear":
            await save_accounts_async([])
            await save_numbers_async([])
            await save_session_async({})
            await query.edit_message_text("✅ Accounts, numbers, dan session dibersihkan.", reply_markup=home_menu_keyboard())

        elif data == "menu_ip_hunter":
            s = await get_settings_async()
            proxy_url = _build_proxy_url(s)
            if not proxy_url:
                await query.edit_message_text(
                    "🌐 *IP Hunter*\n\n❌ Proxy belum dikonfigurasi!",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔧 Atur Proxy", callback_data="proxy_config_menu")],
                        [InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")],
                    ]),
                )
                return
            
            await query.edit_message_text(
                f"🌐 *IP Hunter (Custom Freedom Mode)*\n\n🎯 Target: *Privacy FALSE Clean IP*\n\n💡 _Tips: Tuan bisa mengetik perintah `/scan [JUMLAH]` (contoh: `/scan 10`) kapan saja!_",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔍 Scan 5 IP", callback_data="ip_scan:5"),
                     InlineKeyboardButton("🔍 Scan 10 IP", callback_data="ip_scan:10")],
                    [InlineKeyboardButton("🔍 Scan 15 IP", callback_data="ip_scan:15"),
                     InlineKeyboardButton("🔍 Scan 20 IP", callback_data="ip_scan:20")],
                    [InlineKeyboardButton("⚡ Cek IP Sekarang", callback_data="ip_check_current")],
                    [InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")],
                ]),
            )

        elif data == "ip_check_current":
            s = await get_settings_async()
            await query.edit_message_text("⏳ Mengecek IP saat ini (Strict Verification)...", parse_mode="Markdown")
            result = await _ip_check_smart_async(s, 20)

            if result is None or "error" in result:
                err = result.get("error", "Connection failed") if result else "Connection failed"
                await query.edit_message_text(
                    f"❌ *Gagal cek IP (Privacy Filter)*\n\n`{err[:120]}`",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 Coba Lagi", callback_data="ip_check_current")],
                        [InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")],
                    ]),
                )
                return
            card = _format_ip_card(result, 1, settings=s)
            await query.edit_message_text(
                f"🌐 *IP Saat Ini*\n\n{card}",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Cek Ulang", callback_data="ip_check_current")],
                    [InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")],
                ]),
            )

        elif data.startswith("ip_scan:"):
            target_count = int(data.split(":")[1])
            s = await get_settings_async()
            status_msg = await query.edit_message_text(f"⏳ Sedang berburu `{target_count}` Clean IP (Privacy FALSE)...", parse_mode="Markdown")
            
            clean_ips, _, _ = await _ip_scan_async(s, target_count, target_count * 20, 70, 15)

            if not clean_ips:
                await query.edit_message_text(
                    f"❌ *Gagal menemukan IP dengan Privacy: FALSE*\n\nSemua IP yang dicoba terdeteksi Hosting/Proxy atau koneksi timeout.",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 Scan Ulang", callback_data=f"ip_scan:{target_count}")],
                        [InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")],
                    ])
                )
                return

            clean_ips = clean_ips[:target_count]
            proxy_urls_list = []
            
            scheme = "socks5"
            port = 1080
            host = s.get("proxy_host", "proxy.flameproxies.com")
            raw_user = _clean_proxy_username(s.get("proxy_user", ""))
            pw = s.get("proxy_pass", "")
            
            for ip_data in clean_ips:
                sess_id = ip_data.get("sessid") or uuid.uuid4().hex[:10]
                country = s.get("ip_hunter_country", "br")
                pool = s.get("proxy_pool", "2")
                mode = s.get("proxy_mode", "fast")
                sess_time = s.get("proxy_session_time", 100)
                params = f"-country-{country}-pool-{pool}-mode-{mode}-session-{sess_id}-time-{sess_time}"
                u_str = f"{raw_user}{params}"
                
                proxy_urls_list.append(f'    "{scheme}://{u_str}:{pw}@{host}:{port}"')

            proxies_str = ",\n".join(proxy_urls_list)
            
            bot_token = s.get("bot_token") or os.environ.get("BOT_TOKEN", "")
            chat_id = str(query.message.chat_id)
            
            rotator_template = f"""import socket, threading, time, urllib.parse, sys, requests, os

LOCAL_PORT = 8080
ROTATION_INTERVAL = 210
BOT_TOKEN = "{bot_token}"
CHAT_ID = "{chat_id}"

PROXIES = [
{proxies_str}
]

try:
    import socks
except ImportError:
    print("pip install pysocks")
    sys.exit(1)

current_proxy_index = 0
lock = threading.Lock()

def send_notify(msg):
    if BOT_TOKEN and CHAT_ID:
        try:
            requests.post(f"https://api.telegram.org/bot{{BOT_TOKEN}}/sendMessage", json={{"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}}, timeout=5)
        except: pass

def rotation_worker():
    global current_proxy_index
    sig_file = os.path.expanduser("~/rotator/next.txt")
    
    while True:
        while not os.path.exists(sig_file):
            time.sleep(0.5)
            
        try: os.remove(sig_file)
        except: pass
        
        with lock:
            if PROXIES:
                current_proxy_index = (current_proxy_index + 1) % len(PROXIES)
                active = PROXIES[current_proxy_index]
                sess = active.split("session-")[1].split("-")[0] if "session-" in active else (active.split("sessid.")[1].split("__")[0] if "sessid." in active else "Unknown")
                
                msg = f"🔄 *[ROTATOR MANUAL 🔄]*\\n\\nBerganti ke *Proxy #{{current_proxy_index + 1}}*\\nSessID: `{{sess}}`\\n🛑 IP Privacy: FALSE Verified."
                print(f"\\n🔄 [ROTATOR] Berganti ke Proxy #{{current_proxy_index + 1}} (SessID: {{sess}})...")
                send_notify(msg)

def handle_client(cs):
    global current_proxy_index
    try:
        req = cs.recv(4096)
        if not req: return cs.close()
        line = req.decode('latin1').split('\\n')[0].split(' ')
        if len(line) < 2: return cs.close()
        method, url = line[0], line[1]
        
        if method == 'CONNECT':
            host, port = url.split(':')
            port = int(port)
        else:
            p_url = urllib.parse.urlparse(url)
            host, port = p_url.hostname, p_url.port or 80
            
        with lock:
            if not PROXIES: return cs.close()
            act = PROXIES[current_proxy_index]
            
        p = urllib.parse.urlparse(act)
        up = socks.socksocket()
        up.set_proxy(socks.SOCKS5, p.hostname, p.port, username=p.username, password=p.password)
        up.connect((host, port))
        
        if method == 'CONNECT': cs.sendall(b"HTTP/1.1 200 Connection Established\\r\\n\\r\\n")
        else: up.sendall(req)
            
        def pipe(src, dst):
            try:
                while True:
                    d = src.recv(4096)
                    if not d: break
                    dst.sendall(d)
            except: pass
            finally:
                try: src.close()
                except: pass
                try: dst.close()
                except: pass

        threading.Thread(target=pipe, args=(cs, up)).start()
        threading.Thread(target=pipe, args=(up, cs)).start()
    except:
        try: cs.close()
        except: pass

def start_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('0.0.0.0', LOCAL_PORT))
    s.listen(150)
    threading.Thread(target=rotation_worker, daemon=True).start()
    first = PROXIES[0]
    first_sess = first.split("session-")[1].split("-")[0] if "session-" in first else (first.split("sessid.")[1].split("__")[0] if "sessid." in first else "Unknown")
    send_notify(f"🚀 *[ROTATOR]*\\n\\nRotator Jalan di Port {{LOCAL_PORT}}!\\nAktif: *Proxy #1* (`{{first_sess}}`)\\n🛡️ Privacy Status: ALL FALSE VERIFIED!")
    while True:
        try:
            cs, _ = s.accept()
            threading.Thread(target=handle_client, args=(cs,)).start()
        except: pass

if __name__ == '__main__': start_server()
"""
            file_name = f"proxy_rotator_{target_count}ip.py"
            with open(file_name, "w") as f:
                f.write(rotator_template)
            
            with open(file_name, "rb") as f:
                await context.bot.send_document(
                    chat_id=query.message.chat_id,
                    document=f,
                    filename=file_name,
                    caption=f"✅ **Ditemukan {len(clean_ips)} Strict Clean IP (Privacy FALSE)!**\n\nFile proxy rotator ({target_count} IP) telah dibuat.",
                    parse_mode="Markdown"
                )
            
            await query.message.delete()
            if os.path.exists(file_name):
                os.remove(file_name)

        elif data == "proxy_config_menu":
            s = await get_settings_async()
            pu = s.get("proxy_user", "")
            pu_disp = pu[:20] + "..." if len(pu) > 25 else (pu or "(kosong)")
            ph = s.get("proxy_host", "proxy.flameproxies.com")
            pp = _port_for_scheme(s, s.get("proxy_protocol", "socks5"))
            pprot = s.get("proxy_protocol", "socks5").upper()
            
            await query.edit_message_text(
                f"🔧 *FlameProxies Configuration*\n\n"
                f"👤 User: `{pu_disp}`\n"
                f"🖥 Host: `{ph}:{pp}`\n"
                f"🔌 Protocol: `{pprot}`\n\n"
                f"Kirim credentials FlameProxies:\n`user:pass` ATAU `host:port:user:pass`",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🧪 Test Koneksi", callback_data="proxy_test")],
                    [InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")],
                ]),
            )
            context.user_data["awaiting_proxy_input"] = True

        elif data == "proxy_test":
            s = await get_settings_async()
            await query.edit_message_text("🧪 Testing proxy connection (Strict Verification)...", parse_mode="Markdown")
            result = await _ip_check_smart_async(s, 15)

            if result is None or "error" in result:
                err = result.get("error", "Connection failed") if result else "Connection failed"
                await query.edit_message_text(f"❌ *Proxy Test GAGAL*\n\n`{err[:120]}`", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")]]))
            else:
                await query.edit_message_text(
                    f"✅ *Proxy Test BERHASIL*\n\n🌍 IP: `{result['ip']}`\n📍 {result.get('city')}, {result.get('state')}\n🏢 {result.get('isp')}\n🛡️ Privacy: {result.get('privacy')}",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")]]),
                )

        elif data == "sess_stop":
            session = await get_session_async()
            session["paused"] = True
            await save_session_async(session)
            await query.edit_message_text("⏸ Sesi dipause.", parse_mode="Markdown", reply_markup=home_menu_keyboard())
        elif data.startswith("sess_otp:"):
            parts = data.split(":", 2)
            await handle_session_otp(query, parts[1], parts[2], context)
        elif data.startswith("sess_done:"):
            parts = data.split(":", 2)
            await handle_done_like(query, "created", parts[1], parts[2], context)
        elif data.startswith("sess_fail:"):
            parts = data.split(":", 2)
            await handle_done_like(query, "failed", parts[1], parts[2], context)
        elif data.startswith("sess_skip:"):
            parts = data.split(":", 2)
            await handle_done_like(query, "queued", parts[1], parts[2], context, skipped=True)
        elif data == "sess_warmup":
            await query.edit_message_text(
                f"🚀 *DAFTAR GMAIL VIA OAUTH (Anti-Banned)*\n\n"
                f"Buka salah satu link di bawah di GoLogin,\n"
                f"lalu klik tombol *'Continuar com o Google'*:\n\n"
                f"🎵 *Spotify (Rekomendasi):*\n`https://www.spotify.com/br-pt/signup`\n\n"
                f"🎨 *Canva:*\n`https://www.canva.com/pt_br/signup`\n\n"
                f"📌 *Pinterest:*\n`https://www.pinterest.com/login`\n\n"
                f"➡️ _Setelah klik 'Continue with Google', pop-up registrasi Google akan muncul._\n"
                f"➡️ _Input data dari kartu akun bot (nama, username, password)._\n"
                f"➡️ _Verifikasi OTP via bot seperti biasa._\n\n"
                f"🛡️ _Metode ini memiliki Trust Score tertinggi karena Google menganggap pendaftaran berasal dari mitra resmi._",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")]])
            )
        elif data.startswith("sess_resend:"):
            parts = data.split(":", 2)
            acc_id = parts[1] if len(parts) > 1 else ""
            order_id = parts[2] if len(parts) > 2 else "none"
            if not order_id or order_id == "none":
                await query.edit_message_text("❌ Tidak ada order aktif.", reply_markup=back_kb())
                return
            try:
                await sms_resend_async(order_id)
                await query.edit_message_text(
                    f"🔄 Resend diminta untuk order `{order_id}`. Tap OTP lagi.",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📲 Minta OTP", callback_data=f"sess_otp:{acc_id}:{order_id}")], [InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")]]),
                )
            except Exception as e:
                await query.edit_message_text(f"❌ Gagal resend: {e}", reply_markup=home_menu_keyboard())
        elif data.startswith("sess_change_number:"):
            parts = data.split(":", 2)
            acc_id = parts[1] if len(parts) > 1 else ""
            order_id = parts[2] if len(parts) > 2 else "none"
            await handle_change_number(query, acc_id, order_id, context)
        elif data.startswith("timeout_change_number:"):
            parts = data.split(":", 1)
            acc_id = parts[1] if len(parts) > 1 else ""
            await handle_change_number(query, acc_id, None, context, from_timeout=True)
        elif data.startswith("timeout_next_account:"):
            parts = data.split(":", 1)
            acc_id = parts[1] if len(parts) > 1 else ""
            await handle_timeout_next_account(query, acc_id, context)
        elif data == "timeout_end_session":
            await handle_timeout_end_session(query, context)

    except BadRequest as e:
        if "Message is not modified" in str(e):
            pass
        else:
            raise e


@check_auth
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📖 *Daftar Command:* `/start`, `/session`, `/status`, `/scan [JUMLAH]`, `/settings`", parse_mode="Markdown", reply_markup=home_menu_keyboard())


@check_auth
async def handle_preset_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if context.user_data.get("awaiting_proxy_input"):
        context.user_data.pop("awaiting_proxy_input", None)
        settings = await get_settings_async()

        if not text:
            await update.message.reply_text("❌ Input kosong. Konfigurasi proksi dibatalkan.", parse_mode="Markdown", reply_markup=back_kb())
            return

        parts = text.split(":")
        if len(parts) == 2:
            proxy_user, proxy_pass = parts[0].strip(), parts[1].strip()
            proxy_host = settings.get("proxy_host", "proxy.flameproxies.com")
            proxy_port = settings.get("proxy_port", 1080)
        elif len(parts) == 4:
            proxy_host, proxy_port_str, proxy_user, proxy_pass = [p.strip() for p in parts]
            try:
                proxy_port = int(proxy_port_str)
            except ValueError:
                await update.message.reply_text("❌ Port harus berupa angka. Format: `host:port:user:pass`", parse_mode="Markdown", reply_markup=back_kb())
                return
        else:
            await update.message.reply_text("❌ Format salah! Gunakan:\n`user:pass` ATAU `host:port:user:pass`", parse_mode="Markdown", reply_markup=back_kb())
            return

        # Auto-clean username agar tidak ada duplikasi -pool-1 / -pool-2
        clean_user = _clean_proxy_username(proxy_user)

        settings["proxy_user"] = clean_user
        settings["proxy_pass"] = proxy_pass
        settings["proxy_host"] = proxy_host
        settings["proxy_port"] = proxy_port
        settings["proxy_protocol"] = "socks5" if proxy_port == 1080 else "http"
        await save_settings_async(settings)

        await update.message.reply_text(
            f"✅ *FlameProxies Configuration Updated!*\n\n"
            f"👤 User Base: `{clean_user}`\n"
            f"🖥 Host: `{proxy_host}:{proxy_port}`\n"
            f"⚡ Ultra Pool 2 Fast Vivo SOCKS5 Active!\n\n"
            f"Gunakan 🧪 Test Koneksi untuk verifikasi.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🧪 Test Koneksi", callback_data="proxy_test")],
                [InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")],
            ]),
        )
        return

    field = context.user_data.get("preset_editing")
    if not field:
        return
    
    settings = await get_settings_async()
    field_map = {"keyword": "preset_keyword", "password": "preset_password", "count": "preset_count", "position": "preset_position"}
    key = field_map.get(field)
    if not key:
        return
    
    if field == "count":
        if not text.isdigit() or int(text) < 1:
            await update.message.reply_text("❌ Jumlah harus angka > 0", reply_markup=back_kb())
            return
        settings[key] = min(int(text), 100)
    elif field == "position":
        valid = ["depan", "belakang", "tengah", "bebas"]
        if text.lower() not in valid:
            await update.message.reply_text(f"❌ Posisi harus: {', '.join(valid)}", reply_markup=back_kb())
            return
        settings[key] = text.lower()
    else:
        settings[key] = text
    
    await save_settings_async(settings)
    context.user_data.pop("preset_editing", None)
    
    await update.message.reply_text(
        f"✅ *{field.title()}* diperbarui!",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")]]),
    )


def main():
    s_temp = json.loads(SETTINGS_FILE.read_text()) if SETTINGS_FILE.exists() else {}
    token = s_temp.get("bot_token") or os.environ.get("BOT_TOKEN", "")
    if not token:
        print("❌ Bot token belum diset.")
        return
    print("🤖 Starting Gmail Factory Bot v4 Perfected...")
    from telegram.request import HTTPXRequest
    request = HTTPXRequest(connect_timeout=30, read_timeout=30, write_timeout=30, pool_timeout=30)
    app = Application.builder().token(token).request(request).build()

    wizard_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(wizard_start, pattern="^menu_start_session$")],
        states={
            KEYWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, wizard_keyword)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, wizard_password)],
            COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, wizard_count)],
            POSITION: [CallbackQueryHandler(wizard_position, pattern="^pos_.*$")],
        },
        fallbacks=[CommandHandler("cancel", wizard_cancel)],
        allow_reentry=True
    )
    app.add_handler(wizard_handler)
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("session", cmd_session))
    app.add_handler(CommandHandler("generate", cmd_generate))
    app.add_handler(CommandHandler("go", cmd_go))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("resume", cmd_resume))
    app.add_handler(CommandHandler("balance", cmd_balance))
    app.add_handler(CommandHandler("saldo", cmd_balance))
    app.add_handler(CommandHandler("apidebug", cmd_apidebug))
    app.add_handler(CommandHandler("numbers", cmd_numbers))
    app.add_handler(CommandHandler("accounts", cmd_accounts))
    app.add_handler(CommandHandler("export", cmd_export))
    app.add_handler(CommandHandler("settings", cmd_settings))
    app.add_handler(CommandHandler("settoken", cmd_settoken))
    app.add_handler(CommandHandler("setbirth", cmd_setbirth))
    app.add_handler(CommandHandler("setproduct", cmd_setproduct))
    app.add_handler(CommandHandler("setgender", cmd_setgender))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("setpreset", cmd_setpreset))
    app.add_handler(CommandHandler("setsheet", cmd_setsheet))
    app.add_handler(CommandHandler("scan", cmd_scan_custom))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_preset_input))
    app.add_handler(CallbackQueryHandler(callback_handler))

    while True:
        try:
            print("✅ Bot running. Press Ctrl+C to stop.")
            app.run_polling(drop_pending_updates=True)
            break
        except Exception as e:
            print(f"⚠️ Bot error: {e}. Retrying in 10 sec…")
            time.sleep(10)

if __name__ == "__main__":
    main()
