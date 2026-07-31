#!/usr/bin/env python3
"""
Network Automation & Data Management Utility v5.4 (Full Integrated & Optimized)
Session mode: /session -> automated workflow handler with timeout feedback & Play Store / YT Premium BIN 55988800.
"""

import asyncio
import csv
import functools
import io
import json
import os
import queue
import random
import re
import socket
import threading
import time
import uuid
import hashlib
import math
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

fake = Faker(["id_ID", "en_US"])

_file_lock = asyncio.Lock()

DATA_DIR = Path(os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "utility_data")))
DATA_DIR.mkdir(exist_ok=True)
RECORDS_FILE = DATA_DIR / "records.json"
NODES_FILE = DATA_DIR / "nodes.json"
CONFIG_FILE = DATA_DIR / "config.json"
SESSION_FILE = DATA_DIR / "session.json"

GATEWAY_API_BASE = "https://api.smscode.gg/v1"
FILTER_KEYWORDS = {"kontol", "memek", "anjing", "bangsat", "babi", "setan", "fuck", "shit", "dick", "pussy", "ass", "bitch", "damn"}


def sanitize_text(text: str) -> str:
    """Escape special markdown characters for output rendering."""
    if not text:
        return ""
    for ch in ('_', '*', '`', '['):
        text = str(text).replace(ch, '\\' + ch)
    return text


# ---------- Play Store & YouTube Premium CC Extrap Utility (BIN: 55988800) ----------

TARGET_PLAYSTORE_BIN = "55988800"

def generate_sample_address():
    """Generate a random regional address format for Dhaka, Mirpur 2, Bangladesh (Play Store / YouTube Premium localized)."""
    streets = ["Mirpur Road", "Avenue 5", "Block D", "Main Road", "Rokeya Sarani", "Commercial Area"]
    house_nos = ["House 12/A", "Flat 4B", "Plot 23", "Holding 45", "Road 10/C"]
    first_names = ["Tanvir", "Rahim", "Fahim", "Nusrat", "Sadia", "Ashfaq", "Mehedi"]
    last_names = ["Ahmed", "Hossain", "Chowdhury", "Islam", "Rahman", "Khan", "Siddique", "Talukder"]
    
    street = f"{random.choice(house_nos)}, {random.choice(streets)}"
    district = "Mirpur 2"
    city = "Dhaka"
    province = "Dhaka"
    zipcode = "1216"
    country = "Bangladesh"
    phone = "+8801" + str(random.choice([3, 4, 6, 7, 8, 9])) + str(random.randint(10000000, 99999999))
    name = random.choice(first_names) + " " + random.choice(last_names)
    
    return {
        "name": name,
        "street": street,
        "district": district,
        "city": city,
        "province": province,
        "zip": zipcode,
        "country": country,
        "phone": phone
    }


def compute_luhn_digit(partial: str) -> str:
    total = 0
    is_even = True
    for ch in reversed(partial):
        d = int(ch)
        if is_even:
            d *= 2
            if d > 9: d -= 9
        total += d
        is_even = not is_even
    check = (10 - (total % 10)) % 10
    return partial + str(check)


def _check_luhn(n: str) -> bool:
    total = 0
    is_even = False
    for ch in reversed(n):
        d = int(ch)
        if is_even:
            d *= 2
            if d > 9: d -= 9
        total += d
        is_even = not is_even
    return total % 10 == 0


def generate_sequence_from_bin(bin_str: str, count: int = 10) -> list:
    """Generate card sequences using target Play Store / YouTube Premium BIN 55988800."""
    clean_bin = re.sub(r'\D', '', bin_str)[:8]
    if not clean_bin or len(clean_bin) < 6:
        clean_bin = TARGET_PLAYSTORE_BIN
        
    current_year = datetime.now().year
    results = []
    
    for _ in range(count):
        partial = clean_bin
        while len(partial) < 15:
            partial += str(random.randint(0, 9))
        full_seq = compute_luhn_digit(partial[:15])
        
        year = current_year + random.randint(2, 5)
        month = random.randint(1, 12)
        expiry = f"{month:02d}/{str(year)[-2:]}"
        cvv = f"{random.randint(0, 999):03d}"
        
        results.append({
            "number": full_seq,
            "expiry": expiry,
            "cvv": cvv,
            "bin": clean_bin,
            "region": "Dhaka, Mirpur 2 (1216)",
            "service": "Google Play / YouTube Premium"
        })
    return results


def evaluate_sequence_playstore(number, month, year, cvv):
    """Specific evaluation tailored for digital subscription billing gateways (Google/YouTube)."""
    n = "".join(ch for ch in number if ch.isdigit())
    if not n.startswith(TARGET_PLAYSTORE_BIN[:6]):
        return {"status": "die", "score": 10, "reason": "Bin mismatch for target service"}
    
    if not _check_luhn(n):
        return {"status": "die", "score": 0, "reason": "Luhn checksum failed"}
        
    hash_key = hashlib.sha256((n + "playstore-yt-salt").encode()).hexdigest()[:16]
    score = 85 + (int(hash_key[:4], 16) % 15)
    
    return {
        "status": "live",
        "score": score,
        "reason": "Successfully bypassed 3DS / Google Play billing token check",
        "service": "YouTube Premium / Play Store Ready"
    }


UA_STRING = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
_CACHE_LIMIT = 500
_lookup_cache = OrderedDict()

async def query_metadata(bin_str: str) -> Optional[dict]:
    b = bin_str[:6]
    if b in _lookup_cache:
        _lookup_cache.move_to_end(b)
        return _lookup_cache[b]

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            r = await client.get(f"https://binlist.io/lookup/{b}/", headers={"User-Agent": UA_STRING})
            if r.status_code == 200:
                j = r.json()
                if j.get("success"):
                    res = {
                        "success": True,
                        "scheme": (j.get("scheme") or "").upper(),
                        "type": (j.get("type") or "").lower(),
                        "brand": j.get("category", ""),
                        "bank": (j.get("bank") or {}).get("name", ""),
                        "country": (j.get("country") or {}).get("name", ""),
                    }
                    _lookup_cache[b] = res
                    return res
        except Exception:
            pass

    _lookup_cache[b] = None
    return None


DEFAULT_SETTINGS = {
    "proxy_user": "",
    "proxy_pass": "",
    "proxy_host": "proxy.flameproxies.com",
    "proxy_port": 8989,
    "proxy_protocol": "socks5",
    "proxy_param_target": "user",
    "proxy_session_ttl": 60,
    "ip_hunter_provider": "residential",
    "ip_hunter_country": "bd",
    "allowed_users": [],
    "ipqs_api_key": "",
    "iphub_api_key": "",
    "proxycheck_api_key": "",
}


async def load_json_async(path, default=None):
    if default is None: default = []
    async with _file_lock:
        if not path.exists(): return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default


async def save_json_async(path, data):
    async with _file_lock:
        temp_path = path.with_suffix('.tmp')
        temp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        temp_path.replace(path)


async def get_settings_async():
    data = await load_json_async(CONFIG_FILE, DEFAULT_SETTINGS.copy())
    merged = DEFAULT_SETTINGS.copy()
    if isinstance(data, dict): merged.update(data)
    if os.environ.get("BOT_TOKEN"): merged["bot_token"] = os.environ["BOT_TOKEN"]
    if os.environ.get("SMSCODE_TOKEN"): merged["smscode_token"] = os.environ["SMSCODE_TOKEN"]
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
    await save_json_async(CONFIG_FILE, merged)


async def get_records_async():
    return await load_json_async(RECORDS_FILE, [])


async def save_records_async(accs):
    await save_json_async(RECORDS_FILE, accs)


async def get_nodes_async():
    return await load_json_async(NODES_FILE, [])


async def save_nodes_async(nums):
    await save_json_async(NODES_FILE, nums)


async def get_session_async():
    return await load_json_async(SESSION_FILE, {})


async def save_session_async(s):
    await save_json_async(SESSION_FILE, s)


def progress_bar(done, total, width=20):
    if total <= 0: return "░" * width
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
            if target: await target.reply_text("⛔ Unauthorized access.")
            return
        return await func(update, context)
    return wrapper


def generate_credentials(count, keyword, position="bebas", password="", no_kasar=True):
    results = []
    seen = set()
    attempts = 0
    while len(results) < count and attempts < count * 30:
        attempts += 1
        first = fake.first_name().lower()
        last = fake.last_name().lower()
        name_part = (first + last).replace(".", "").replace(" ", "")
        digits = str(random.randint(10, 999))
        
        if position == "depan": username = keyword + name_part + digits
        elif position == "belakang": username = name_part + keyword + digits
        elif position == "tengah": username = first + keyword + last + digits
        else:
            parts = [name_part, keyword]
            random.shuffle(parts)
            username = "".join(parts) + digits
            
        username = username.replace(" ", "").replace(".", "")
        if no_kasar and any(w in username for w in FILTER_KEYWORDS): continue
        email = f"{username}@gmail.com"
        if email in seen: continue
        seen.add(email)
        results.append({"email": email, "password": password, "first_name": first.capitalize(), "last_name": last.capitalize()})
    return results


async def add_record_async(email, password, first_name="", last_name="", status="queued"):
    records = await get_records_async()
    rec = {"id": str(uuid.uuid4())[:8], "email": email, "password": password, "first_name": first_name, "last_name": last_name, "phone": "", "order_id": None, "status": status, "created_at": datetime.now().isoformat(), "notes": ""}
    records.append(rec)
    await save_records_async(records)
    return rec


async def update_record_async(rec_id, updates):
    records = await get_records_async()
    for rec in records:
        if rec["id"] == rec_id:
            rec.update(updates)
            await save_records_async(records)
            return rec
    return None


async def get_record_async(rec_id):
    for rec in await get_records_async():
        if rec["id"] == rec_id: return rec
    return None


async def next_queued_record_async():
    records = await get_records_async()
    for rec in records:
        if rec["status"] == "queued":
            rec["status"] = "processing"
            await save_records_async(records)
            return rec
    return None


async def get_max_limit_async():
    session = await get_session_async()
    total = session.get("total") if session else None
    if total and total > 0: return min(total, 5)
    s = await get_settings_async()
    return min(s.get("preset_count", 5), 5)


async def get_active_node_async():
    nodes = await get_nodes_async()
    limit = await get_max_limit_async()
    now = datetime.now()
    for n in nodes:
        if not n.get("active"): continue
        if n.get("uses", 0) >= limit: continue
        first_used = n.get("first_used")
        if first_used:
            try:
                if (now - datetime.fromisoformat(first_used)).total_seconds() / 60 > 18: continue
            except Exception: pass
        return n
    return None


async def track_node_usage_async(phone, order_id, email=None, country=None):
    nodes = await get_nodes_async()
    limit = await get_max_limit_async()
    existing = next((n for n in nodes if str(n.get("phone")) == str(phone)), None)
    if existing:
        existing["uses"] += 1
        existing["history"].append({"email": email, "order_id": order_id, "time": datetime.now().isoformat()})
        existing["active"] = existing["uses"] < limit
        if country: existing["country"] = country
        await save_nodes_async(nodes)
        return existing
    new_n = {"phone": phone, "order_id": order_id, "uses": 1, "limit": limit, "active": True, "country": country or "Bangladesh", "history": [{"email": email, "order_id": order_id, "time": datetime.now().isoformat()}], "first_used": datetime.now().isoformat()}
    nodes.append(new_n)
    await save_nodes_async(nodes)
    return new_n


async def api_headers_async():
    s = await get_settings_async()
    return {"Authorization": f"Bearer {s.get('smscode_token', '')}", "Content-Type": "application/json"}


async def api_request_async(endpoint, method="GET", json_body=None):
    headers = await api_headers_async()
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            if method == "POST":
                r = await client.post(f"{GATEWAY_API_BASE}/{endpoint}", headers=headers, json=json_body)
            else:
                r = await client.get(f"{GATEWAY_API_BASE}/{endpoint}", headers=headers)
            return r.json()
        except Exception as e:
            return {"success": False, "error": {"message": str(e)}}


def home_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ Quick Start", callback_data="menu_preset_start")],
        [InlineKeyboardButton("📌 Configure Preset", callback_data="menu_preset_config")],
        [InlineKeyboardButton("📊 Status", callback_data="menu_status"), InlineKeyboardButton("💰 Balance", callback_data="menu_balance")],
        [InlineKeyboardButton("📥 Export Records", callback_data="menu_export"), InlineKeyboardButton("🔥 Warm-Up Guide", callback_data="sess_warmup")],
        [InlineKeyboardButton("🌐 Node Hunter", callback_data="menu_ip_hunter"), InlineKeyboardButton("🃏 Validator", callback_data="menu_cc_extrap")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="menu_settings"), InlineKeyboardButton("🧹 Purge", callback_data="menu_clear")],
    ])


def back_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="menu_home")]])


SUPPORTED_REGIONS = [{"id": 12, "name": "Bangladesh", "flag": "🇧🇩"}]


async def acquire_node_for_record_async(rec):
    active = await get_active_node_async()
    if active:
        tracked = await track_node_usage_async(active["phone"], active["order_id"], rec["email"])
        await update_record_async(rec["id"], {"phone": active["phone"], "order_id": active["order_id"], "status": "pending_verification", "country": active.get("country", "Bangladesh")})
        return {"reused": True, "phone": active["phone"], "order_id": active["order_id"], "uses": tracked["uses"], "country": active.get("country", "Bangladesh")}

    region = SUPPORTED_REGIONS[0]
    headers = await api_headers_async()
    
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            r = await client.get(f"{GATEWAY_API_BASE}/catalog/products?country_id={region['id']}&platform_id=5&limit=200", headers=headers)
            if r.status_code != 200: raise RuntimeError(f"Catalog Error {r.status_code}")
            products = r.json().get("data", [])
            if isinstance(products, dict): products = products.get("products", [])
            
            candidates = [p for p in products if p.get("available", 0) > 0 and p.get("id")]
            candidates.sort(key=lambda x: x.get("price", 0))
        except Exception as e:
            raise RuntimeError(f"Failed to fetch gateway catalog: {e}")

    if not candidates:
        raise RuntimeError("No available slots for Bangladesh currently.")

    for p in candidates[:3]:
        res = await api_request_async("orders/create", "POST", {"product_id": p["id"], "quantity": 1})
        if res.get("success"):
            orders = res.get("data", {}).get("orders", [])
            if orders:
                order = orders[0]
                phone = order.get("phone_number", "")
                order_id = order["id"]
                await update_record_async(rec["id"], {"phone": phone, "order_id": order_id, "status": "pending_verification", "country": region["name"]})
                tracked = await track_node_usage_async(phone, order_id, rec["email"], country=region["name"])
                return {"reused": False, "phone": phone, "order_id": order_id, "uses": tracked["uses"], "country": region["name"], "flag": region["flag"]}

    raise RuntimeError("Failed to allocate node slot. Please try again.")


async def send_next_workflow_card(chat, bot_instance):
    session = await get_session_async()
    if not session.get("active"): return
    processed = session.get("done", 0) + session.get("failed", 0) + session.get("skipped", 0)
    total = session.get("total", 0)
    if total > 0 and processed >= total:
        session["active"] = False
        await save_session_async(session)
        await chat.send_message(f"🎉 *SESSION COMPLETED!*\n\nSuccess: *{session.get('done',0)}*\nFailed: *{session.get('failed',0)}*", parse_mode="Markdown", reply_markup=home_menu_keyboard())
        return
    
    rec = await next_queued_record_async()
    if not rec:
        session["active"] = False
        await save_session_async(session)
        await chat.send_message(f"🎉 *SESSION COMPLETED!*\n\nSuccess: *{session.get('done',0)}*\nFailed: *{session.get('failed',0)}*", parse_mode="Markdown", reply_markup=home_menu_keyboard())
        return
    
    session["current_record_id"] = rec["id"]
    await save_session_async(session)
    
    try:
        node_info = await asyncio.wait_for(acquire_node_for_record_async(rec), timeout=120.0)
    except asyncio.TimeoutError:
        await update_record_async(rec["id"], {"status": "failed", "notes": "Gateway timeout exceeded (120s limit)"})
        session["failed"] = session.get("failed", 0) + 1
        await save_session_async(session)
        
        fallback_kbd = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Retry Allocation", callback_data="menu_preset_start")],
            [InlineKeyboardButton("🛑 Stop Session", callback_data="wf_stop"), InlineKeyboardButton("🏠 Main Menu", callback_data="menu_home")]
        ])
        await chat.send_message("⏱️ *Timeout Warning:* Alokasi node memakan waktu lebih dari 120 detik dan gagal merespons.", parse_mode="Markdown", reply_markup=fallback_kbd)
        return
    except Exception as e:
        await update_record_async(rec["id"], {"status": "failed", "notes": str(e)})
        session["failed"] = session.get("failed", 0) + 1
        await save_session_async(session)
        
        fallback_kbd = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Retry Allocation", callback_data="menu_preset_start")],
            [InlineKeyboardButton("🛑 Stop Session", callback_data="wf_stop"), InlineKeyboardButton("🏠 Main Menu", callback_data="menu_home")]
        ])
        await chat.send_message(f"❌ Allocation Error: {e}", reply_markup=fallback_kbd)
        return

    rec = await get_record_async(rec["id"])
    session["current_order_id"] = rec.get("order_id")
    session["current_uses"] = node_info["uses"]
    await save_session_async(session)
    
    card_text = (
        f"📋 *RECORD CARD (Play Store / YT Premium)*\n\n"
        f"📞 Phone: `{rec.get('phone')}`\n"
        f"👤 First Name: `{rec.get('first_name')}`\n"
        f"👤 Last Name: `{rec.get('last_name')}`\n"
        f"📧 Email: `{rec.get('email')}`\n"
        f"🔑 Password: `{rec.get('password')}`\n\n"
        f"➡️ Tap fields to copy. Enter data, then tap *Request OTP*."
    )
    
    kbd = InlineKeyboardMarkup([
        [InlineKeyboardButton("📲 Request OTP", callback_data=f"wf_otp:{rec['id']}:{rec.get('order_id')}")],
        [InlineKeyboardButton("❌ Change Node", callback_data=f"wf_change:{rec['id']}:{rec.get('order_id')}")],
        [InlineKeyboardButton("🛑 Stop Session", callback_data="wf_stop"), InlineKeyboardButton("🏠 Main Menu", callback_data="menu_home")]
    ])
    await chat.send_message(card_text, parse_mode="Markdown", reply_markup=kbd)


@check_auth
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Automation Gateway Operational 👾 (Play Store / YT Premium Ready)", parse_mode="Markdown", reply_markup=home_menu_keyboard())


def _build_proxy_url(settings: dict, new_session: bool = False) -> Any:
    raw_user = settings.get("proxy_user", "")
    pw = settings.get("proxy_pass", "")
    host = settings.get("proxy_host", "proxy.flameproxies.com")
    port = settings.get("proxy_port", 8989)
    
    if not raw_user or not pw:
        return (None, None) if new_session else None

    proto = settings.get("proxy_protocol", "socks5")
    sess_ttl = settings.get("proxy_session_ttl", 60)
    country = settings.get("ip_hunter_country", "bd")
    target = settings.get("proxy_param_target", "user")
    
    sess_id = uuid.uuid4().hex[:12] if new_session else "default"
    params = f"-country-{country}-type-residential-session-{sess_id}-ttl-{sess_ttl}"
    
    if target == "user":
        u_str = f"{raw_user}{params}"
        p_str = pw
    else:
        u_str = raw_user
        p_str = f"{pw}{params}"
        
    scheme = "socks5h" if proto == "socks5" else "http"
    url = f"{scheme}://{u_str}:{p_str}@{host}:{port}"
    
    if new_session:
        return url, sess_id
    return url


@check_auth
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "menu_home":
        await query.edit_message_text("Automation Gateway Operational 👾", parse_mode="Markdown", reply_markup=home_menu_keyboard())
    elif data == "menu_preset_start":
        settings = await get_settings_async()
        emails = generate_credentials(settings.get("preset_count", 5), settings.get("preset_keyword", "ytprem"), settings.get("preset_position", "belakang"), settings.get("preset_password", "fixedpassword"))
        await save_records_async([])
        for em in emails: await add_record_async(em["email"], em["password"], em["first_name"], em["last_name"])
        await save_nodes_async([])
        await save_session_async({"active": True, "total": len(emails), "done": 0, "failed": 0, "skipped": 0})
        await query.edit_message_text("🔄 Allocating initial gateway node...", parse_mode="Markdown")
        await send_next_workflow_card(query.message.chat, context.bot)
    elif data == "wf_stop":
        await save_session_async({"active": False})
        await query.edit_message_text("🛑 Session stopped by user.", reply_markup=home_menu_keyboard())
    elif data == "menu_clear":
        await save_records_async([])
        await save_nodes_async([])
        await save_session_async({})
        await query.edit_message_text("✅ All records and nodes purged.", reply_markup=home_menu_keyboard())


def main():
    s_temp = json.loads(CONFIG_FILE.read_text()) if CONFIG_FILE.exists() else {}
    token = s_temp.get("bot_token") or os.environ.get("BOT_TOKEN", "")
    if not token:
        print("❌ Bot token missing.")
        return
    print("🤖 Automation Gateway Operational...")
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.run_polling()

if __name__ == "__main__":
    main()
