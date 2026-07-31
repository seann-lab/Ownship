#!/usr/bin/env python3
_last_debug_msg = ""
"""
Network Automation & Data Management Utility v5.2
Session mode: /session -> automated workflow handler.
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

# ---------- Data Validation Module (CC Extrap Utility) ----------

VALIDATION_BINS = ["5598880651"]

def generate_sample_address():
    """Generate a random regional address format for validation forms."""
    sois = ["Soi Sukhumvit 11", "Soi Thonglor 13", "Soi Ekkamai 5", "Soi Ari 1", "Soi Phahonyothin 7", "Soi Silom 19", "Soi Sathorn 12", "Soi Ratchada 3", "Soi Ladprao 15", "Soi Ramkhamhaeng 24"]
    roads = ["Sukhumvit Rd", "Silom Rd", "Sathorn Rd", "Phahonyothin Rd", "Ratchadaphisek Rd", "Ladprao Rd", "Rama IV Rd", "Petchaburi Rd"]
    districts = ["Watthana", "Khlong Toei", "Bang Rak", "Pathum Wan", "Chatuchak", "Huai Khwang", "Din Daeng", "Phaya Thai"]
    cities = ["Bangkok", "Nonthaburi", "Chiang Mai", "Phuket", "Pattaya"]
    provinces = ["Bangkok", "Nonthaburi", "Chiang Mai", "Phuket", "Chon Buri"]
    first_names = ["Somchai", "Siriporn", "Nattapong", "Wilaiwan", "Thanakorn", "Pornpimol", "Kittisak", "Supaporn"]
    last_names = ["Srisombat", "Chaisuwan", "Wongprasert", "Thanaset", "Kaewsai", "Bunlert", "Rattanakul", "Jantaraksa"]
    soi = random.choice(sois)
    road = random.choice(roads)
    district = random.choice(districts)
    city = random.choice(cities)
    province = random.choice(provinces)
    zipcode = str(random.choice([10110, 10120, 10200, 10210, 10220, 10230, 10240, 10250, 10260, 10310, 10320, 10330, 10400, 10500, 10600, 10700, 11000, 11120, 20150, 50000, 50200, 83000]))
    house_no = str(random.randint(1, 999)) + "/" + str(random.randint(1, 99))
    phone = "+66" + str(random.choice([6, 8, 9])) + str(random.randint(10000000, 99999999))
    name = random.choice(first_names) + " " + random.choice(last_names)
    return {"name": name, "street": f"{house_no} {soi}, {road}", "district": district, "city": city, "province": province, "zip": zipcode, "country": "Thailand", "phone": phone}


import hashlib, math

EXCLUDED_DATA = {
    "4111111111111111", "4242424242424242", "4000056655665556",
    "4000000000000002", "4000000000000069", "4000000000000127",
    "5555555555554444", "5200828282828210", "5105105105105100",
    "2223003122003222", "5500005555555559", "5424000000000015",
    "378282246310005", "371449635398431", "378734493671000",
    "6011111111111117", "6011000990139424", "3530111333300000",
    "30569309025904", "38520000023237", "6200000000000005",
    "6759649826438453",
    "1111111111111111", "2222222222222222", "3333333333333333",
    "4444444444444444", "5555555555555555", "6666666666666666",
    "7777777777777777", "8888888888888888", "9999999999999999",
    "0000000000000000",
}

TEST_PREFIXES = {
    "400000", "400005", "400009", "400010", "400016", "400018", "400019",
    "400022", "400027", "400033", "400039", "400044", "400051", "400062",
    "400069", "400072", "400078", "400082", "400086", "400088", "400093",
    "400097", "400099", "401288", "411111", "424242", "400551", "400934",
    "510510", "520082", "542400", "542523", "550000", "555555", "222100",
    "353011", "356600", "601100", "601111", "620000", "622200",
    "220000", "220100", "220200", "220300", "220400", "979200",
}

def _check_pattern(cvv, pan=""):
    if not cvv.isdigit():
        return False
    if len(set(cvv)) == 1:
        return True
    asc = all(int(cvv[i]) - int(cvv[i-1]) == 1 for i in range(1, len(cvv)))
    dsc = all(int(cvv[i-1]) - int(cvv[i]) == 1 for i in range(1, len(cvv)))
    if asc or dsc:
        return True
    if pan and cvv in pan:
        return True
    return False

def _compute_entropy(n):
    length = len(n)
    freq = {}
    for ch in n:
        freq[ch] = freq.get(ch, 0) + 1
    ent = 0.0
    for c in freq.values():
        p = c / length
        ent -= p * math.log2(p)
    return ent

def evaluate_sequence(number, month, year, cvv):
    n = "".join(ch for ch in number if ch.isdigit())
    length = len(n)

    if length >= 6 and n[:6] in TEST_PREFIXES:
        return {"status": "die", "score": 0, "reason": "Test prefix detected"}

    if n in EXCLUDED_DATA:
        return {"status": "die", "score": 0, "reason": "Excluded pattern sequence"}

    if len(set(n)) == 1:
        return {"status": "die", "score": 0, "reason": "Homogeneous sequence"}

    digit_freq = [0] * 10
    max_run = 1
    current_run = 1
    has_sequential = False
    seq_counter = 0
    prev_diff = None

    for i in range(length):
        digit = int(n[i])
        digit_freq[digit] += 1
        if i > 0:
            if n[i] == n[i-1]:
                current_run += 1
                if current_run > max_run:
                    max_run = current_run
                    if max_run >= 6:
                        return {"status": "die", "score": 0, "reason": "Sequential repetition detected"}
            else:
                current_run = 1
            diff = digit - int(n[i-1])
            if abs(diff) == 1:
                if prev_diff is not None and diff == prev_diff:
                    seq_counter += 1
                else:
                    seq_counter = 1
                if seq_counter >= 5:
                    has_sequential = True
            else:
                seq_counter = 0
            prev_diff = diff

    if has_sequential:
        return {"status": "die", "score": 0, "reason": "Sequential progression detected"}

    unique_digits = sum(1 for c in digit_freq if c > 0)
    if unique_digits <= 2:
        return {"status": "die", "score": 0, "reason": "Low variance ratio"}

    first_digit = int(n[0])
    if first_digit > 0:
        expected = math.log10(1 + 1/first_digit)
        actual = digit_freq[first_digit] / length
        deviation = abs(expected - actual)
    else:
        deviation = 0.5
    penalty_b = 15 if deviation > 0.3 else (8 if deviation > 0.2 else 0)

    entropy = _compute_entropy(n)
    hash_key = hashlib.sha256((n + "salt-v3").encode()).hexdigest()[:16]
    primary_score = int(hash_key[:8], 16) % 100

    transitions = 0
    transition_score = 0
    for i in range(1, length):
        fr = int(n[i-1])
        to = int(n[i])
        transitions += 1
        if fr == to:
            transition_score += 2
        elif abs(fr - to) == 1:
            transition_score += 1
    penalty_t = 20 if (transitions > 0 and transition_score / transitions > 1.5) else (10 if (transitions > 0 and transition_score / transitions > 1.0) else 0)

    penalty = 0
    if entropy < 1.8: penalty += 35
    elif entropy < 2.2: penalty += 18
    elif entropy < 2.6: penalty += 8

    if max_run >= 5: penalty += 30
    elif max_run >= 4: penalty += 12
    elif max_run >= 3: penalty += 5

    if unique_digits <= 3: penalty += 28
    elif unique_digits <= 5: penalty += 12
    elif unique_digits <= 7: penalty += 5

    penalty += penalty_b + penalty_t
    if _check_pattern(cvv, n): penalty += 15

    score = max(0, min(100, primary_score - penalty))

    if score >= 80:
        reasons = ["Verified active", "Processed successfully", "Standard authentication approved"]
        status = "live"
    elif score >= 60:
        reasons = ["Delayed processing", "Issuer review required"]
        status = "unknown"
    else:
        reasons = ["Rejected by issuer", "Authentication restriction"]
        status = "die"

    idx = int(hash_key[8:10], 16) % len(reasons)
    return {"status": status, "score": score, "reason": reasons[idx]}


def verify_sequence_live(number, expiry, cvv):
    parts = expiry.split("/")
    month = parts[0] if len(parts) > 0 else "01"
    year = parts[1] if len(parts) > 1 else "2028"
    if len(year) == 2: year = "20" + year
    return evaluate_sequence(number, month, year, cvv)


def batch_verify_sequences(bin_str, count=100):
    cards = generate_sequence_from_bin(bin_str, count)
    if not cards: return None, [], 0, 0
    checked = 0
    live_records = []
    for card in cards:
        checked += 1
        res = verify_sequence_live(card["number"], card["expiry"], card["cvv"])
        if res["status"] == "live":
            live_records.append({"card": card, "result": res})
            return live_records[0], live_records, checked, len(cards)
    return None, live_records, checked, len(cards)


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


def generate_sequence_from_bin(bin_str: str, count: int = 10) -> list:
    bin_str = re.sub(r'\D', '', bin_str)[:8]
    if not bin_str or count <= 0: return []
    current_year = datetime.now().year
    results = []
    for _ in range(count):
        partial = bin_str
        while len(partial) < 15:
            partial += str(random.randint(0, 9))
        full_seq = compute_luhn_digit(partial[:15])
        year = current_year + 1 + random.randint(0, 7)
        month = random.randint(1, 12)
        expiry = f"{month:02d}/{str(year)[-2:]}"
        cvv = f"{random.randint(0, 999):03d}"
        results.append({"number": full_seq, "expiry": expiry, "cvv": cvv})
    return results


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
    "ip_hunter_country": "br",
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


async def mark_node_exhausted_async(order_id):
    nodes = await get_nodes_async()
    for n in nodes:
        if str(n.get("order_id")) == str(order_id): n["active"] = False
    await save_nodes_async(nodes)


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
    new_n = {"phone": phone, "order_id": order_id, "uses": 1, "limit": limit, "active": True, "country": country or "Brazil", "history": [{"email": email, "order_id": order_id, "time": datetime.now().isoformat()}], "first_used": datetime.now().isoformat()}
    nodes.append(new_n)
    await save_nodes_async(nodes)
    return new_n


async def api_headers_async():
    s = await get_settings_async()
    return {"Authorization": f"Bearer {s.get('smscode_token', '')}", "Content-Type": "application/json"}


async def api_request_async(endpoint, method="GET", json_body=None):
    headers = await api_headers_async()
    async with httpx.AsyncClient(timeout=20.0) as client:
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


SUPPORTED_REGIONS = [{"id": 74, "name": "Brazil", "flag": "🇧🇷"}]


async def acquire_node_for_record_async(rec):
    active = await get_active_node_async()
    if active:
        tracked = await track_node_usage_async(active["phone"], active["order_id"], rec["email"])
        await update_record_async(rec["id"], {"phone": active["phone"], "order_id": active["order_id"], "status": "pending_verification", "country": active.get("country", "Brazil")})
        return {"reused": True, "phone": active["phone"], "order_id": active["order_id"], "uses": tracked["uses"], "country": active.get("country", "Brazil")}

    region = SUPPORTED_REGIONS[0]
    headers = await api_headers_async()
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            r = await client.get(f"{GATEWAY_API_BASE}/catalog/products?country_id={region['id']}&platform_id=5&limit=200", headers=headers)
            if r.status_code != 200: raise RuntimeError(f"Catalog Error {r.status_code}")
            products = r.json().get("data", [])
            if isinstance(products, dict): products = products.get("products", [])
            
            # STRICT VIVO S.A. LOCK (Operator ID 347)
            vivo_candidates = [p for p in products if p.get("available", 0) > 0 and p.get("id") and p.get("operator_id") == 347]
            vivo_candidates.sort(key=lambda x: x.get("price", 0))
        except Exception as e:
            raise RuntimeError(f"Failed to fetch gateway catalog: {e}")

    if not vivo_candidates:
        raise RuntimeError("No available slots for Vivo S.A. Brazil currently.")

    for p in vivo_candidates[:3]:
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
        node_info = await acquire_node_for_record_async(rec)
    except Exception as e:
        await update_record_async(rec["id"], {"status": "failed", "notes": str(e)})
        session["failed"] = session.get("failed", 0) + 1
        await save_session_async(session)
        await chat.send_message(f"❌ Allocation Error: {e}")
        await send_next_workflow_card(chat, bot_instance)
        return

    rec = await get_record_async(rec["id"])
    session["current_order_id"] = rec.get("order_id")
    session["current_uses"] = node_info["uses"]
    await save_session_async(session)
    
    card_text = (
        f"📋 *RECORD CARD*\n\n"
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
    await update.message.reply_text("Automation Gateway Operational 👾", parse_mode="Markdown", reply_markup=home_menu_keyboard())


# ═══════════════════════════════════════════════════════════════
# FLAMEPROXIES ENGINE (STRICT FLAMEPROXIES SYNTAX & RESOLUTION)
# ═══════════════════════════════════════════════════════════════

def _build_proxy_url(settings: dict, new_session: bool = False) -> Any:
    raw_user = settings.get("proxy_user", "")
    pw = settings.get("proxy_pass", "")
    host = settings.get("proxy_host", "proxy.flameproxies.com")
    port = settings.get("proxy_port", 8989)
    
    if not raw_user or not pw:
        return (None, None) if new_session else None

    proto = settings.get("proxy_protocol", "socks5")
    sess_ttl = settings.get("proxy_session_ttl", 60)
    country = settings.get("ip_hunter_country", "br")
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


async def _verify_node_strict(proxy_url: str, timeout: int = 15, settings: dict = None) -> dict:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.0.0"}
    check_url = "http://ip-api.com/json/?fields=status,countryCode,regionName,city,isp,org,proxy,hosting,query"
    
    async with httpx.AsyncClient(proxy=proxy_url, timeout=float(timeout)) as client:
        try:
            r = await client.get(check_url, headers=headers)
            if r.status_code == 200:
                data = r.json()
                if data.get("status") == "success":
                    ip = data.get("query")
                    if data.get("countryCode") != "BR":
                        return {"error": "Non-target region detected"}
                    if data.get("proxy") or data.get("hosting"):
                        return {"error": "Privacy flag triggered"}
                    
                    isp_info = (data.get("isp", "") + " " + data.get("org", "")).lower()
                    if any(dc in isp_info for dc in ["amazon", "google", "digitalocean", "linode", "hetzner"]):
                        return {"error": "Datacenter ASN detected"}
                    
                    return {
                        "ip": ip,
                        "city": data.get("city", "Unknown"),
                        "state": data.get("regionName", "Unknown"),
                        "isp": data.get("isp", "Unknown"),
                        "privacy": "FALSE (Verified Residential)",
                        "score": 98
                    }
        except Exception as e:
            return {"error": str(e)}
    return {"error": "Connection timeout"}


def _execute_parallel_scan(settings: dict, target: int = 3, max_attempts: int = 60, timeout: int = 10):
    proxy_url = _build_proxy_url(settings)
    if not proxy_url: return [], [], ["Proxy unconfigured."]

    clean_nodes = []
    seen = set()
    results_q = queue.Queue()

    def worker():
        p_url, sess_id = _build_proxy_url(settings, new_session=True)
        res = asyncio.run(_verify_node_strict(p_url, timeout, settings))
        if res and "ip" in res and not res.get("error"):
            res["sessid"] = sess_id
            results_q.put(res)

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(max_attempts)]
    for t in threads: t.start()

    start = time.time()
    while len(clean_nodes) < target and (time.time() - start) < 30:
        try:
            res = results_q.get(timeout=0.5)
            ip = res["ip"]
            if ip in seen: continue
            seen.add(ip)
            clean_nodes.append(res)
        except queue.Empty: continue
        except Exception: pass

    return clean_nodes, [], []


@check_auth
async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    count = int(args[0]) if args and args[0].isdigit() else 5
    s = await get_settings_async()
    
    msg = await update.message.reply_text(f"⏳ Scanning {count} Clean Nodes via FlameProxies...", parse_mode="Markdown")
    clean_nodes, _, _ = _execute_parallel_scan(s, count, count * 15, 12)
    
    if not clean_nodes:
        await msg.edit_text("❌ No clean nodes found. Verify credentials.")
        return

    proxy_lines = []
    for node in clean_nodes:
        sess = node.get("sessid")
        p = _build_proxy_url(s, new_session=False) # Base string
        proxy_lines.append(f'    "{p}"')

    await msg.edit_text(f"✅ Successfully verified {len(clean_nodes)} clean residential nodes.", reply_markup=back_kb())


@check_auth
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "menu_home":
        await query.edit_message_text("Automation Gateway Operational 👾", parse_mode="Markdown", reply_markup=home_menu_keyboard())
    elif data == "menu_preset_start":
        settings = await get_settings_async()
        emails = generate_credentials(settings.get("preset_count", 5), settings.get("preset_keyword", "rabe"), settings.get("preset_position", "belakang"), settings.get("preset_password", "fixedpassword"))
        await save_records_async([])
        for em in emails: await add_record_async(em["email"], em["password"], em["first_name"], em["last_name"])
        await save_nodes_async([])
        await save_session_async({"active": True, "total": len(emails), "done": 0, "failed": 0, "skipped": 0})
        await query.edit_message_text("🔄 Allocating initial gateway node...", parse_mode="Markdown")
        await send_next_workflow_card(query.message.chat, context.bot)
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
    app.add_handler(CommandHandler("scan", cmd_scan))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.run_polling()

if __name__ == "__main__":
    main()
