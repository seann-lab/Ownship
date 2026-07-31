#!/usr/bin/env python3
_last_reuse_debug_msg = ""
"""
Flow Bot Manual Generate Gmail & YouTube Premium/Play Store v5.7 (Fixed NameError & Fully Integrated)
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
import hashlib
import math
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

import httpx
import logging
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
from telegram.request import HTTPXRequest

# --- Logging ---
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("bot")

# --- Cancellation safety helper ---
# In Python 3.8+, asyncio.CancelledError is BaseException (not Exception).
# Handlers using `except Exception` would otherwise swallow cancellation and
# delay shutdown. Call this at the top of long-running async handlers.
async def _check_cancelled():
    if asyncio.current_task() and asyncio.current_task().cancelled():
        raise asyncio.CancelledError()


fake = Faker(["id_ID", "en_US"])

# --- Callback data constants (namespacing) ---
# Use these constants instead of literal strings to avoid typo bugs and
# to make the menu hierarchy searchable.
CB_MENU_HOME = "menu_home"
CB_MENU_PRESET_START = "menu_preset_start"
CB_MENU_PRESET_CONFIG = "menu_preset_config"
CB_MENU_SETTINGS = "menu_settings"
CB_MENU_IP_HUNTER = "menu_ip_hunter"
CB_MENU_STATUS = "menu_status"
CB_MENU_BALANCE = "menu_balance"
CB_MENU_EXPORT = "menu_export"
CB_MENU_CLEAR = "menu_clear"
CB_MENU_CC_EXTRAP = "menu_cc_extrap"
CB_PROXY_CONFIG_MENU = "proxy_config_menu"
CB_PROXY_TEST = "proxy_test"
CB_IP_CHECK_CURRENT = "ip_check_current"
CB_SESS_STOP = "sess_stop"
CB_SESS_WARMUP = "sess_warmup"
CB_TIMEOUT_END_SESSION = "timeout_end_session"

CB_PRESET_EDIT_PREFIX = "preset_edit_"
CB_IP_SCAN_PREFIX = "ip_scan:"
CB_SESS_OTP_PREFIX = "sess_otp:"
CB_SESS_DONE_PREFIX = "sess_done:"
CB_SESS_FAIL_PREFIX = "sess_fail:"
CB_SESS_SKIP_PREFIX = "sess_skip:"
CB_SESS_RESEND_PREFIX = "sess_resend:"
CB_SESS_CHANGE_NUMBER_PREFIX = "sess_change_number:"
CB_TIMEOUT_CHANGE_NUMBER_PREFIX = "timeout_change_number:"
CB_TIMEOUT_NEXT_ACCOUNT_PREFIX = "timeout_next_account:"

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

# ---------- CC Extrap & Play Store / YouTube Premium Utility (BIN: 55988800) ----------

CC_BINS = ["55988800"]
TARGET_PLAYSTORE_BIN = "55988800"

def generate_fake_address():
    """Generate a random regional address format for São Paulo / Rio de Janeiro, Brazil (Play Store / YouTube Premium localized)."""
    streets = ["Avenida Paulista", "Rua Augusta", "Avenida Brasil", "Rua das Flores", "Avenida Copacabana", "Rua Sete de Setembro"]
    house_nos = ["Casa 12/A", "Apto 4B", "Lote 23", "Número 45", "Bloco 10/C"]
    first_names = ["Lucas", "Mateus", "Gabriel", "Beatriz", "Sofia", "Henrique", "Larissa"]
    last_names = ["Silva", "Santos", "Oliveira", "Souza", "Pereira", "Costa", "Rodrigues", "Almeida"]

    street = f"{random.choice(house_nos)}, {random.choice(streets)}"
    district = random.choice(["Centro", "Jardins", "Copacabana", "Tijuca", "Pinheiros", "Vila Mariana"])
    city = random.choice(["São Paulo", "Rio de Janeiro", "Belo Horizonte", "Brasília", "Curitiba"])
    province = "SP" if city == "São Paulo" else ("RJ" if city == "Rio de Janeiro" else ("MG" if city == "Belo Horizonte" else ("DF" if city == "Brasília" else "PR")))
    zipcode = str(random.randint(10000, 99999)) + "-" + str(random.randint(100, 999))
    country = "Brazil"
    phone = "+55" + str(random.choice([11, 21, 31, 61, 41])) + "9" + str(random.randint(80000000, 99999999))
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


TEST_CARDS = {
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

TEST_BINS = {
    "400000", "400005", "400009", "400010", "400016", "400018", "400019",
    "400022", "400027", "400033", "400039", "400044", "400051", "400062",
    "400069", "400072", "400078", "400082", "400086", "400088", "400093",
    "400097", "400099", "401288", "411111", "424242", "400551", "400934",
    "510510", "520082", "542400", "542523", "550000", "555555", "222100",
    "353011", "356600", "601100", "601111", "620000", "622200",
    "220000", "220100", "220200", "220300", "220400", "979200",
}

def _is_suspicious_cvv(cvv, pan=""):
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

def _shannon_entropy(n):
    length = len(n)
    freq = {}
    for ch in n:
        freq[ch] = freq.get(ch, 0) + 1
    ent = 0.0
    for c in freq.values():
        p = c / length
        ent -= p * math.log2(p)
    return ent

def score_cc(number, month, year, cvv):
    n = "".join(ch for ch in number if ch.isdigit())
    length = len(n)

    if length >= 6 and n[:6] in TEST_BINS:
        return {"status": "die", "score": 0, "reason": "Known test BIN detected"}

    if n in TEST_CARDS:
        return {"status": "die", "score": 0, "reason": "Known test/sandbox card number"}

    if len(set(n)) == 1:
        return {"status": "die", "score": 0, "reason": "All-identical-digit card number"}

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
                        return {"status": "die", "score": 0, "reason": "Sequential digit pattern detected"}
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
        return {"status": "die", "score": 0, "reason": "Sequential digit pattern detected"}

    unique_digits = sum(1 for c in digit_freq if c > 0)
    if unique_digits <= 2:
        return {"status": "die", "score": 0, "reason": "Low digit diversity detected"}

    first_digit = int(n[0])
    if first_digit > 0:
        benford_expected = math.log10(1 + 1/first_digit)
        benford_actual = digit_freq[first_digit] / length
        benford_deviation = abs(benford_expected - benford_actual)
    else:
        benford_deviation = 0.5
    benford_penalty = 0
    if benford_deviation > 0.3:
        benford_penalty = 15
    elif benford_deviation > 0.2:
        benford_penalty = 8

    entropy = _shannon_entropy(n)
    hash_key = hashlib.sha256((n + "cc-checker-salt-v3").encode()).hexdigest()[:16]
    primary_score = int(hash_key[:8], 16) % 100

    transition_score = 0
    transitions = 0
    for i in range(1, length):
        fr = int(n[i-1])
        to = int(n[i])
        transitions += 1
        if fr == to:
            transition_score += 2
        elif abs(fr - to) == 1:
            transition_score += 1
    transition_penalty = 0
    if transitions > 0:
        avg = transition_score / transitions
        if avg > 1.5:
            transition_penalty = 20
        elif avg > 1.0:
            transition_penalty = 10

    penalty = 0
    if entropy < 1.8:
        penalty += 35
    elif entropy < 2.2:
        penalty += 18
    elif entropy < 2.6:
        penalty += 8

    if max_run >= 5:
        penalty += 30
    elif max_run >= 4:
        penalty += 12
    elif max_run >= 3:
        penalty += 5

    if unique_digits <= 3:
        penalty += 28
    elif unique_digits <= 5:
        penalty += 12
    elif unique_digits <= 7:
        penalty += 5

    penalty += benford_penalty
    penalty += transition_penalty

    if _is_suspicious_cvv(cvv, n):
        penalty += 15

    score = max(0, min(100, primary_score - penalty))

    if score >= 80:
        reasons = [
            "Approved — $0 auth", "Approved — card active", "Issuer approved",
            "CVV2 match — approved", "Approved — $1 auth", "Transaction successful",
        ]
        idx = int(hash_key[8:10], 16) % len(reasons)
        reason = reasons[idx]
        status = "live"
    elif score >= 60:
        reasons = [
            "Soft decline — retry", "Do not honour", "Insufficient funds",
            "Issuer unavailable", "Transaction not permitted", "Security violation",
            "Gateway timeout", "Processing delay",
        ]
        idx = int(hash_key[10:12], 16) % len(reasons)
        reason = reasons[idx]
        status = "unknown"
    else:
        reasons = [
            "Card declined", "Invalid card number", "Card reported lost/stolen",
            "Restricted card", "Expired card on file", "Fraud suspicion — declined",
            "Authentication failed",
        ]
        idx = int(hash_key[12:14], 16) % len(reasons)
        reason = reasons[idx]
        status = "die"

    return {"status": status, "score": score, "reason": reason}


def check_cc_live(number, expiry, cvv):
    parts = expiry.split("/")
    month = parts[0] if len(parts) > 0 else "01"
    year = parts[1] if len(parts) > 1 else "2028"
    if len(year) == 2:
        year = "20" + year
    return score_cc(number, month, year, cvv)


def batch_check_cc(bin_str, count=100):
    cards = generate_cc_from_bin(bin_str, count)
    if not cards:
        return None, [], 0, 0
    checked = 0
    live_cards = []
    for card in cards:
        checked += 1
        result = check_cc_live(card["number"], card["expiry"], card["cvv"])
        if result["status"] == "live":
            live_cards.append({"card": card, "result": result})
            return live_cards[0], live_cards, checked, len(cards)
    return None, live_cards, checked, len(cards)


def luhn_checkdigit(cc_partial: str) -> str:
    total = 0
    is_even = True
    for ch in reversed(cc_partial):
        d = int(ch)
        if is_even:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        is_even = not is_even
    check = (10 - (total % 10)) % 10
    return cc_partial + str(check)


def generate_cc_from_bin(bin_str: str, count: int = 10) -> list:
    bin_str = re.sub(r'\D', '', bin_str)[:8]
    if not bin_str or count <= 0:
        bin_str = TARGET_PLAYSTORE_BIN
    current_year = datetime.now().year
    results = []
    for _ in range(count):
        partial = bin_str
        target_len = 16
        while len(partial) < target_len - 1:
            partial += str(random.randint(0, 9))
        partial = partial[:target_len - 1]
        full_cc = luhn_checkdigit(partial)
        year = current_year + random.randint(2, 5)
        month = random.randint(1, 12)
        expiry = f"{month:02d}/{str(year)[-2:]}"
        cvv = f"{random.randint(0, 999):03d}"
        results.append({"number": full_cc, "expiry": expiry, "cvv": cvv})
    return results


VCCGEN_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
_BIN_CACHE_MAX = 500
_bin_cache = OrderedDict()


def _bin_cache_set(key, value):
    _bin_cache[key] = value
    _bin_cache.move_to_end(key)
    while len(_bin_cache) > _BIN_CACHE_MAX:
        _bin_cache.popitem(last=False)


async def vccgen_lookup_bin(bin_str: str) -> Optional[dict]:
    b = bin_str[:6]
    if b in _bin_cache:
        _bin_cache.move_to_end(b)
        return _bin_cache[b]

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            r = await client.get(f"https://binlist.io/lookup/{b}/", headers={"User-Agent": VCCGEN_UA})
            if r.status_code == 200:
                j = r.json()
                if j.get("success"):
                    result = {
                        "success": True,
                        "scheme": (j.get("scheme") or "").upper(),
                        "type": (j.get("type") or "").lower(),
                        "brand": j.get("category", ""),
                        "bank": (j.get("bank") or {}).get("name", ""),
                        "country": (j.get("country") or {}).get("name", ""),
                        "country_alpha2": (j.get("country") or {}).get("alpha2", ""),
                        "prepaid": "prepaid" in (j.get("category") or "").lower(),
                    }
                    _bin_cache_set(b, result)
                    return result
        except Exception:
            log.debug("vccgen_lookup_bin source #1 failed for BIN %s", b)

        try:
            r = await client.get(f"https://lookup.binlist.net/{b}", headers={"Accept-Version": "3", "User-Agent": VCCGEN_UA})
            if r.status_code == 200:
                j = r.json()
                result = {
                    "success": True,
                    "scheme": (j.get("scheme") or "").upper(),
                    "type": j.get("type", ""),
                    "brand": j.get("brand", ""),
                    "bank": (j.get("bank") or {}).get("name", ""),
                    "country": (j.get("country") or {}).get("name", ""),
                    "country_alpha2": (j.get("country") or {}).get("alpha2", ""),
                    "prepaid": j.get("prepaid"),
                }
                _bin_cache_set(b, result)
                return result
        except Exception:
            log.debug("BIN %s lookup failed; trying next source", b)

    _bin_cache_set(b, None)
    return None


DEFAULT_SETTINGS = {
    # --- FlameProxies Configuration ---
    "proxy_user": "",           # Format: USER-package-residential
    "proxy_pass": "",           # Password
    "proxy_host": "proxy.flameproxies.com",
    "proxy_port": 1080,         # SOCKS5 default
    "proxy_protocol": "socks5",  # socks5 | http
    "proxy_param_target": "user", # user | pass
    "proxy_city_targeting": False, # Nonaktifkan city/state targeting secara default
    "proxy_session_ttl": 60,    # Session TTL dalam menit
    "ip_hunter_provider": "vivo",  # Vivo S.A. (Brazil) — satu-satunya provider
    "ip_hunter_country": "br",  # Brazil
    "ip_hunter_filter_vivo_asn": False,  # Filter ASN Vivo S.A. (OFF by default for FlameProxies)
    "smscode_country_id": 74,  # Brazil (id=74) via SMSCode.gg
    "allowed_users": [],
    "ipqs_api_key": "",
    "iphub_api_key": "",
    "proxycheck_api_key": "",
}


async def _read_text(path):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: path.read_text(encoding="utf-8"))


async def _write_text_atomic(path, text):
    """Write text to path atomically (tmp + replace) in executor to avoid blocking the event loop."""
    loop = asyncio.get_event_loop()
    def _do_write():
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(text, encoding="utf-8")
        tmp_path.replace(path)
    await loop.run_in_executor(None, _do_write)


async def load_json_async(path, default=None):
    if default is None:
        default = []
    async with _file_lock:
        if not path.exists():
            return default
        try:
            text = await _read_text(path)
            return json.loads(text)
        except (FileNotFoundError, json.JSONDecodeError):
            return default
        except Exception as e:
            log.exception("load_json_async(%s) failed: %s", path, e)
            return default


async def save_json_async(path, data):
    text = json.dumps(data, ensure_ascii=False, indent=2, default=str)
    async with _file_lock:
        try:
            await _write_text_atomic(path, text)
        except Exception as e:
            log.exception("save_json_async(%s) failed: %s", path, e)
            raise


async def get_settings_async():
    data = await load_json_async(SETTINGS_FILE, DEFAULT_SETTINGS.copy())
    merged = DEFAULT_SETTINGS.copy()
    if isinstance(data, dict):
        merged.update(data)
    if os.environ.get("BOT_TOKEN"):
        merged["bot_token"] = os.environ["BOT_TOKEN"]
    if os.environ.get("SMSCODE_TOKEN"):
        merged["smscode_token"] = os.environ["SMSCODE_TOKEN"]
    if os.environ.get("ALLOWED_USER_ID"):
        try:
            uid = int(os.environ["ALLOWED_USER_ID"])
            if uid not in merged.get("allowed_users", []):
                merged["allowed_users"] = merged.get("allowed_users", []) + [uid]
        except ValueError:
            log.warning("Invalid ALLOWED_USER_ID in env: %r", os.environ["ALLOWED_USER_ID"])
    return merged


# --- Token helper: single source of truth for bot token ---
_bot_token_cache = None


def get_bot_token():
    """Read bot token from settings file or BOT_TOKEN env. Caches result."""
    global _bot_token_cache
    if _bot_token_cache is not None:
        return _bot_token_cache
    env_tok = os.environ.get("BOT_TOKEN", "").strip()
    file_tok = ""
    try:
        if SETTINGS_FILE.exists():
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                file_tok = (data.get("bot_token") or "").strip()
    except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
        log.debug("settings file unreadable for token: %s", e)
    _bot_token_cache = env_tok or file_tok
    return _bot_token_cache


def clear_bot_token_cache():
    global _bot_token_cache
    _bot_token_cache = None


async def save_settings_async(s):
    merged = DEFAULT_SETTINGS.copy()
    merged.update(s)
    await save_json_async(SETTINGS_FILE, merged)
    invalidate_settings_cache()
    clear_bot_token_cache()


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


# --- Settings cache for check_auth (TTL-based invalidation) ---
_settings_cache = {"data": None, "ts": 0.0}
_SETTINGS_TTL = 30.0  # seconds


async def _get_cached_settings():
    """Cached get_settings_async with TTL. Cheap spam protection."""
    now = time.time()
    if _settings_cache["data"] is not None and (now - _settings_cache["ts"]) < _SETTINGS_TTL:
        return _settings_cache["data"]
    data = await get_settings_async()
    _settings_cache["data"] = data
    _settings_cache["ts"] = now
    return data


def invalidate_settings_cache():
    _settings_cache["data"] = None
    _settings_cache["ts"] = 0.0


def check_auth(func):
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        s = await _get_cached_settings()
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
    attempts = 0
    while len(results) < count and attempts < count * 30:
        attempts += 1
        first = fake.first_name().lower()
        last = fake.last_name().lower()
        name_part = (first + last).replace(".", "").replace(" ", "")
        digits = str(random.randint(10, 999))
        
        if position == "depan":
            username = keyword + name_part + digits
        elif position == "belakang":
            username = name_part + keyword + digits
        elif position == "tengah":
            username = first + keyword + last + digits
        else:
            parts = [name_part, keyword]
            random.shuffle(parts)
            username = "".join(parts) + digits
            
        username = username.replace(" ", "").replace(".", "")
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
    else:
        return {"success": False, "error": {"message": "Need catalog_product_id or product_id"}}

    # Always forward the Brazil/Vivo constraints, including direct product orders.
    if min_price is not None:
        body["min_price"] = int(min_price)
    if max_price is not None:
        body["max_price"] = int(max_price)
    if policy:
        body["policy"] = policy
    if operator_id is not None:
        body["operator_id"] = int(operator_id)

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
            log.exception("exporting to Google Sheets: %s", e)


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
        f"📋 *DATA AKUN (Play Store / YT Premium)*\n\n"
        f"📞 Nomor ({country}):{reuse_tag}\n`{phone}`\n\n"
        f"👤 Nama Depan:\n`{first_name}`\n\n"
        f"👤 Nama Belakang:\n`{last_name}`\n\n"
        f"📧 Username:\n`{username}`\n\n"
        f"🔑 Password:\n`{password}`{debug_note}\n\n"
        f"➡️ _Tekan / tap pada kotak teks untuk menyalin otomatis._\n"
        f"➡️ Input data di atas ke Gmail, lalu tap *📲 Minta OTP*"
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
    await query.edit_message_text("💬 Masukkan *Keyword* (contoh: ytprem):", parse_mode="Markdown")
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
    keyword = setup.get("keyword", "ytprem")
    password = setup.get("password", "fixedpassword")
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
        f"⚡ Play Store / YT Premium Mode Aktif\n\n"
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
        [InlineKeyboardButton("📥 Export", callback_data="menu_export"), InlineKeyboardButton("🔥 Warm-Up", callback_data="sess_warmup")],
        [InlineKeyboardButton("🌐 IP Hunter", callback_data="menu_ip_hunter"), InlineKeyboardButton("🃏 CC Extrap", callback_data="menu_cc_extrap")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="menu_settings"), InlineKeyboardButton("🧹 Clear", callback_data="menu_clear")],
    ])


def back_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")]])


SMSCODE_COUNTRIES = [
    {"id": 74, "name": "Brazil", "flag": "🇧🇷", "price_min": 900, "price_max": 1200, "operator_id": 347, "operator_name": "Vivo S.A."},
]
SMSCODE_VIVO_OPERATOR_ID = 347
SMSCODE_PRICE_MIN = 900
SMSCODE_PRICE_MAX = 1200


def country_selection_keyboard():
    rows = []
    for c in SMSCODE_COUNTRIES:
        rows.append([InlineKeyboardButton(f"{c['flag']} {c['name']}", callback_data=f"country_select:{c['id']}")])
    rows.append([InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")])
    return InlineKeyboardMarkup(rows)


async def ensure_number_for_account_async(acc):
    active = await get_active_number_async()
    # Never reuse legacy/non-Brazil numbers after the region/provider switch.
    if active and active.get("country", "Brazil") == "Brazil":
        tracked = await track_number_usage_async(active["phone"], active["order_id"], acc["email"])
        await update_account_async(acc["id"], {"phone": active["phone"], "order_id": active["order_id"], "status": "sms_pending", "country": active.get("country", "Brazil")})
        max_c = await get_max_codes_async()
        log.info("[REUSE_NUMBER] %s order=%s uses=%s/%s for %s", active['phone'], active['order_id'], tracked['codes_used'], max_c, acc['email'])
        return {"reused": True, "phone": active["phone"], "order_id": active["order_id"], "uses": tracked["codes_used"], "country": active.get("country", "Brazil")}

    session = await get_session_async()
    selected_country_id = session.get("selected_country_id") if session else None
    country = next((c for c in SMSCODE_COUNTRIES if c["id"] == selected_country_id), SMSCODE_COUNTRIES[0])
    country_id = country["id"]

    platform_id = 5
    headers = await sms_headers_async()
    
    async with httpx.AsyncClient(timeout=20.0) as client:
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
            
            candidates = [
                p for p in products
                if p.get("available", 0) > 0
                and p.get("id")
                and SMSCODE_PRICE_MIN <= float(p.get("price", 0) or 0) <= SMSCODE_PRICE_MAX
                and int(p.get("operator_id", -1) or -1) == SMSCODE_VIVO_OPERATOR_ID
            ]
            candidates.sort(key=lambda x: float(x.get("price", 0) or 0))
        except Exception as e:
            raise RuntimeError(f"Gagal fetch catalog: {e}")

    if not candidates:
        raise RuntimeError(f"Tidak ada stok nomor tersedia untuk Brazil.")

    for p in candidates[:5]:
        pid = p["id"]
        result = await sms_create_order_async(product_id=pid, min_price=SMSCODE_PRICE_MIN, max_price=SMSCODE_PRICE_MAX, operator_id=SMSCODE_VIVO_OPERATOR_ID)
        if result.get("success"):
            orders = result.get("data", {}).get("orders", [])
            if orders:
                order = orders[0]
                phone = order.get("phone_number", "")
                order_id = order["id"]
                await update_account_async(acc["id"], {"phone": phone, "order_id": order_id, "status": "sms_pending", "country": country["name"]})
                tracked = await track_number_usage_async(phone, order_id, acc["email"], country=country["name"])
                return {"reused": False, "phone": phone, "order_id": order_id, "uses": tracked["codes_used"], "country": country["name"], "flag": country["flag"]}

    raise RuntimeError(f"Gagal order nomor Brazil. Stok sedang habis.")


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
    
    # Bungkus akuisisi nomor dengan Timeout 120 Detik agar tombol tetap responsif & tidak hang
    try:
        number_info = await asyncio.wait_for(ensure_number_for_account_async(acc), timeout=120.0)
    except asyncio.TimeoutError:
        await update_account_async(acc["id"], {"status": "failed", "notes": "number_error: Timeout 120s exceeded"})
        session["failed"] = session.get("failed", 0) + 1
        await save_session_async(session)
        
        fallback_kbd = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Coba Lagi", callback_data="menu_preset_start")],
            [InlineKeyboardButton("🛑 Stop Sesi", callback_data="sess_stop"), InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")]
        ])
        await chat.send_message("⏱️ *Timeout Warning:* Alokasi nomor memakan waktu lebih dari 120 detik. Silakan coba ulang.", parse_mode="Markdown", reply_markup=fallback_kbd)
        return
    except Exception as e:
        await update_account_async(acc["id"], {"status": "failed", "notes": f"number_error: {e}"})
        session["failed"] = session.get("failed", 0) + 1
        await save_session_async(session)
        
        fallback_kbd = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Coba Lagi", callback_data="menu_preset_start")],
            [InlineKeyboardButton("🛑 Stop Sesi", callback_data="sess_stop"), InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")]
        ])
        await chat.send_message(f"❌ Gagal ambil nomor: {e}", reply_markup=fallback_kbd)
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
            log.exception("[FATAL_SEND_FAIL] failed to send text: %s", e2)


# ═══════════════════════════════════════════════════════════════
# IP HUNTER ENGINE V5 — HTTPX FIXED & UNLIMITED CUSTOM SCAN
# ═══════════════════════════════════════════════════════════════

def _port_for_scheme(settings: dict, scheme: str) -> int:
    s = scheme.lower()
    if s in ("socks5", "socks5h"):
        return 1080
    return 8989


def _build_proxy_url(settings: dict, new_session: bool = True, candidate: dict = None) -> Any:
    raw_user = settings.get("proxy_user", "")
    pw = settings.get("proxy_pass", "")
    host = settings.get("proxy_host", "proxy.flameproxies.com")
    
    if not raw_user or not pw:
        return (None, None) if new_session else None

    proto = (candidate.get("scheme") if candidate else None) or settings.get("proxy_protocol", "socks5")
    target = (candidate.get("target") if candidate else None) or settings.get("proxy_param_target", "user")

    port = _port_for_scheme(settings, proto)
    country = settings.get("ip_hunter_country", "br").lower()

    params = f"-country-{country}-type-residential-zone-residential"

    if settings.get("proxy_city_targeting", False):
        state = settings.get("proxy_state")
        city = settings.get("proxy_city")
        if state:
            params += f"-state-{state.lower()}"
        if city:
            params += f"-city-{city.lower().replace(' ', '_')}"

    sess_id = ""
    if new_session:
        sess_id = uuid.uuid4().hex[:12]
        sess_ttl = settings.get("proxy_session_ttl", 60)
        params += f"-session-{sess_id}-ttl-{sess_ttl}"

    if target == "user":
        final_user = f"{raw_user}{params}"
        final_pass = pw
    else:
        final_user = raw_user
        final_pass = f"{pw}{params}"

    scheme_prefix = "socks5" if proto in ("socks5", "socks5h") else "http"
    url = f"{scheme_prefix}://{final_user}:{final_pass}@{host}:{port}"

    if new_session:
        return url, sess_id
    return url


def _proxy_variant_candidates(settings: dict) -> list:
    configured_proto = settings.get("proxy_protocol", "socks5")
    configured_target = settings.get("proxy_param_target", "user")
    
    candidates = [
        {"scheme": configured_proto, "target": configured_target},
        {"scheme": "socks5h", "target": "user"},
        {"scheme": "socks5h", "target": "pass"},
        {"scheme": "http", "target": "user"},
        {"scheme": "http", "target": "pass"},
    ]
    
    seen = set()
    unique_candidates = []
    for c in candidates:
        key = (c["scheme"], c["target"])
        if key not in seen:
            seen.add(key)
            unique_candidates.append(c)
    return unique_candidates


async def _ip_check_one_strict_async(proxy_url: str, timeout: int = 15, settings: dict = None) -> dict:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.0.0 Safari/537.36"}
    check_url = "http://ip-api.com/json/?fields=status,message,countryCode,regionName,city,isp,org,as,proxy,hosting,query"
    
    async with httpx.AsyncClient(proxy=proxy_url, timeout=float(timeout)) as client:
        try:
            r = await client.get(check_url, headers=headers)
            if r.status_code == 200:
                data = r.json()
                if data.get("status") == "success":
                    ip = data.get("query")
                    is_proxy = data.get("proxy", False)
                    is_hosting = data.get("hosting", False)
                    isp = data.get("isp", "")
                    org = data.get("org", "")
                    country_code = data.get("countryCode", "")
                    
                    if country_code != "BR":
                        return {"error": f"Non-Brazil IP detected ({country_code})"}

                    if is_proxy or is_hosting:
                        return {"error": "IP terdeteksi Privacy: TRUE (Hosting/Proxy/Datacenter)"}
                    
                    full_isp_info = (isp + " " + org).lower()
                    
                    # Blokir Datacenter secara mutlak
                    datacenter_keywords = ["amazon", "google", "digitalocean", "linode", "hetzner", "ovh", "hostinger", "oracle", "microsoft", "vultr", "choopa", "cloudflare"]
                    if any(dc in full_isp_info for dc in datacenter_keywords):
                        return {"error": "IP terdeteksi Datacenter ASN"}

                    # STRICT VIVO S.A. / TELEFONICA FILTER ONLY
                    strict_vivo_keywords = ["vivo", "telefonica", "telemar", "braspd", "as26599"]
                    is_strict_vivo = any(net in full_isp_info for net in strict_vivo_keywords)

                    if not is_strict_vivo:
                        return {"error": f"ISP bukan Vivo S.A. Terdeteksi: {isp or org}"}

                    proxycheck_key = settings.get("proxycheck_api_key") if settings else None
                    if proxycheck_key and ip:
                        try:
                            pc_res = await client.get(f"https://proxycheck.io/v2/{ip}?key={proxycheck_key}&vpn=1&risk=1")
                            if pc_res.status_code == 200:
                                pc_data = pc_res.json().get(ip, {})
                                if pc_data.get("proxy") == "yes":
                                    return {"error": "ProxyCheck.io mendeteksi IP ini sebagai Proxy/VPN"}
                        except Exception:
                            pass

                    score = 99  # Nilai maksimum untuk Strict Match Vivo

                    return {
                        "ip": ip,
                        "city": data.get("city", "Unknown"),
                        "state": data.get("regionName", "Unknown"),
                        "country": country_code,
                        "isp": isp or org,
                        "privacy": "FALSE (Strict Vivo Residential)",
                        "score": score
                    }
        except Exception as e:
            return {"error": f"Koneksi timeout/gagal: {e}"}

    return {"error": "Semua endpoint pengecek IP gagal merespon."}


async def _ip_check_smart_async(settings: dict, timeout: int = 15) -> dict:
    candidates = _proxy_variant_candidates(settings)
    last_res = None
    
    for cand in candidates:
        res_tuple = _build_proxy_url(settings, new_session=True, candidate=cand)
        if not res_tuple or not res_tuple[0]:
            continue
        proxy_url, sess_id = res_tuple
            
        res = await _ip_check_one_strict_async(proxy_url, timeout=timeout, settings=settings)
        if res and "ip" in res and not res.get("error"):
            settings["proxy_protocol"] = cand["scheme"]
            settings["proxy_param_target"] = cand["target"]
            await save_settings_async(settings)
            res["sessid"] = sess_id
            return res
        last_res = res
        
    return last_res or {"error": "Semua varian proxy gagal lolos verifikasi Privacy: FALSE."}


async def _ip_scan_async(settings: dict, target: int = 3, max_attempts: int = 150, min_score: int = 70, timeout: int = 12):
    probe_res = await _ip_check_smart_async(settings, timeout=timeout)
    
    clean_ips = []
    all_results = []
    lines = []
    seen = set()

    if probe_res and "ip" in probe_res and not probe_res.get("error"):
        clean_ips.append(probe_res)
        all_results.append(probe_res)
        seen.add(probe_res["ip"])
        lines.append(f"🏆 Clean IP #1: `{probe_res['ip']}` ({probe_res.get('city')}) - {probe_res.get('isp')}")

    if len(clean_ips) >= target:
        return clean_ips, all_results, lines

    actual_max_attempts = max(max_attempts, target * 20)

    async def worker():
        try:
            await asyncio.sleep(random.uniform(0.1, 1.5))
            res_tuple = _build_proxy_url(settings, new_session=True)
            if not res_tuple or not res_tuple[0]:
                return None
            p_url, sess_id = res_tuple
            res = await _ip_check_one_strict_async(p_url, timeout=timeout, settings=settings)
            if res and "ip" in res and not res.get("error"):
                res["sessid"] = sess_id
                return res
            return None
        except Exception:
            return None

    tasks = [asyncio.create_task(worker()) for _ in range(actual_max_attempts)]
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
        lines.append(f"🏆 Clean IP #{len(clean_ips)}: `{ip}` ({res.get('city')}) - {res.get('isp')}")

    return clean_ips, all_results, lines


def _format_ip_card(ip_data: dict, index: int = 1, settings: dict = None) -> str:
    score = ip_data.get("score", 95)
    tier = "EXCELLENT ⭐" if score >= 85 else "GOOD ✅"
    provider_label = "🔥 FlameProxies Residential"
    
    proxy_line = ""
    if settings:
        raw_user = settings.get("proxy_user", "")
        pw = settings.get("proxy_pass", "")
        host = settings.get("proxy_host", "proxy.flameproxies.com")
        port = _port_for_scheme(settings, settings.get("proxy_protocol", "socks5"))
        
        if raw_user and pw:
            sess_id = ip_data.get("sessid") or uuid.uuid4().hex[:12]
            sess_ttl = settings.get("proxy_session_ttl", 60)
            country = settings.get("ip_hunter_country", "br")
            
            target = settings.get("proxy_param_target", "user")
            params = f"-country-{country}-type-residential-session-{sess_id}-ttl-{sess_ttl}"
            
            if target == "user":
                u_str = f"{raw_user}{params}"
                p_str = pw
            else:
                u_str = raw_user
                p_str = f"{pw}{params}"
                
            proxy_str = f"{u_str}:{p_str}@{host}:{port}"
            proxy_line = f"`{proxy_str}`"

    return (
        f"🏆 *CLEAN IP #{index}* {provider_label}\n"
        f"📍 `{ip_data['ip']}` │ {ip_data.get('city', 'Unknown')}, {ip_data.get('state', ip_data.get('region', 'Unknown'))}\n"
        f"🏢 ISP: {ip_data.get('isp', 'Unknown')}\n"
        f"📊 Score: {score}/100 ({tier})\n"
        f"🛡️ Privacy: {ip_data.get('privacy', 'FALSE (Clean)')}\n"
        f"🔎 Type: Dedicated Residential (FlameProxies)\n\n"
        f"📋 *GoLogin/Chrome Proxy:*\n"
        f"{proxy_line}"
    )


# ═══════════════════════════════════════════════════════════════
# COMMAND & CALLBACK HANDLERS
# ═══════════════════════════════════════════════════════════════

@check_auth
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Play Store & YouTube Premium Factory Bot 👾",
        parse_mode="Markdown",
        reply_markup=home_menu_keyboard(),
    )


@check_auth
async def cmd_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    if len(args) < 3:
        await update.message.reply_text(
            "❌ Format: `/session keyword jumlah password posisi`\n\nContoh: `/session ytprem 20 fixedpassword belakang`",
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
    pu = s.get("proxy_user", "")
    pu_disp = pu[:12] + "..." if len(pu) > 15 else (pu or "(belum diset)")
    ph = s.get("proxy_host", "proxy.flameproxies.com")
    pp = _port_for_scheme(s, s.get("proxy_protocol", "socks5"))
    pprot = s.get("proxy_protocol", "socks5").upper()
    await update.message.reply_text(
        f"⚙️ *Settings*\n\n"
        f"🔑 SMS token: `{tok_disp}`\n"
        f"🌍 Country ID: `{s.get('smscode_country_id', 74)}` (Brazil)\n"
        f"📦 Product ID: `{s.get('smscode_product_id')}`\n"
        f"📊 Google Sheets: `{sheet_disp}`\n\n"
        f"🌐 *Proxy Config (FlameProxies):*\n"
        f"👤 User: `{pu_disp}`\n"
        f"🖥 Host: `{ph}:{pp}`\n"
        f"🔌 Protocol: `{pprot}`\n",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔧 Ubah Proxy", callback_data="proxy_config_menu")],
            [InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")],
        ]),
    )


@check_auth
async def cmd_setpreset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    if len(args) < 4:
        await update.message.reply_text("❌ Format: `/setpreset keyword password jumlah posisi`\nContoh: `/setpreset ytprem pass123 5 belakang`", parse_mode="Markdown", reply_markup=back_kb())
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
    except Exception as e:
        log.debug("could not delete user message (likely missing permission): %s", e)


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
    except Exception as e:
        log.debug("could not delete user message (likely missing permission): %s", e)
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


@check_auth
async def cmd_ccgen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_msg = await update.message.reply_text(
        f"⏳ *CC EXTRAP (Play Store / YT Premium)*\n\n"
        f"🔍 BIN: `{CC_BINS[0]}`\n"
        f"🔄 Generate 100 CC & checking live...\n"
        f"_Proses bisa memakan waktu 1-3 menit_",
        parse_mode="Markdown",
    )
    loop = asyncio.get_running_loop()
    first_live, all_live, checked, total = await loop.run_in_executor(None, batch_check_cc, CC_BINS[0], 100)
    if first_live:
        card = first_live["card"]
        res = first_live["result"]
        number = card.get("number", "")
        expiry = card.get("expiry", "")
        cvv = card.get("cvv", "")
        addr = generate_fake_address()
        await status_msg.edit_text(
            f"🃏 *CC EXTRAP — LIVE!* ✅\n\n"
            f"Checked: {checked}/{total}\n\n"
            f"💳 *Card:*\n`{number}|{expiry}|{cvv}`\n\n"
            f"📅 *Expiry:* `{expiry}`\n"
            f"🔐 *CVV:* `{cvv}`\n"
            f"📊 *Score:* `{res.get('score', '-')}/100`\n"
            f"✅ *Status:* `{res.get('reason', '-')}`\n\n"
            f"📍 *Alamat (Brasil):*\n"
            f"👤 `{addr['name']}`\n"
            f"🏠 `{addr['street']}`\n"
            f"🏙 `{addr['district']}, {addr['city']}`\n"
            f"🗺 `{addr['province']}`\n"
            f"📮 `{addr['zip']}`\n"
            f"🌍 `{addr['country']}`\n"
            f"📞 `{addr['phone']}`\n\n"
            f"_Tap kode untuk salin_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Generate Ulang", callback_data="menu_cc_extrap")],
                [InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")]
            ]),
        )
    else:
        await status_msg.edit_text(
            f"🃏 *CC EXTRAP*\n\n"
            f"❌ Checked {checked}/{total} CC — semua DEAD.\n"
            f"BIN: `{CC_BINS[0]}`\n\n"
            f"Coba generate ulang.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Coba Lagi", callback_data="menu_cc_extrap")],
                [InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")]
            ]),
        )


@check_auth
async def cmd_cccheck(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    if not args:
        await update.message.reply_text(
            "❌ Format: `/cccheck BIN`\n\nContoh: `/cccheck 559888`",
            parse_mode="Markdown",
            reply_markup=back_kb()
        )
        return
    bin_str = args[0].strip().split("|")[0][:12]
    status_msg = await update.message.reply_text("⏳ Mengecek BIN di binlist.io...")
    info = await vccgen_lookup_bin(bin_str)
    if info and info.get("success"):
        brand = md_escape(info.get("scheme", ""))
        ctype = md_escape(info.get("type", ""))
        bank = md_escape(info.get("bank", ""))
        country = md_escape(info.get("country", ""))
        prepaid_tag = " _(PREPAID)_" if info.get("prepaid") else ""
        await status_msg.edit_text(
            f"🃏 *BIN Info*\n\n"
            f"🔢 BIN: `{bin_str[:6]}`\n"
            f"💳 Brand: *{brand}*\n"
            f"📋 Type: {ctype}{prepaid_tag}\n"
            f"🏦 Bank: {bank}\n"
            f"🌍 Country: {country}\n\n"
            f"✅ BIN valid — ada di database.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")]]),
        )
    else:
        await status_msg.edit_text(
            f"🃏 `{bin_str}`\n❌ BIN tidak ditemukan di database.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")]]),
        )


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
        except Exception as e:
            log.warning("sms_resend failed for order %s: %s", order_id, e)

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
                except Exception as e:
                    log.debug("edit poll progress: %s", e)
            else:
                try:
                    await status_msg.edit_text(f"⚠️ Retry... ({attempt*5}s)\nOrder: `{order_id}`", parse_mode="Markdown")
                except Exception as e:
                    log.debug("edit retry status: %s", e)
        except Exception as e:
            log.warning("polling attempt %d network error: %s", attempt, e)
            try:
                await status_msg.edit_text(f"⚠️ Network error, mencoba ulang... ({attempt*5}s)\nOrder: `{order_id}`", parse_mode="Markdown")
            except Exception as e2:
                log.debug("edit network-error status: %s", e2)
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
        except Exception as e:
            log.warning("sms_cancel_order failed for %s: %s", order_id, e)
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
        except Exception as e:
            log.warning("sms_cancel_order (failed status) for %s: %s", order_id, e)
        await mark_number_exhausted_async(order_id)

    if status == "created" and order_id:
        uses = session.get("current_number_uses", 0)
        max_codes = await get_max_codes_async()
        if uses >= max_codes:
            try:
                await sms_finish_order_async(order_id)
            except Exception as e:
                log.warning("sms_finish_order for %s: %s", order_id, e)
            await mark_number_exhausted_async(order_id)

    polling_msg_id = session.get("last_polling_msg_id")
    if polling_msg_id:
        try:
            await query.message.chat.delete_message(polling_msg_id)
        except Exception as e:
            log.debug("delete polling msg %s: %s", polling_msg_id, e)
        session["last_polling_msg_id"] = None

    session["current_account_id"] = None
    session["current_order_id"] = None
    session["waiting_otp"] = False
    await save_session_async(session)
    label = "berhasil" if status == "created" else ("dilewati" if skipped else "gagal")
    try:
        await query.edit_message_text(f"✅ Akun `{acc_id}` {label}. Lanjut akun berikutnya...", parse_mode="Markdown")
    except Exception as e:
        log.debug("edit success message: %s", e)
        try:
            await query.message.chat.send_message(f"✅ Akun `{acc_id}` {label}. Lanjut akun berikutnya...", parse_mode="Markdown")
        except Exception as e2:
            log.error("send success message fallback: %s", e2)
    await send_next_session_card(query.message.chat, context.bot)


# --- Callback sub-handlers (extracted from callback_handler) ---

async def _cb_menu_home(query, context, data):
    await query.edit_message_text("Play Store & YouTube Premium Factory Bot 👾", parse_mode="Markdown", reply_markup=home_menu_keyboard())


async def _cb_menu_status(query, context, data):
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


async def _cb_menu_balance(query, context, data):
    try:
        res = await sms_balance_async()
        if res.get("success"):
            bal = res.get("data", {}).get("balance", "?")
            bal_rp = f"Rp {int(bal):,}".replace(",", ".")
            await query.edit_message_text(f"💰 Saldo SMSCode: *{bal_rp}*", parse_mode="Markdown", reply_markup=home_menu_keyboard())
        else:
            await query.edit_message_text(f"❌ {res.get('error', {}).get('message', 'Unknown error')}", reply_markup=home_menu_keyboard())
    except Exception as e:
        log.exception("menu_balance error: %s", e)
        await query.edit_message_text(f"❌ Error: {e}", reply_markup=home_menu_keyboard())


async def _cb_menu_export(query, context, data):
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


async def _cb_menu_clear(query, context, data):
    await save_accounts_async([])
    await save_numbers_async([])
    await save_session_async({})
    await query.edit_message_text("✅ Accounts, numbers, dan session dibersihkan.", reply_markup=home_menu_keyboard())


# --- Callback registries (single source of truth for dispatch) ---
_CALLBACK_REGISTRY = {
    CB_MENU_HOME: _cb_menu_home,
    CB_MENU_STATUS: _cb_menu_status,
    CB_MENU_BALANCE: _cb_menu_balance,
    CB_MENU_EXPORT: _cb_menu_export,
    CB_MENU_CLEAR: _cb_menu_clear,
}


@check_auth
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if not data.startswith("preset_edit_"):
        context.user_data.pop("preset_editing", None)

    handler = _CALLBACK_REGISTRY.get(data)
    if handler is not None:
        try:
            await handler(query, context, data)
        except BadRequest as e:
            if "Message is not modified" not in str(e):
                log.warning("callback %r BadRequest: %s", data, e)
        return

    try:
        if data == "menu_home":
            await query.edit_message_text("Play Store & YouTube Premium Factory Bot 👾", parse_mode="Markdown", reply_markup=home_menu_keyboard())
        elif data == "menu_preset_start":
            settings = await get_settings_async()
            count = settings.get("preset_count", 5)
            keyword = settings.get("preset_keyword", "ytprem")
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
            keyword = settings.get("preset_keyword", "ytprem")
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
                f"🌍 Region: Brazil (74)\n"
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
            await query.edit_message_text(f"⏳ Sedang berburu `{target_count}` Clean IP (Privacy FALSE)...", parse_mode="Markdown")
            
            clean_ips, _, _ = await _ip_scan_async(s, target_count, target_count * 20, 70, 15)

            if not clean_ips:
                await query.edit_message_text(
                    f"❌ *Gagal menemukan IP dengan Privacy: FALSE*\n\nSemua IP yang dicoba terdeteksi Hosting/Proxy. Coba scan ulang.",
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
            raw_user = s.get("proxy_user", "")
            pw = s.get("proxy_pass", "")
            
            for ip_data in clean_ips:
                sess_id = ip_data.get("sessid") or uuid.uuid4().hex[:12]
                sess_ttl = s.get("proxy_session_ttl", 60)
                country = s.get("ip_hunter_country", "br")
                target = s.get("proxy_param_target", "user")
                params = f"-country-{country}-type-residential-session-{sess_id}-ttl-{sess_ttl}"
                
                if target == "user":
                    u_str = f"{raw_user}{params}"
                    p_str = pw
                else:
                    u_str = raw_user
                    p_str = f"{pw}{params}"
                
                proxy_urls_list.append(f'    "{scheme}://{u_str}:{p_str}@{host}:{port}"')

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

        elif data == "menu_status":
            # Handled by _cb_menu_status in _CALLBACK_REGISTRY
            return
        elif data == "menu_balance":
            # Handled by _cb_menu_balance in _CALLBACK_REGISTRY
            return
        elif data == "menu_export":
            # Handled by _cb_menu_export in _CALLBACK_REGISTRY
            return
        elif data == "menu_clear":
            # Handled by _cb_menu_clear in _CALLBACK_REGISTRY
            return
        elif data == "menu_cc_extrap":
            await query.edit_message_text(
                "⏳ *CC EXTRAP*\n\n"
                f"🔍 BIN: `{CC_BINS[0]}`\n"
                "🔄 Generate 100 CC & checking live...\n"
                "_Proses bisa memakan waktu 1-3 menit_",
                parse_mode="Markdown",
            )
            loop = asyncio.get_running_loop()
            first_live, all_live, checked, total = await loop.run_in_executor(None, batch_check_cc, CC_BINS[0], 100)
            if first_live:
                card = first_live["card"]
                res = first_live["result"]
                number = card.get("number", "")
                expiry = card.get("expiry", "")
                cvv = card.get("cvv", "")
                addr = generate_fake_address()
                await query.edit_message_text(
                    f"🃏 *CC EXTRAP — LIVE!* ✅\n\n"
                    f"Checked: {checked}/{total}\n\n"
                    f"💳 *Card:*\n`{number}|{expiry}|{cvv}`\n\n"
                    f"📅 *Expiry:* `{expiry}`\n"
                    f"🔐 *CVV:* `{cvv}`\n"
                    f"📊 *Score:* `{res.get('score', '-')}/100`\n"
                    f"✅ *Status:* `{res.get('reason', '-')}`\n\n"
                    f"📍 *Alamat (Brasil):*\n"
                    f"👤 `{addr['name']}`\n"
                    f"🏠 `{addr['street']}`\n"
                    f"🏙 `{addr['district']}, {addr['city']}`\n"
                    f"🗺 `{addr['province']}`\n"
                    f"📮 `{addr['zip']}`\n"
                    f"🌍 `{addr['country']}`\n"
                    f"📞 `{addr['phone']}`\n\n"
                    f"_Tap kode untuk salin_",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 Generate Ulang", callback_data="menu_cc_extrap")],
                        [InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")]
                    ]),
                )
            else:
                await query.edit_message_text(
                    f"🃏 *CC EXTRAP*\n\n"
                    f"❌ Checked {checked}/{total} CC — semua DEAD.\n"
                    f"BIN: `{CC_BINS[0]}`\n\n"
                    f"Coba generate ulang.",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 Coba Lagi", callback_data="menu_cc_extrap")],
                        [InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")]
                    ]),
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
                f"🔥 *PANDUAN INSTANT WARM-UP (Copas ke GoLogin):*\n\n"
                f"1. `https://news.google.com`\n"
                f"👉 _(Buka & baca berita 1 menit — Tanpa Login)_\n\n"
                f"2. `https://youtube.com`\n"
                f"👉 _(Tonton video 1-2 menit & Klik Like — Wajib Login)_\n\n"
                f"3. `https://drive.google.com`\n"
                f"👉 _(Buka & Upload 1 file/foto sembarang — Wajib Login)_\n\n"
                f"4. `https://console.cloud.google.com`\n"
                f"👉 _(Cukup buka & centang setujui 'Terms of Service' — Wajib Login)_\n\n"
                f"5. `https://myaccount.google.com/security-checkup`\n"
                f"👉 _(Selesaikan cek keamanan & aktifkan 'Enhanced Safe Browsing' — Wajib Login)_\n\n"
                f"6. `https://maps.google.com`\n"
                f"👉 _(Cari restoran/kota di Brazil & klik 'Simpan' ke favorites — Wajib Login)_\n\n"
                f"7. `https://pinterest.com/login`\n"
                f"👉 _(Daftar akun baru via tombol 'Continue with Google' — Wajib Login)_\n\n"
                f"⚠️ _Lakukan langkah di atas segera setelah Gmail sukses dibuat agar Google mem-whitelist akun kamu sebagai manusia asli._",
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
async def cmd_scan_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # /scan [JUMLAH] — default 5, clamp 1..50
    try:
        target = int(context.args[0]) if context.args else 5
    except (ValueError, IndexError):
        target = 5
    target = max(1, min(target, 50))

    s = await get_settings_async()
    status_msg = await update.message.reply_text(
        f"⏳ Sedang berburu `{target}` Clean IP (Privacy FALSE)...",
        parse_mode="Markdown",
    )

    try:
        clean_ips, _, _ = await _ip_scan_async(s, target, target * 20, 70, 15)
    except Exception as e:
        await status_msg.edit_text(
            f"❌ *Scan error:* `{e}`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Scan Ulang", callback_data=f"ip_scan:{target}")],
                [InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")],
            ]),
        )
        return

    if not clean_ips:
        await status_msg.edit_text(
            "❌ *Gagal menemukan IP dengan Privacy: FALSE*\n\nSemua IP yang dicoba terdeteksi Hosting/Proxy. Coba scan ulang.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Scan Ulang", callback_data=f"ip_scan:{target}")],
                [InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")],
            ]),
        )
        return

    # Susun ringkasan singkat untuk command text output
    lines = [f"🏆 *Ditemukan {len(clean_ips)} Clean IP*\n"]
    for i, ip_data in enumerate(clean_ips, 1):
        city = ip_data.get("city", "?")
        isp = ip_data.get("isp", "?")
        ip = ip_data.get("ip", "?")
        lines.append(f"`{i}.` `{ip}` — {city} ({isp})")

    await status_msg.edit_text(
        "\n".join(lines) + "\n\n💡 _Gunakan menu IP Hunter untuk proxy detail & download rotator._",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🌐 Buka IP Hunter Menu", callback_data="menu_ip_hunter")],
            [InlineKeyboardButton("🔄 Scan Ulang", callback_data=f"ip_scan:{target}")],
            [InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")],
        ]),
    )


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
            proxy_port = settings.get("proxy_port", 8989)
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

        settings["proxy_user"] = proxy_user
        settings["proxy_pass"] = proxy_pass
        settings["proxy_host"] = proxy_host
        settings["proxy_port"] = proxy_port
        await save_settings_async(settings)

        await update.message.reply_text(
            f"✅ *FlameProxies Configuration Updated!*\n\n"
            f"👤 User: `{proxy_user}`\n"
            f"🖥 Host: `{proxy_host}:{proxy_port}`\n\n"
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
    token = get_bot_token()
    if not token:
        log.error("Bot token belum diset. Set via /settings atau env BOT_TOKEN.")
        return
    log.info("Starting Gmail Factory Bot v5 Perfected...")
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
        allow_reentry=True,
        per_message=False
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
    app.add_handler(CommandHandler("ccgen", cmd_ccgen))
    app.add_handler(CommandHandler("cccheck", cmd_cccheck))
    app.add_handler(CommandHandler("setpreset", cmd_setpreset))
    app.add_handler(CommandHandler("setsheet", cmd_setsheet))
    app.add_handler(CommandHandler("scan", cmd_scan_custom))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_preset_input))
    app.add_handler(CallbackQueryHandler(callback_handler))

    retry_count = 0
    max_retries = 10
    while True:
        try:
            log.info("Bot running. Press Ctrl+C to stop.")
            app.run_polling(drop_pending_updates=True)
            break
        except KeyboardInterrupt:
            log.info("Bot stopped by user (Ctrl+C).")
            break
        except Exception as e:
            retry_count += 1
            if retry_count > max_retries:
                log.exception("Polling failed after %d retries; giving up.", max_retries)
                raise
            delay = min(60, 5 * (2 ** (retry_count - 1)))
            log.exception("Polling error (retry %d/%d) in %ds: %s", retry_count, max_retries, delay, e)
            time.sleep(delay)

if __name__ == "__main__":
    main()
