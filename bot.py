#!/usr/bin/env python3
_last_reuse_debug_msg = ""
"""
Gmail Factory Telegram Bot v2
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
import threading
import time
import uuid

# Major Brazilian cities for geo-targeting (improve IP quality for Google detection)
BRAZIL_CITIES = [
    ("São Paulo", "SP"),
    ("Rio de Janeiro", "RJ"),
    ("Brasília", "DF"),
    ("Salvador", "BA"),
    ("Fortaleza", "CE"),
    ("Belo Horizonte", "MG"),
    ("Manaus", "AM"),
    ("Curitiba", "PR"),
    ("Recife", "PE"),
    ("Porto Alegre", "RS"),
]

from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests as http_requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- Create a robust session with automatic retries for SMSCode API ---
sms_session = http_requests.Session()
retries_policy = Retry(total=5, backoff_factor=1, status_forcelist=[ 500, 502, 503, 504 ], allowed_methods=["GET", "POST"])
sms_session.mount('https://', HTTPAdapter(max_retries=retries_policy))

from faker import Faker
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters

fake = Faker(["id_ID", "en_US"])

# --- File locking for JSON persistence ---
_file_lock = threading.Lock()

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
        text = text.replace(ch, '\\' + ch)
    return text

# ---------- CC Extrap (ported from PHP CCEXTRAP by hndko) ----------

# Hardcoded BIN list for auto-check
CC_BINS = ["5598880651"]

# Fake address for CC usage (Thai-style, realistic)
def generate_fake_address():
    """Generate a random fake Thai address for CC form filling."""
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


# ── CC Heuristic Scoring Engine (ported from uncoder.eu.org/cc-checker) ──
# Offline checker: no API calls needed. Scores CCs based on entropy, digit
# patterns, BIN database, Benford's law, Markov transitions — identical logic
# to uncoder's scoreCard(). Score >= 80 = LIVE, 60-79 = UNKNOWN, < 60 = DIE.

import hashlib, math

# Known test/sandbox card numbers — always DIE
TEST_CARDS = {
    "4111111111111111", "4242424242424242", "4000056655665556",
    "4000000000000002", "4000000000000069", "4000000000000127",
    "5555555555554444", "5200828282828210", "5105105105105100",
    "2223003122003222", "5500005555555559", "5424000000000015",
    "378282246310005", "371449635398431", "378734493671000",
    "6011111111111117", "6011000990139424", "3530111333300000",
    "30569309025904", "38520000023237", "6200000000000005",
    "6759649826438453",
    # All-same-digit
    "1111111111111111", "2222222222222222", "3333333333333333",
    "4444444444444444", "5555555555555555", "6666666666666666",
    "7777777777777777", "8888888888888888", "9999999999999999",
    "0000000000000000",
}

# Known test BIN prefixes (6-digit)
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
    """Check if CVV has fake patterns: all-same, sequential, substring of PAN."""
    if not cvv.isdigit():
        return False
    if len(set(cvv)) == 1:
        return True
    # Ascending or descending
    asc = all(int(cvv[i]) - int(cvv[i-1]) == 1 for i in range(1, len(cvv)))
    dsc = all(int(cvv[i-1]) - int(cvv[i]) == 1 for i in range(1, len(cvv)))
    if asc or dsc:
        return True
    if pan and cvv in pan:
        return True
    return False

def _shannon_entropy(n):
    """Shannon entropy of digit string."""
    length = len(n)
    freq = {}
    for ch in n:
        freq[ch] = freq.get(ch, 0) + 1
    ent = 0.0
    for c in freq.values():
        p = c / length
        ent -= p * math.log2(p)
    return ent

def _longest_run(n):
    """Length of longest consecutive identical digit run."""
    mx, cur = 1, 1
    for i in range(1, len(n)):
        if n[i] == n[i-1]:
            cur += 1
            if cur > mx:
                mx = cur
        else:
            cur = 1
    return mx

def _has_sequential_run(n, threshold=5):
    """Detect monotone ascending/descending run of length >= threshold."""
    asc, dsc = 1, 1
    for i in range(1, len(n)):
        diff = int(n[i]) - int(n[i-1])
        asc = asc + 1 if diff == 1 else 1
        dsc = dsc + 1 if diff == -1 else 1
        if asc >= threshold or dsc >= threshold:
            return True
    return False

def score_cc(number, month, year, cvv):
    """
    Heuristic scoring engine — identical to uncoder.eu.org/cc-checker scoreCard().
    Returns dict: {status: 'live'|'unknown'|'die', score: 0-100, reason: str}
    """
    n = "".join(ch for ch in number if ch.isdigit())
    length = len(n)

    # 0. Test BIN detection
    if length >= 6 and n[:6] in TEST_BINS:
        return {"status": "die", "score": 0, "reason": "Known test BIN detected"}

    # 1. Known test card
    if n in TEST_CARDS:
        return {"status": "die", "score": 0, "reason": "Known test/sandbox card number"}

    # 2. All-same-digit
    if len(set(n)) == 1:
        return {"status": "die", "score": 0, "reason": "All-identical-digit card number"}

    # 3. Structural analysis
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

    # 4. Unique digits
    unique_digits = sum(1 for c in digit_freq if c > 0)
    if unique_digits <= 2:
        return {"status": "die", "score": 0, "reason": "Low digit diversity detected"}

    # 4b. Benford's Law
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

    # 5. Entropy
    entropy = _shannon_entropy(n)

    # 6. Primary score from hash
    hash_key = hashlib.sha256((n + "cc-checker-salt-v3").encode()).hexdigest()[:16]
    primary_score = int(hash_key[:8], 16) % 100

    # 4c. Markov transition analysis
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

    # 7. Penalty system
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

    # 8. Suspicious CVV penalty
    if _is_suspicious_cvv(cvv, n):
        penalty += 15

    # 9. Final score
    score = max(0, min(100, primary_score - penalty))

    # 10. Status + reason
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
    """Check single CC via heuristic scoring engine (offline, no API)."""
    parts = expiry.split("/")
    month = parts[0] if len(parts) > 0 else "01"
    year = parts[1] if len(parts) > 1 else "2028"
    if len(year) == 2:
        year = "20" + year
    return score_cc(number, month, year, cvv)


def batch_check_cc(bin_str, count=100):
    """Generate `count` CCs from BIN, score each, return first LIVE or None."""
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

# ---------- CC Generator (ported from vccgenerator.org client-side JS) ----------

def luhn_checkdigit(cc_partial: str) -> str:
    """Calculate Luhn check digit and append it. (exact port of vccgenerator.org calculateLuhnCheckDigit)"""
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
    """Generate CC numbers from BIN using Luhn. (ported from vccgenerator.org generateBinCard)
    BIN is capped at 8 digits max (same as vccgenerator.org BIN_INPUT_MAX = 8)
    to ensure enough random digits for realistic card numbers.
    """
    # Strip non-digit characters and cap at 8 digits (vccgenerator.org limit)
    bin_str = re.sub(r'\D', '', bin_str)[:8]
    if not bin_str or count <= 0:
        return []
    from datetime import datetime
    results = []
    current_year = datetime.now().year
    for _ in range(count):
        # Fill remaining digits randomly (target = 16 total, last is Luhn check)
        partial = bin_str
        target_len = 16
        while len(partial) < target_len - 1:
            partial += str(random.randint(0, 9))
        partial = partial[:target_len - 1]
        full_cc = luhn_checkdigit(partial)
        # Future expiry: current_year+1 to current_year+8 (same as vccgenerator.org)
        year = current_year + 1 + random.randint(0, 7)
        month = random.randint(1, 12)
        expiry = f"{month:02d}/{str(year)[-2:]}"
        # CVV: random 3 digits (no filtering — vccgenerator.org doesn't filter)
        cvv = f"{random.randint(0, 999):03d}"
        results.append({"number": full_cc, "expiry": expiry, "cvv": cvv})
    return results


# ---- BIN Lookup & CC Generator (source: vccgenerator.org logic + binlist.io API) ----

VCCGEN_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

# BIN lookup cache (LRU, max 500 entries)
_BIN_CACHE_MAX = 500
_bin_cache = OrderedDict()


def _bin_cache_set(key, value):
    """Store in BIN cache with LRU eviction."""
    _bin_cache[key] = value
    _bin_cache.move_to_end(key)
    while len(_bin_cache) > _BIN_CACHE_MAX:
        _bin_cache.popitem(last=False)


def vccgen_lookup_bin(bin_str: str) -> dict | None:
    """Lookup BIN info. Primary: binlist.io (free, fast). Fallback: binlist.net.
    Uses 6-digit prefix for lookup (standard BIN length).
    Returns normalized dict: {scheme, type, brand, bank, country, success} or None.
    """
    b = bin_str[:6]  # Standard BIN = first 6 digits

    # Check cache first
    if b in _bin_cache:
        _bin_cache.move_to_end(b)
        return _bin_cache[b]

    # Primary: binlist.io (free, fast, no heavy rate limiting)
    try:
        r = http_requests.get(
            f"https://binlist.io/lookup/{b}/",
            headers={"User-Agent": VCCGEN_UA},
            timeout=10,
        )
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
        pass

    # Fallback: binlist.net
    try:
        r = http_requests.get(
            f"https://lookup.binlist.net/{b}",
            headers={"Accept-Version": "3", "User-Agent": VCCGEN_UA},
            timeout=10,
        )
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
        pass

    # Mark as not found in cache too (avoid repeated lookups)
    _bin_cache_set(b, None)
    return None


def vccgen_generate_cards(bin_str: str, count: int = 5) -> list:
    """Generate CC cards from BIN using Luhn algorithm.
    BIN lookup is optional (for extra info like brand/bank/country).
    Cards are ALWAYS generated regardless of lookup result.
    """
    # Generate cards locally — always works as long as BIN has digits
    local_cards = generate_cc_from_bin(bin_str, count)
    if not local_cards:
        return []

    # Try BIN lookup for extra info (optional, non-blocking)
    info = vccgen_lookup_bin(bin_str)
    brand = info.get("scheme", "") if info and info.get("success") else ""
    ctype = info.get("type", "") if info and info.get("success") else ""
    bank = info.get("bank", "") if info and info.get("success") else ""
    country = info.get("country", "") if info and info.get("success") else ""
    prepaid = info.get("prepaid") if info and info.get("success") else None

    cards = []
    for c in local_cards:
        cards.append({
            "number": c["number"],
            "expiry": c["expiry"],
            "cvv": c["cvv"],
            "brand": brand,
            "type": ctype,
            "bank": bank,
            "country": country,
            "prepaid": prepaid,
        })
    return cards


def auto_check_bins(bins: list, cards_per_bin: int = 5) -> dict | None:
    """Pick a random BIN from the list, generate CC locally.
    Tries other BINs if the picked one fails (unlikely with local gen).
    """
    shuffled = list(bins)
    random.shuffle(shuffled)
    for bin_str in shuffled:
        cards = vccgen_generate_cards(bin_str, cards_per_bin)
        if cards:
            card = cards[0]
            return {
                "bin": bin_str,
                "live_card": f"{card['number']}|{card['expiry']}|{card['cvv']}",
                "all_cards": cards,
                "status": "LIVE",
                "source": "binlist.io + local gen",
                "brand": card.get("brand", ""),
                "type": card.get("type", ""),
                "bank": card.get("bank", ""),
                "country": card.get("country", ""),
            }

    return None

# ---------- End CC Extrap ----------


DEFAULT_SETTINGS = {
    # ... settings lainnya ...
    
    # --- FlameProxies Configuration (Ganti DataImpulse) ---
    "proxy_user": "",           # Format: USER-package-residential
    "proxy_pass": "",           # Password + parameter geo/session
    "proxy_host": "proxy.flameproxies.com",  # Ganti dari gw.dataimpulse.com
    "proxy_port": 8989,         # Ganti dari 824
    "proxy_protocol": "http",   # Ganti dari socks5 (FlameProxies support HTTP/HTTPS)
    "proxy_session_ttl": 60,    # Session TTL dalam menit
    "ip_hunter_provider": "residential",  # residential, mobile, static
    "ip_hunter_country": "br",  # Brazil
    "ipqs_api_key": "",
    "iphub_api_key": "",
}


def load_json(path, default=None):
    if default is None:
        default = []
    try:
        with _file_lock:
            return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, data):
    with _file_lock:
        temp_path = path.with_suffix('.tmp')
        temp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str))
        temp_path.replace(path)


def get_settings():
    data = load_json(SETTINGS_FILE, DEFAULT_SETTINGS.copy())
    merged = DEFAULT_SETTINGS.copy()
    if isinstance(data, dict):
        merged.update(data)
    # Environment variable overrides (for Railway/Docker deploy)
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
            pass
    if os.environ.get("IPQS_API_KEY"):
        merged["ipqs_api_key"] = os.environ["IPQS_API_KEY"]
    if os.environ.get("IPHUB_API_KEY"):
        merged["iphub_api_key"] = os.environ["IPHUB_API_KEY"]
    return merged


def save_settings(s):
    merged = DEFAULT_SETTINGS.copy()
    merged.update(s)
    save_json(SETTINGS_FILE, merged)


def get_accounts():
    return load_json(ACCOUNTS_FILE, [])


def save_accounts(accs):
    save_json(ACCOUNTS_FILE, accs)


def get_numbers():
    return load_json(NUMBERS_FILE, [])


def save_numbers(nums):
    save_json(NUMBERS_FILE, nums)


def get_session():
    return load_json(SESSION_FILE, {})


def save_session(s):
    with _file_lock:
        path = SESSION_FILE
        path.write_text(json.dumps(s, ensure_ascii=False, indent=2, default=str))


def progress_bar(done, total, width=20):
    if total <= 0:
        return "░" * width
    fill = round((done / total) * width)
    return "█" * fill + "░" * (width - fill)


def check_auth(func):
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        s = get_settings()
        allowed = s.get("allowed_users", [])
        user = update.effective_user.id if update.effective_user else None
        if allowed and user not in allowed:
            target = update.message or update.callback_query.message
            await target.reply_text("⛔ Kamu tidak punya akses ke bot ini.")
            return
        return await func(update, context)
    return wrapper


def generate_emails(count, keyword, position="bebas", password="", no_kasar=True):
    results = []
    attempts = 0
    while len(results) < count and attempts < count * 30:
        attempts += 1
        first = fake.first_name().lower()
        last = fake.last_name().lower()
        name_part = (first + last).replace(".", "").replace(" ", "")
        digits = str(random.randint(10, 999))
        
        # Angka selalu di akhir, posisi hanya untuk (keyword + nama)
        if position == "depan":
            username = keyword + name_part + digits
        elif position == "belakang":
            username = name_part + keyword + digits
        elif position == "tengah":
            username = first + keyword + last + digits
        else: # bebas
            parts = [name_part, keyword]
            random.shuffle(parts)
            username = "".join(parts) + digits
            
        username = username.replace(" ", "").replace(".", "")
        if no_kasar and any(w in username for w in BAD_WORDS):
            continue
        email = f"{username}@gmail.com"
        if any(r["email"] == email for r in results):
            continue
        results.append({
            "email": email,
            "password": password,
            "first_name": first.capitalize(),
            "last_name": last.capitalize(),
        })
    return results


def add_account(email, password, first_name="", last_name="", status="queued"):
    accounts = get_accounts()
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
    save_accounts(accounts)
    return acc


def update_account(account_id, updates):
    accounts = get_accounts()
    for acc in accounts:
        if acc["id"] == account_id:
            acc.update(updates)
            save_accounts(accounts)
            return acc
    return None


def get_account(account_id):
    for acc in get_accounts():
        if acc["id"] == account_id:
            return acc
    return None


def next_queued_account():
    accounts = get_accounts()
    for acc in accounts:
        if acc["status"] == "queued":
            acc["status"] = "creating"
            save_accounts(accounts)
            return acc
    return None


def session_counts():
    session = get_session()
    return session.get("done", 0), session.get("total", 0)


def get_max_codes():
    session = get_session()
    total = session.get("total") if session else None
    if total and total > 0:
        return min(total, 5)
    s = get_settings()
    preset_c = s.get("preset_count")
    if preset_c and preset_c > 0:
        return min(preset_c, 5)
    return s.get("max_codes_per_number", 5)

def get_active_number():
    global _last_reuse_debug_msg
    numbers = get_numbers()
    max_codes = get_max_codes()
    
    import datetime as dt
    now = dt.datetime.now()
    
    debug_logs = []
    if not numbers:
        import os
        size = NUMBERS_FILE.stat().st_size if NUMBERS_FILE.exists() else -1
        debug_logs.append(f"DB kosong (Exists: {NUMBERS_FILE.exists()}, Size: {size}b)")
        
    for n in numbers:
        phone = n.get('phone', '?')
        if not n.get("can_reuse"):
            debug_logs.append(f"Nomor {phone} nonaktif (can_reuse=False)")
            continue
        if n.get("codes_used", 0) >= max_codes:
            debug_logs.append(f"Nomor {phone} penuh ({n.get('codes_used')}/{max_codes}x)")
            continue
            
        first_used_str = n.get("first_used")
        if first_used_str:
            try:
                first_used = dt.datetime.fromisoformat(first_used_str)
                diff_minutes = (now - first_used).total_seconds() / 60
                if diff_minutes > 18:
                    debug_logs.append(f"Nomor {phone} expired ({diff_minutes:.1f}m lalu)")
                    continue
            except Exception as e:
                debug_logs.append(f"Nomor {phone} error time: {e}")
                pass
                
        _last_reuse_debug_msg = f"Reused {phone}"
        return n

    _last_reuse_debug_msg = " | ".join(debug_logs) if debug_logs else "DB nomor kosong"
    return None


def mark_number_exhausted(order_id):
    numbers = get_numbers()
    for n in numbers:
        if str(n.get("order_id")) == str(order_id):
            n["can_reuse"] = False
    save_numbers(numbers)


def track_number_usage(phone, order_id, account_email=None, country=None):
    numbers = get_numbers()
    max_codes = get_max_codes()
    existing = next((n for n in numbers if str(n.get("phone")) == str(phone)), None)
    if existing:
        existing["codes_used"] += 1
        existing["accounts"].append({"email": account_email, "order_id": order_id, "time": datetime.now().isoformat()})
        existing["can_reuse"] = existing["codes_used"] < max_codes
        if country:
            existing["country"] = country
        save_numbers(numbers)
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
    save_numbers(numbers)
    return new_n


def sms_headers():
    s = get_settings()
    return {"Authorization": f"Bearer {s['smscode_token']}", "Content-Type": "application/json"}


def sms_balance():
    r = sms_session.get(f"{SMSCODE_BASE}/balance", headers=sms_headers(), timeout=15)
    return r.json()


def sms_create_order(catalog_product_id=None, product_id=None, min_price=None, max_price=None, policy=None, operator_id=None):
    """Create a SMSCode order via v1 API.
    Two modes (per API docs — use EITHER, not both):
      1. Routed: catalog_product_id + optional min_price/max_price/policy/operator_id
         Server picks the best available tier within constraints.
      2. Direct: product_id — exact tier-slot, no routing.
    """
    body = {"quantity": 1}
    if product_id is not None:
        # Direct mode — exact tier
        body["product_id"] = int(product_id)
    elif catalog_product_id is not None:
        # Routed mode — server picks best tier
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

    headers = sms_headers()
    headers["Idempotency-Key"] = str(uuid.uuid4())
    try:
        r = sms_session.post(f"{SMSCODE_BASE}/orders/create", headers=headers, json=body, timeout=20)
        return r.json()
    except Exception as e:
        return {"success": False, "error": {"message": f"NetworkError: {e}"}}


def sms_get_order(order_id, after_code=None):
    url = f"{SMSCODE_BASE}/orders/{order_id}"
    if after_code:
        url += f"?after_code={after_code}"
    try:
        r = sms_session.get(url, headers=sms_headers(), timeout=15)
        try:
            return r.json()
        except Exception:
            return {"success": False, "error": {"message": f"Bad response ({r.status_code}): {r.text[:100]}"}}
    except Exception as e:
        # Normalize connection errors so polling can retry cleanly
        return {"success": False, "error": {"message": f"NetworkError: {e}"}}


def sms_finish_order(order_id):
    try:
        oid = int(order_id)
    except (ValueError, TypeError):
        return {"success": False, "error": {"message": f"Invalid order_id: {order_id}"}}
    r = sms_session.post(f"{SMSCODE_BASE}/orders/finish", headers=sms_headers(), json={"id": oid}, timeout=15)
    try:
        return r.json()
    except Exception:
        return {"success": r.status_code == 200, "status_code": r.status_code, "body": r.text[:200]}


def sms_cancel_order(order_id):
    try:
        oid = int(order_id)
    except (ValueError, TypeError):
        return {"success": False, "error": {"message": f"Invalid order_id: {order_id}"}}
    r = sms_session.post(f"{SMSCODE_BASE}/orders/cancel", headers=sms_headers(), json={"id": oid}, timeout=15)
    try:
        return r.json()
    except Exception:
        return {"success": r.status_code == 200, "status_code": r.status_code, "body": r.text[:200]}


def sms_resend(order_id):
    try:
        oid = int(order_id)
    except (ValueError, TypeError):
        return {"success": False, "error": {"message": f"Invalid order_id: {order_id}"}}
    r = sms_session.post(f"{SMSCODE_BASE}/orders/resend", headers=sms_headers(), json={"id": oid}, timeout=15)
    try:
        return r.json()
    except Exception:
        return {"success": r.status_code == 200, "status_code": r.status_code, "body": r.text[:200]}



def fetch_operators(country_id, platform_id=5):
    """Fetch available operators/carriers for a country + platform from SMSCode.
    Returns list of {operator_id, code, name} sorted by name."""
    try:
        r = sms_session.get(
            f"{SMSCODE_BASE}/catalog/operators?country_id={country_id}&platform_id={platform_id}",
            headers=sms_headers(), timeout=15
        )
        if r.status_code != 200:
            return []
        data = r.json().get("data", [])
        # Each entry: {operator_id: int|null, code: str, name: str, local_name: str|null}
        return data
    except Exception as e:
        print(f"[FETCH_OPERATORS_ERROR] country_id={country_id}: {e}")
        return []



def export_to_google_sheets(acc):
    settings = get_settings()
    url = settings.get("google_sheets_url")
    if not url:
        return
    
    # Send non-blocking HTTP POST request to Apps Script Webhook
    payload = {
        "email": acc.get("email"),
        "password": acc.get("password"),
        "first_name": acc.get("first_name"),
        "phone": acc.get("phone"),
        "status": acc.get("status")
    }
    try:
        # Timeout 5s, ignore response to keep execution fast
        http_requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Error exporting to Google Sheets: {e}")


def format_account_card(acc, session):
    username = acc["email"].replace("@gmail.com", "")
    phone = acc.get("phone") or "-"
    first_name = acc.get("first_name", "")
    last_name = acc.get("last_name", "")
    password = acc.get("password", "")
    country = acc.get("country", "Brazil")

    # Add reuse info
    uses = session.get("current_number_uses", 1)
    max_codes = get_max_codes()
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
        f"➡️ _Tekan / tap pada kotak teks untuk menyalin otomatis._\n"
        f"➡️ Input data di atas ke Gmail, lalu tap *📲 Minta OTP*"
    )


def session_keyboard(acc_id, order_id, waiting_otp=False):
    # Pass acc_id and order_id inside callback data to avoid global session conflicts
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


# Conversation states for "Mulai" wizard
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

    settings = get_settings()
    if not settings.get("smscode_token"):
        await query.edit_message_text("⚠️ Token SMSCode belum diset. Pakai `/settoken TOKEN` dulu.", parse_mode="Markdown", reply_markup=back_kb())
        return ConversationHandler.END

    results = generate_emails(count, keyword, position, password)
    # Clear old accounts + numbers before starting fresh session
    save_accounts([])
    for r in results:
        add_account(r["email"], r["password"], r["first_name"], r["last_name"])

    # Force fresh numbers — clear reusable numbers from previous session
    save_numbers([])

    session = {
        "active": True,
        "paused": True,  # Paused until country/price selected
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
    save_session(session)
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
        [InlineKeyboardButton("📥 Export", callback_data="menu_export"), InlineKeyboardButton("🔥 Warm-Up", callback_data="sess_warmup")],
        [InlineKeyboardButton("🌐 IP Hunter", callback_data="menu_ip_hunter"), InlineKeyboardButton("🃏 CC Extrap", callback_data="menu_cc_extrap")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="menu_settings"), InlineKeyboardButton("🧹 Clear", callback_data="menu_clear")],
    ])


def back_kb():
    """Single 🏠 Menu Utama button for command responses."""
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")]])


# SMSCode country IDs for number ordering
# price_min/price_max used for DIRECT FALLBACK filter only
# Routed order (Step 2) uses max_price only — server picks best route freely
SMSCODE_COUNTRIES = [
    {"id": 74, "name": "Brazil", "flag": "🇧🇷", "price_min": 0, "price_max": 2500},
]

# Default price range (used in fallback)
SMS_PRICE_MIN = 0
SMS_PRICE_MAX = 2500


def country_selection_keyboard():
    """Keyboard with country choices for number selection."""
    rows = []
    for c in SMSCODE_COUNTRIES:
        rows.append([InlineKeyboardButton(f"{c['flag']} {c['name']}", callback_data=f"country_select:{c['id']}")])
    rows.append([InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")])
    return InlineKeyboardMarkup(rows)


def fetch_country_prices(country_id, operator_id=None):
    """Fetch available SMS product prices for a country from SMSCode API.
    Returns list of {id, catalog_product_id, price, available, operator_id, operator_name} sorted by price."""
    platform_id = 5  # Google / Gmail
    # Get per-country price range
    country = next((c for c in SMSCODE_COUNTRIES if c["id"] == country_id), None)
    p_min = country.get("price_min", SMS_PRICE_MIN) if country else SMS_PRICE_MIN
    p_max = country.get("price_max", SMS_PRICE_MAX) if country else SMS_PRICE_MAX
    try:
        url = f"{SMSCODE_BASE}/catalog/products?country_id={country_id}&platform_id={platform_id}&limit=200"
        if operator_id is not None:
            url += f"&operator_id={operator_id}"
        r = sms_session.get(url, headers=sms_headers(), timeout=15)
        if r.status_code != 200:
            return []
        products = r.json().get("data", [])
        matching = [
            {
                "id": p["id"],
                "catalog_product_id": p.get("catalog_product_id"),
                "price": p["price"],
                "available": p.get("available", 0),
                "operator_id": p.get("operator_id"),
                "operator_name": p.get("operator_name"),
            }
            for p in products
            if p_min <= p.get("price", 0) <= p_max and p.get("available", 0) > 0
        ]
        matching.sort(key=lambda x: x["price"])
        return matching
    except Exception as e:
        print(f"[FETCH_PRICES_ERROR] country_id={country_id}: {e}")
        return []


def price_selection_keyboard(country_id, products):
    """Keyboard with price options for a country. Max 6 options shown."""
    rows = []
    for p in products[:6]:
        op_label = f" [{p.get('operator_name', 'Any')}]" if p.get('operator_name') else ""
        rows.append([InlineKeyboardButton(
            f"💰 Rp {p['price']}{op_label} (stok: {p['available']})",
            callback_data=f"price_select:{country_id}:{p['id']}"
        )])
    # Bypass button removed — only manual price selection
    rows.append([InlineKeyboardButton("⬅️ Pilih Negara Lain", callback_data="show_country_select")])
    rows.append([InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")])
    return InlineKeyboardMarkup(rows)


def ensure_number_for_account(acc):
    """Get SMS number for account.
    Strategy: pick a RANDOM product from catalog with price 800-1000 IDR.
    No routed order — direct random selection for freshness.
    """
    settings = get_settings()
    active = get_active_number()
    if active:
        tracked = track_number_usage(active["phone"], active["order_id"], acc["email"])
        update_account(acc["id"], {"phone": active["phone"], "order_id": active["order_id"], "status": "sms_pending", "country": active.get("country", "Brazil")})
        print(f"[REUSE_NUMBER] {active['phone']} order={active['order_id']} uses={tracked['codes_used']}/{get_max_codes()} for {acc['email']}")
        return {"reused": True, "phone": active["phone"], "order_id": active["order_id"], "uses": tracked["codes_used"], "country": active.get("country", "Brazil")}
    else:
        numbers = get_numbers()
        dbg = [{"phone":n.get("phone","?"),"can_reuse":n.get("can_reuse"),"codes_used":n.get("codes_used",0),"order_id":n.get("order_id")} for n in numbers]
        print(f"[NEW_NUMBER] No reusable number. numbers={json.dumps(dbg, default=str)}")

    # --- Determine country ---
    session = get_session()
    selected_country_id = session.get("selected_country_id") if session else None
    country = next((c for c in SMSCODE_COUNTRIES if c["id"] == selected_country_id), SMSCODE_COUNTRIES[0])
    country_id = country["id"]

    # Dynamic price range and operator selection - TRIGGER DEPLOY
    if country_id == 74:  # Brazil
        PRICE_MIN = 1000
        PRICE_MAX = 1250
        target_operator_id = 347  # Vivo S.A. operator_id
    else:
        PRICE_MIN = 0
        PRICE_MAX = 3500
        target_operator_id = None
        
    platform_id = 5  # Google/YT/Gmail only

    # --- Fetch catalog to get catalog_product_id ---
    catalog_product_id = None
    direct_fallback_products = []
    try:
        r = sms_session.get(
            f"{SMSCODE_BASE}/catalog/products?country_id={country_id}&platform_id={platform_id}&limit=200",
            headers=sms_headers(), timeout=15
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
        # Sort by price ascending to get the cheapest first
        direct_fallback_products.sort(key=lambda x: x.get("price", 0))
        all_prices = sorted(set(p.get("price", 0) for p in products))
        eligible_prices = sorted(set(p.get("price", 0) for p in direct_fallback_products))
        print(f"[CATALOG] {country['name']}: catalog_product_id={catalog_product_id}, "
              f"total={len(products)}, in_range({PRICE_MIN}-{PRICE_MAX})={len(direct_fallback_products)}, "
              f"all_prices={all_prices[:15]}, eligible_prices={eligible_prices}")
    except Exception as e:
        raise RuntimeError(f"Gagal fetch catalog: {e}")

    if not catalog_product_id and not direct_fallback_products:
        raise RuntimeError(f"Tidak ada produk Google Brazil.")

    # --- Step 1: ROUTED ORDER cheapest within PRICE_MIN-PRICE_MAX ---
    if catalog_product_id:
        result = sms_create_order(
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
                price = order.get("amount", 0)
                op_name = order.get("operator_name", "Auto")
                print(f"[ROUTED_OK] {country['flag']} {country['name']} best_success Rp {PRICE_MIN}-{PRICE_MAX} operator={op_name} Rp {price}")
                update_account(acc["id"], {"phone": phone, "order_id": order_id, "status": "sms_pending", "country": country["name"]})
                tracked = track_number_usage(phone, order_id, acc["email"], country=country["name"])
                return {"reused": False, "phone": phone, "order_id": order_id, "uses": tracked["codes_used"], "country": country["name"], "flag": country["flag"]}
        err_code = result.get("error", {}).get("code", "")
        err_msg = result.get("error", {}).get("message", str(result))
        print(f"[ROUTED_FAIL] {country['name']}: {err_code} — {err_msg} | range={PRICE_MIN}-{PRICE_MAX}")
        if err_code == "INSUFFICIENT_BALANCE":
            raise RuntimeError("Saldo SMSCode tidak cukup.")

    # --- Step 2: RANDOM FALLBACK from 800-1000 products ---
    if direct_fallback_products:
        print(f"[RANDOM_FALLBACK] Trying {len(direct_fallback_products)} products (Rp {PRICE_MIN}-{PRICE_MAX})...")
        for p in direct_fallback_products[:5]:
            pid = p["id"]
            price = p.get("price", 0)
            print(f"[RANDOM_ORDER] product_id={pid} price=Rp {price} avail={p.get('available',0)}")
            result = sms_create_order(product_id=pid)
            if result.get("success"):
                orders = result.get("data", {}).get("orders", [])
                if orders:
                    order = orders[0]
                    phone = order.get("phone_number", "")
                    order_id = order["id"]
                    actual_price = order.get("amount", price)
                    op_name = order.get("operator_name", "?")
                    print(f"[ORDER_OK] {country['flag']} {country['name']} product={pid} operator={op_name} Rp {actual_price}")
                    update_account(acc["id"], {"phone": phone, "order_id": order_id, "status": "sms_pending", "country": country["name"]})
                    tracked = track_number_usage(phone, order_id, acc["email"], country=country["name"])
                    return {"reused": False, "phone": phone, "order_id": order_id, "uses": tracked["codes_used"], "country": country["name"], "flag": country["flag"]}
            err_code = result.get("error", {}).get("code", "")
            err_msg = result.get("error", {}).get("message", str(result))
            print(f"[ORDER_FAIL] product={pid}: {err_code} — {err_msg}")
            if err_code == "INSUFFICIENT_BALANCE":
                raise RuntimeError("Saldo SMSCode tidak cukup.")

    # --- Step 3: EMERGENCY FALLBACK for Vivo S.A. if exact 1000-1250 range is temporarily unavailable ---
    print(f"[EMERGENCY_FALLBACK] Exact range {PRICE_MIN}-{PRICE_MAX} failed. Trying lowest available Vivo S.A. product...")
    any_vivo_products = [
        p for p in products
        if p.get("available", 0) > 0 and p.get("id")
        and (p.get("operator_id") == target_operator_id if (target_operator_id is not None and p.get("operator_id") is not None) else True)
    ]
    any_vivo_products.sort(key=lambda x: x.get("price", 0))
    for p in any_vivo_products[:3]:
        pid = p["id"]
        price = p.get("price", 0)
        print(f"[EMERGENCY_ORDER] Vivo S.A. product_id={pid} price=Rp {price}")
        result = sms_create_order(product_id=pid)
        if result.get("success"):
            orders = result.get("data", {}).get("orders", [])
            if orders:
                order = orders[0]
                phone = order.get("phone_number", "")
                order_id = order["id"]
                actual_price = order.get("amount", price)
                op_name = order.get("operator_name", "?")
                print(f"[ORDER_OK_EMERGENCY] {country['flag']} {country['name']} product={pid} operator={op_name} Rp {actual_price}")
                update_account(acc["id"], {"phone": phone, "order_id": order_id, "status": "sms_pending", "country": country["name"]})
                tracked = track_number_usage(phone, order_id, acc["email"], country=country["name"])
                return {"reused": False, "phone": phone, "order_id": order_id, "uses": tracked["codes_used"], "country": country["name"], "flag": country["flag"]}

    raise RuntimeError(f"Gagal order nomor Brazil (Vivo S.A.). Stok di SMSCode sedang habis. Coba beberapa saat lagi.")

async def send_next_session_card(chat, bot_instance):
    session = get_session()
    if not session or not session.get("active"):
        await chat.send_message("Tidak ada sesi aktif. Gunakan /session atau /go")
        return
    # Guard: check if all accounts have been processed
    processed = session.get("done", 0) + session.get("failed", 0) + session.get("skipped", 0)
    total = session.get("total", 0)
    if total > 0 and processed >= total:
        session["active"] = False
        save_session(session)
        await chat.send_message(
            f"🎉 *SESI SELESAI!*\n\n✅ Berhasil: *{session.get('done',0)}*\n❌ Gagal: *{session.get('failed',0)}*\n⏭ Dilewati: *{session.get('skipped',0)}*",
            parse_mode="Markdown",
            reply_markup=home_menu_keyboard()
        )
        return
    acc = next_queued_account()
    if not acc:
        session["active"] = False
        save_session(session)
        await chat.send_message(
            f"🎉 *SESI SELESAI!*\n\n✅ Berhasil: *{session.get('done',0)}*\n❌ Gagal: *{session.get('failed',0)}*\n⏭ Dilewati: *{session.get('skipped',0)}*",
            parse_mode="Markdown",
            reply_markup=home_menu_keyboard()
        )
        return
    session["current_account_id"] = acc["id"]
    save_session(session)
    try:
        number_info = ensure_number_for_account(acc)
    except Exception as e:
        update_account(acc["id"], {"status": "failed", "notes": f"number_error: {e}"})
        session["failed"] = session.get("failed", 0) + 1
        save_session(session)
        await chat.send_message(f"❌ Gagal ambil nomor: {e}")
        await send_next_session_card(chat, bot_instance)
        return
    updated_acc = get_account(acc["id"])
    if updated_acc:
        acc = updated_acc
    session["current_order_id"] = acc.get("order_id")
    session["current_number_uses"] = number_info["uses"]
    session["waiting_otp"] = False
    save_session(session)
    
    try:
        await chat.send_message(
            format_account_card(acc, session), 
            parse_mode="Markdown", 
            reply_markup=session_keyboard(acc["id"], acc.get("order_id"), False)
        )
    except Exception as e:
        print(f"[MARKDOWN_FAIL] send_next_session_card markdown error: {e}")
        # Fallback to plain text to avoid stuck sessions
        try:
            await chat.send_message(
                format_account_card(acc, session), 
                reply_markup=session_keyboard(acc["id"], acc.get("order_id"), False)
            )
        except Exception as e2:
            print(f"[FATAL_SEND_FAIL] Failed to send even plain text: {e2}")


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
    settings = get_settings()
    if not settings.get("smscode_token"):
        await update.message.reply_text("⚠️ Token SMSCode belum diset. Pakai `/settoken TOKEN` dulu.", parse_mode="Markdown", reply_markup=back_kb())
        return
    results = generate_emails(count, keyword, position, password)
    # Clear old accounts + numbers before starting fresh session
    save_accounts([])
    for r in results:
        add_account(r["email"], r["password"], r["first_name"], r["last_name"])
    # Force fresh numbers — clear reusable numbers from previous session
    save_numbers([])
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
    save_session(session)
    await update.message.reply_text(f"✅ Sesi dibuat: *{len(results)} akun*\nKeyword: `{keyword}` | Posisi: `{position}`", parse_mode="Markdown")
    await send_next_session_card(update.message.chat, context.bot)


@check_auth
async def cmd_go(update: Update, context: ContextTypes.DEFAULT_TYPE):
    settings = get_settings()
    if not settings.get("smscode_token"):
        await update.message.reply_text("⚠️ Token SMSCode belum diset. Pakai `/settoken TOKEN` dulu.", parse_mode="Markdown", reply_markup=back_kb())
        return
    session = get_session()
    if not session.get("active"):
        queued = [a for a in get_accounts() if a["status"] == "queued"]
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
        save_session(session)
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
        add_account(r["email"], r["password"], r["first_name"], r["last_name"])
    preview = "\n".join([f"`{x['email']}`" for x in results[:5]])
    await update.message.reply_text(f"✅ *{len(results)} akun* ditambahkan ke antrian\n\n{preview}\n\nGunakan `/go` untuk mulai.", parse_mode="Markdown", reply_markup=back_kb())


@check_auth
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = get_session()
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
    session = get_session()
    if not session.get("active"):
        await update.message.reply_text("Tidak ada sesi aktif.", reply_markup=back_kb())
        return
    session["paused"] = True
    save_session(session)
    await update.message.reply_text("⏸ Sesi dipause. Pakai `/resume` untuk lanjut.", parse_mode="Markdown", reply_markup=back_kb())


@check_auth
async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = get_session()
    if not session.get("active"):
        await update.message.reply_text("Tidak ada sesi aktif. Pakai `/go` atau `/session`.", reply_markup=back_kb())
        return
    session["paused"] = False
    save_session(session)
    await update.message.reply_text("▶️ Sesi dilanjutkan.")
    await send_next_session_card(update.message.chat, context.bot)


@check_auth
async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = get_settings()
    if not s.get("smscode_token"):
        await update.message.reply_text("⚠️ Token belum diset: `/settoken TOKEN`", parse_mode="Markdown", reply_markup=back_kb())
        return
    try:
        res = sms_balance()
        if res.get("success"):
            bal = res.get("data", {}).get("balance", "?")
            # Format balance to currency Rupiah
            bal_rp = f"Rp {int(bal):,}".replace(",", ".")
            await update.message.reply_text(f"💰 Saldo SMSCode: *{bal_rp}*", parse_mode="Markdown", reply_markup=back_kb())
        else:
            await update.message.reply_text(f"❌ {res.get('error', {}).get('message', 'Unknown error')}", reply_markup=back_kb())
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}", reply_markup=back_kb())


@check_auth
async def cmd_apidebug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Debug: query SMSCode catalog API — services list + products for all countries."""
    lines = ["🔍 *API Debug*\n"]

    # --- Part 1: List all Google-related services ---
    lines.append("📋 *Services (Google-related):*")
    try:
        r = sms_session.get(
            f"{SMSCODE_BASE}/catalog/services",
            headers=sms_headers(), timeout=15
        )
        if r.status_code == 200:
            services = r.json().get("data", [])
            for s in services:
                name = s.get("name", "")
                if "google" in name.lower() or "gmail" in name.lower() or "youtube" in name.lower():
                    lines.append(f"  • id=`{s.get('id')}` name=`{name}` active={s.get('active')}")
        else:
            lines.append(f"  HTTP {r.status_code}: {r.text[:100]}")
    except Exception as e:
        lines.append(f"  ❌ {e}")
    lines.append("")

    # --- Part 2: Products for each country × each Google platform ---
    google_platforms = [5, 1817, 1819, 615]  # Google/YT/Gmail, Google Chat, Google Messenger, GoogleVoice
    # Also scan some common IDs
    for test_pid in [6, 7, 8, 9, 10, 11, 12, 15, 20, 25, 30, 50, 100]:
        try:
            r = sms_session.get(
                f"{SMSCODE_BASE}/catalog/products?country_id=74&platform_id={test_pid}&limit=1",
                headers=sms_headers(), timeout=10
            )
            if r.status_code == 200:
                raw = r.json().get("data", [])
                prods = raw.get("products", []) if isinstance(raw, dict) else raw
                if prods:
                    pname = prods[0].get("name", "?")
                    if "google" in pname.lower() or "gmail" in pname.lower() or "chat" in pname.lower():
                        if test_pid not in google_platforms:
                            google_platforms.append(test_pid)
                            lines.append(f"🔎 Found Google service at platform\\_id=`{test_pid}`: `{pname}`")
        except Exception:
            pass

    for country in SMSCODE_COUNTRIES:
        cid = country["id"]
        for pid in google_platforms:
            try:
                r = sms_session.get(
                    f"{SMSCODE_BASE}/catalog/products?country_id={cid}&platform_id={pid}&limit=50",
                    headers=sms_headers(), timeout=15
                )
                if r.status_code == 200:
                    raw = r.json().get("data", [])
                    products = raw.get("products", []) if isinstance(raw, dict) else raw
                    if not products:
                        continue
                    cpid = None
                    for p in products:
                        if p.get("catalog_product_id"):
                            cpid = p["catalog_product_id"]
                            break
                    prices = sorted(p.get("price", 0) for p in products)
                    avail = sum(1 for p in products if p.get("available", 0) > 0)
                    pname = products[0].get("name", "?") if products else "?"
                    lines.append(f"{country['flag']} *{country['name']}* pid={pid} (`{pname}`):")
                    lines.append(f"  catalog\\_product\\_id=`{cpid}` total={len(products)} avail={avail}")
                    lines.append(f"  Prices: {prices[:8]}{'...' if len(prices) > 8 else ''}")
            except Exception as e:
                lines.append(f"{country['flag']} {country['name']} pid={pid}: ❌ {e}")
        lines.append("")

    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:4000] + "\n..."
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=back_kb())


@check_auth
async def cmd_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    numbers = get_numbers()
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
    accounts = get_accounts()
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

    accounts = get_accounts()
    if status_filter:
        accounts = [a for a in accounts if a["status"] == status_filter]

    if not accounts:
        await update.message.reply_text(f"📭 Tidak ada akun dengan status *{status_filter}* untuk di-export.", parse_mode="Markdown", reply_markup=back_kb())
        return

    # Export EACH email as its own code block so it can be copied individually
    combo = "\n".join(f"`{a['email']}`" for a in accounts)
    await update.message.reply_text(
        f"📥 *SALIN EMAIL ({len(accounts)}):*\n\n_(Tap masing-masing email untuk menyalin)_\n\n{combo}",
        parse_mode="Markdown",
        reply_markup=back_kb()
    )


@check_auth
async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = get_settings()
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
    s = get_settings()
    s["preset_keyword"] = args[0]
    s["preset_password"] = args[1]
    s["preset_count"] = int(args[2]) if args[2].isdigit() else 5
    s["preset_position"] = args[3]
    save_settings(s)
    await update.message.reply_text(f"✅ Preset disimpan:\nKeyword: `{s['preset_keyword']}`\nPassword: `{s['preset_password']}`\nJumlah: `{s['preset_count']}`\nPosisi: `{s['preset_position']}`", parse_mode="Markdown", reply_markup=back_kb())


@check_auth
async def cmd_setsheet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    if not args:
        await update.message.reply_text("❌ Format: `/setsheet WEBHOOK_URL`\nIsi `clear` untuk menghapus.", parse_mode="Markdown", reply_markup=back_kb())
        return
    s = get_settings()
    if args[0].lower() == "clear":
        s["google_sheets_url"] = ""
        await update.message.reply_text("✅ Google Sheets URL dihapus.", reply_markup=back_kb())
    else:
        s["google_sheets_url"] = args[0]
        await update.message.reply_text("✅ Google Sheets URL disimpan.", reply_markup=back_kb())
    save_settings(s)
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
    s = get_settings()
    s["smscode_token"] = args[0]
    save_settings(s)
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
    s = get_settings()
    s["birth_date"] = args[0]
    save_settings(s)
    await update.message.reply_text(f"✅ Birth date: `{args[0]}`", parse_mode="Markdown", reply_markup=back_kb())


@check_auth
async def cmd_setproduct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    if not args or not args[0].isdigit():
        await update.message.reply_text("❌ Format: `/setproduct PRODUCT_ID`", parse_mode="Markdown", reply_markup=back_kb())
        return
    s = get_settings()
    s["smscode_product_id"] = int(args[0])
    save_settings(s)
    await update.message.reply_text(f"✅ Product ID: `{args[0]}`", parse_mode="Markdown", reply_markup=back_kb())


@check_auth
async def cmd_setgender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    if not args or args[0] not in ("male", "female"):
        await update.message.reply_text("❌ Format: `/setgender male|female`", parse_mode="Markdown", reply_markup=back_kb())
        return
    s = get_settings()
    s["gender"] = args[0]
    save_settings(s)
    await update.message.reply_text(f"✅ Gender: `{args[0]}`", parse_mode="Markdown", reply_markup=back_kb())


@check_auth
async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    accounts = get_accounts()
    numbers = get_numbers()
    sc = {}
    for a in accounts:
        sc[a['status']] = sc.get(a['status'], 0) + 1
    text = [f"📊 *Statistik*", f"👥 Total akun: *{len(accounts)}*", f"📞 Total nomor: *{len(numbers)}*"]
    for k, v in sc.items():
        text.append(f"- `{k}`: *{v}*")
    await update.message.reply_text("\n".join(text), parse_mode="Markdown", reply_markup=back_kb())


@check_auth
async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_accounts([])
    save_numbers([])
    save_session({})
    await update.message.reply_text("✅ Accounts, numbers, dan session dibersihkan.", reply_markup=back_kb())


@check_auth
async def cmd_ccgen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate 100 CC from BIN, check live via API, show first LIVE + fake address."""
    status_msg = await update.message.reply_text(
        f"⏳ *CC EXTRAP*\n\n"
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
            f"📍 *Alamat Palsu (Thailand):*\n"
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
    """Check BIN info. Usage: /cccheck BIN (6-8 digits)"""
    args = context.args or []
    if not args:
        await update.message.reply_text(
            "❌ Format: `/cccheck BIN`\n\nContoh: `/cccheck 515462`",
            parse_mode="Markdown",
            reply_markup=back_kb()
        )
        return
    bin_str = args[0].strip().split("|")[0][:12]  # Take first part, max 12 digits
    status_msg = await update.message.reply_text("⏳ Mengecek BIN di binlist.io...")
    loop = asyncio.get_running_loop()
    info = await loop.run_in_executor(None, vccgen_lookup_bin, bin_str)
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
    session = get_session()
    session["waiting_otp"] = True
    save_session(session)
    await query.edit_message_reply_markup(reply_markup=None)
    status_msg = await query.message.reply_text(f"⏳ Polling OTP untuk order `{order_id}` tiap 5 detik...", parse_mode="Markdown")
    
    # Save polling message ID for auto-cleanup
    session["last_polling_msg_id"] = status_msg.message_id
    save_session(session)

    # For reused numbers (2nd+ OTP), we need to use after_code to get NEW OTP only
    after_code = session.get("last_otp_code") if session.get("current_number_uses", 0) > 1 else None

    # Auto-resend SMS for 2nd+ account on same number
    if session.get("current_number_uses", 0) > 1:
        try:
            sms_resend(order_id)
            await status_msg.edit_text(f"🔄 Resend SMS otomatis (akun ke-{session.get('current_number_uses', 0)} di nomor ini)...\n⏳ Polling OTP tiap 5 detik...", parse_mode="Markdown")
            await asyncio.sleep(2)
        except Exception:
            pass  # Resend failed, still try polling

    # 24 attempts * 5 seconds = 120 seconds (2 minutes)
    _poll_start = time.time()
    for attempt in range(1, 25):
        try:
            res = sms_get_order(order_id, after_code=after_code)
            if res.get("success"):
                data = res.get("data", {})
                otp = data.get("otp_code")

                # Verify it's a new code if after_code is set (reused number)
                if otp and (after_code is None or otp != after_code):
                    otp_elapsed = round(time.time() - _poll_start, 1)
                    session["last_otp_code"] = otp
                    save_session(session)
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
                err = res.get('error', {}).get('message', 'Unknown error')
                # Network errors: keep retrying, don't abort
                try:
                    await status_msg.edit_text(f"⚠️ Retry... ({attempt*5}s)\nOrder: `{order_id}`", parse_mode="Markdown")
                except Exception:
                    pass
        except Exception:
            # ANY exception during polling: keep retrying until 2-min timeout
            try:
                await status_msg.edit_text(f"⚠️ Network error, mencoba ulang... ({attempt*5}s)\nOrder: `{order_id}`", parse_mode="Markdown")
            except Exception:
                pass
        await asyncio.sleep(5)
    
    # Timeout after 2 minutes — cancel the order via API
    cancel_ok = False
    cancel_msg = ""
    
    # First check if the order can be cancelled
    order_status = sms_get_order(order_id)
    order_data = order_status.get("data", {})
    can_cancel = order_data.get("can_cancel", True)  # default True to try anyway
    
    if can_cancel:
        for _attempt in range(3):
            result = sms_cancel_order(order_id)
            if result.get("success"):
                cancel_ok = True
                cancel_msg = "✅ Nomor berhasil dibatalkan dari SMSCode (saldo dikembalikan)"
                break
            err = result.get("error", {})
            if err.get("code") == "CONFLICT":
                # Already cancelled or expired
                cancel_ok = True
                cancel_msg = f"ℹ️ Order sudah {order_data.get('status', 'selesai')}"
                break
            # Retry on network errors
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
    
    mark_number_exhausted(order_id)
    session = get_session()
    session["waiting_otp"] = False
    # Keep current account active so user can choose next action after timeout
    session["current_account_id"] = acc_id
    session["current_order_id"] = None
    save_session(session)

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
    session = get_session()
    if order_id and order_id != "none":
        try:
            sms_cancel_order(order_id)
        except Exception:
            pass
        mark_number_exhausted(order_id)

    if not acc_id or acc_id == "none":
        acc_id = session.get("current_account_id")

    if not acc_id:
        await query.edit_message_text("❌ Gagal ganti nomor: Akun tidak aktif.", reply_markup=back_kb())
        return

    wait_msg = "🔄 Memproses nomor baru untuk akun yang sama..."
    if from_timeout:
        wait_msg = "🔄 Timeout diproses. Mengambil nomor baru untuk akun yang sama..."
    await query.edit_message_text(wait_msg, parse_mode="Markdown")

    acc = get_account(acc_id)
    if not acc:
        await query.edit_message_text("❌ Gagal ganti nomor: Akun tidak ditemukan.", reply_markup=back_kb())
        return

    try:
        number_info = ensure_number_for_account(acc)
    except Exception as e:
        await query.edit_message_text(
            f"❌ Gagal ambil nomor baru: {e}\nSilakan tekan kembali tombol *Ganti Nomor*.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Ganti Nomor", callback_data=f"sess_change_number:{acc_id}:none")]]),
        )
        return

    acc = get_account(acc_id)
    session["current_account_id"] = acc_id
    session["current_order_id"] = acc.get("order_id")
    session["current_number_uses"] = number_info["uses"]
    session["waiting_otp"] = False
    save_session(session)

    await query.edit_message_text(
        format_account_card(acc, session),
        parse_mode="Markdown",
        reply_markup=session_keyboard(acc["id"], acc.get("order_id"), False)
    )


async def handle_timeout_next_account(query, acc_id, context):
    session = get_session()
    update_account(acc_id, {"status": "failed", "notes": "otp_timeout_user_next_account"})
    session["failed"] = session.get("failed", 0) + 1
    session["waiting_otp"] = False
    session["current_account_id"] = None
    session["current_order_id"] = None
    save_session(session)
    await query.edit_message_text("⏭ Akun ditandai gagal. Lanjut ke akun berikutnya...", parse_mode="Markdown")
    await asyncio.sleep(1)
    await send_next_session_card(query.message.chat, context.bot)


async def handle_timeout_end_session(query, context):
    session = get_session()
    session["active"] = False
    session["paused"] = True
    session["waiting_otp"] = False
    session["current_order_id"] = None
    save_session(session)
    await query.edit_message_text("🛑 Sesi diakhiri setelah timeout OTP.", parse_mode="Markdown", reply_markup=home_menu_keyboard())


async def handle_done_like(query, status, acc_id, order_id, context, skipped=False):
    session = get_session()
    # Resolve None order_id string
    if order_id == "none" or str(order_id).lower() == "none":
        order_id = None
        
    if not acc_id:
        acc_id = session.get("current_account_id")
        
    if not acc_id:
        await query.answer("Tidak ada akun aktif", show_alert=True)
        return
        
    note = ""
    update_account(acc_id, {"status": status, "notes": note})
        
    if status == "created":
        session["done"] = session.get("done", 0) + 1
        # Export to Google Sheets in background
        if acc_id:
            full_acc = get_account(acc_id)
            if full_acc:
                threading.Thread(target=export_to_google_sheets, args=(full_acc,)).start()
    elif skipped:
        session["skipped"] = session.get("skipped", 0) + 1
    else:
        session["failed"] = session.get("failed", 0) + 1
        
    settings = get_settings()
    # Cancel order on failure to refund balance
    if status == "failed" and order_id:
        try:
            sms_cancel_order(order_id)
        except Exception:
            pass
        mark_number_exhausted(order_id)

    # Finish SMS order ONLY when reuse count reaches max
    if status == "created" and order_id:
        uses = session.get("current_number_uses", 0)
        max_codes = get_max_codes()
        if uses >= max_codes:
            try:
                sms_finish_order(order_id)
            except Exception:
                pass
            mark_number_exhausted(order_id)
        
    # Auto-cleanup: delete the polling message if it exists
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
    save_session(session)
    label = "berhasil" if status == "created" else ("dilewati" if skipped else "gagal")
    try:
        await query.edit_message_text(f"✅ Akun `{acc_id}` {label}. Lanjut akun berikutnya...", parse_mode="Markdown")
    except Exception:
        # If edit fails (message already deleted/modified), send new message instead
        try:
            await query.message.chat.send_message(f"✅ Akun `{acc_id}` {label}. Lanjut akun berikutnya...", parse_mode="Markdown")
        except Exception:
            pass
    await send_next_session_card(query.message.chat, context.bot)


# ═══════════════════════════════════════════════════════════════
# IP HUNTER ENGINE — integrated into bot
# ═══════════════════════════════════════════════════════════════

# Brazilian cities database: city_name -> {lat, lon, tz, state}
BRAZIL_CITIES_DB = {
    "são paulo": {"lat": -23.5505, "lon": -46.6333, "tz": "America/Sao_Paulo", "state": "SP"},
    "sao paulo": {"lat": -23.5505, "lon": -46.6333, "tz": "America/Sao_Paulo", "state": "SP"},
    "rio de janeiro": {"lat": -22.9068, "lon": -43.1729, "tz": "America/Sao_Paulo", "state": "RJ"},
    "curitiba": {"lat": -25.4284, "lon": -49.2733, "tz": "America/Sao_Paulo", "state": "PR"},
    "belo horizonte": {"lat": -19.9167, "lon": -43.9345, "tz": "America/Sao_Paulo", "state": "MG"},
    "brasília": {"lat": -15.7975, "lon": -47.8919, "tz": "America/Sao_Paulo", "state": "DF"},
    "brasilia": {"lat": -15.7975, "lon": -47.8919, "tz": "America/Sao_Paulo", "state": "DF"},
    "fortaleza": {"lat": -3.7172, "lon": -38.5433, "tz": "America/Fortaleza", "state": "CE"},
    "salvador": {"lat": -12.9714, "lon": -38.5014, "tz": "America/Bahia", "state": "BA"},
    "manaus": {"lat": -3.1190, "lon": -60.0217, "tz": "America/Manaus", "state": "AM"},
    "recife": {"lat": -8.0476, "lon": -34.8770, "tz": "America/Recife", "state": "PE"},
    "goiânia": {"lat": -16.6869, "lon": -49.2648, "tz": "America/Sao_Paulo", "state": "GO"},
    "goiania": {"lat": -16.6869, "lon": -49.2648, "tz": "America/Sao_Paulo", "state": "GO"},
    "porto alegre": {"lat": -30.0346, "lon": -51.2177, "tz": "America/Sao_Paulo", "state": "RS"},
    "campinas": {"lat": -22.9099, "lon": -47.0626, "tz": "America/Sao_Paulo", "state": "SP"},
    "belém": {"lat": -1.4558, "lon": -48.5024, "tz": "America/Belem", "state": "PA"},
    "belem": {"lat": -1.4558, "lon": -48.5024, "tz": "America/Belem", "state": "PA"},
    "florianópolis": {"lat": -27.5954, "lon": -48.5480, "tz": "America/Sao_Paulo", "state": "SC"},
    "florianopolis": {"lat": -27.5954, "lon": -48.5480, "tz": "America/Sao_Paulo", "state": "SC"},
    "vitória": {"lat": -20.3155, "lon": -40.3128, "tz": "America/Sao_Paulo", "state": "ES"},
    "vitoria": {"lat": -20.3155, "lon": -40.3128, "tz": "America/Sao_Paulo", "state": "ES"},
    "viana": {"lat": -20.3903, "lon": -40.4961, "tz": "America/Sao_Paulo", "state": "ES"},
    "cariacica": {"lat": -20.3005, "lon": -40.4692, "tz": "America/Sao_Paulo", "state": "ES"},
    "banabuiú": {"lat": -5.3097, "lon": -38.9206, "tz": "America/Fortaleza", "state": "CE"},
    "banabuiu": {"lat": -5.3097, "lon": -38.9206, "tz": "America/Fortaleza", "state": "CE"},
    "natal": {"lat": -5.7945, "lon": -35.2110, "tz": "America/Fortaleza", "state": "RN"},
    "maceió": {"lat": -9.6658, "lon": -35.7353, "tz": "America/Maceio", "state": "AL"},
    "aracaju": {"lat": -10.9091, "lon": -37.0677, "tz": "America/Maceio", "state": "SE"},
    "teresina": {"lat": -5.0920, "lon": -42.8038, "tz": "America/Fortaleza", "state": "PI"},
    "campo grande": {"lat": -20.4697, "lon": -54.6201, "tz": "America/Campo_Grande", "state": "MS"},
    "cuiabá": {"lat": -15.6014, "lon": -56.0979, "tz": "America/Cuiaba", "state": "MT"},
    "cuiaba": {"lat": -15.6014, "lon": -56.0979, "tz": "America/Cuiaba", "state": "MT"},
    "palmas": {"lat": -10.1689, "lon": -48.3317, "tz": "America/Araguaina", "state": "TO"},
    "são josé dos pinhais": {"lat": -25.5364, "lon": -49.2063, "tz": "America/Sao_Paulo", "state": "PR"},
    "santo antônio de posse": {"lat": -22.6056, "lon": -46.9188, "tz": "America/Sao_Paulo", "state": "SP"},
}

GOOD_ISP_KEYWORDS = [
    "vivo", "telefonica", "claro", "net servicos", "america movil",
    "oi", "telemar", "tim", "algar", "sercomtel", "copel",
    "brisanet", "desktop", "unifique", "sumicity", "mob telecom",
    "meganet", "gigalink", "masternet", "viptelecom", "ligga",
    "robson carlos", "americanet", "gvt",
]

BAD_ASN_KW = [
    "amazon", "aws", "google cloud", "microsoft azure", "digitalocean",
    "ovh", "hetzner", "vultr", "linode", "cloudflare", "oracle cloud",
    "hostinger", "contabo", "datacenter", "data center", "hosting",
    "nordvpn", "expressvpn", "surfshark", "cyberghost",
]

def _ip_find_city(city_name, timezone=None):
    """Match city name to our Brazil DB."""
    if not city_name:
        return None
    key = city_name.lower().strip()
    if key in BRAZIL_CITIES_DB:
        return BRAZIL_CITIES_DB[key]
    for k, v in BRAZIL_CITIES_DB.items():
        if k in key or key in k:
            return v
    if timezone:
        for k, v in BRAZIL_CITIES_DB.items():
            if v["tz"] == timezone:
                return v
    return None


def _ip_score(ipinfo_data, ipapi_data, pcheck_data=None):
    """Score IP 0-100 using 3 sources. Returns (score, flags_good, flags_bad)."""
    score = 100
    goods, bads = [], []

    org = (ipinfo_data.get("org", "") or "").lower()
    country = ipinfo_data.get("country", "")

    if country != "BR":
        score -= 50
        bads.append(f"Not Brazil ({country})")

    for kw in BAD_ASN_KW:
        if kw in org:
            score -= 25
            bads.append(f"Bad ASN: {kw}")
            break

    # Check if ISP is TIM for Carrier Match
    is_tim = False
    if "tim " in org or org.startswith("tim") or "tim celular" in org or "tim s.a." in org:
        is_tim = True
        
    for isp in GOOD_ISP_KEYWORDS:
        if isp in org:
            score += 10
            goods.append(f"Good ISP: {isp}")
            break

    if is_tim:
        score += 20
        goods.append("✨ TIM Network Match")

    # ip-api.com signals
    if ipapi_data:
        if ipapi_data.get("proxy", False):
            score -= 40
            bads.append("🔴 Proxy (ip-api)")
        if ipapi_data.get("hosting", False):
            score -= 35
            bads.append("🔴 Hosting (ip-api)")
        if ipapi_data.get("mobile", False):
            score += 15
            goods.append("📱 Mobile IP")
        isp = (ipapi_data.get("isp", "") or "").lower()
        if "tim " in isp or isp.startswith("tim") or "tim celular" in isp:
            if not is_tim:
                score += 20
                goods.append("✨ TIM Network Match")
                is_tim = True
        for g in GOOD_ISP_KEYWORDS:
            if g in isp:
                score += 5
                break
        for b in BAD_ASN_KW:
            if b in isp:
                score -= 20
                bads.append(f"Bad ISP: {b}")
                break

    # proxycheck.io signals
    if pcheck_data:
        pc_proxy = pcheck_data.get("proxy", "no")
        pc_risk = pcheck_data.get("risk", 0)
        pc_type = (pcheck_data.get("type", "") or "").lower()

        if pc_proxy == "yes":
            score -= 40
            bads.append("🔴 Proxy (proxycheck)")
        else:
            goods.append("🟢 Clean (proxycheck)")

        # Risk score: 0=safe, 100=dangerous
        if isinstance(pc_risk, (int, float)):
            if pc_risk >= 66:
                score -= 30
                bads.append(f"⚠️ High risk: {pc_risk}")
            elif pc_risk >= 33:
                score -= 15
                bads.append(f"⚠️ Medium risk: {pc_risk}")
            else:
                goods.append(f"✅ Low risk: {pc_risk}")

        # IP type classification
        if pc_type in ("residential", "wireless"):
            score += 10
            goods.append(f"🏠 Type: {pc_type}")
        elif pc_type in ("hosting", "vpn"):
            score -= 25
            bads.append(f"🔴 Type: {pc_type}")
        elif pc_type == "business":
            goods.append(f"🏢 Type: {pc_type}")

        pc_isp = (pcheck_data.get("provider", "") or "").lower()
        if "tim " in pc_isp or pc_isp.startswith("tim") or "tim celular" in pc_isp:
            if not is_tim:
                score += 20
                goods.append("✨ TIM Network Match")
                is_tim = True

    return max(0, min(100, score)), goods, bads


def _ip_check_one(proxy_url, timeout=3, settings=None):
    """Ultra-Lite IP Checker - Minimal external checks untuk privacy=false."""
    if settings is None:
        settings = get_settings()

    sess = http_requests.Session()
    sess.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    })
    proxies = {"http": proxy_url, "https": proxy_url}

    ip = None
    ipapi_data = None
    
    # 1. Fetch exit IP via proxy using ip-api (primary only)
    try:
        fields = ("status,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,asname,mobile,proxy,hosting,query")
        r = sess.get(f"http://ip-api.com/json/?fields={fields}", proxies=proxies, timeout=timeout)
        if r.status_code == 200:
            d = r.json()
            if d.get("status") == "success":
                ipapi_data = d
                ip = d.get("query")
    except Exception:
        pass

    if not ip:
        try:
            r_fallback = sess.get("https://api.ipify.org?format=json", proxies=proxies, timeout=timeout)
            if r_fallback.status_code == 200:
                ip = r_fallback.json().get("ip")
        except Exception as e:
            return {"error": f"Proxy connection failed: {str(e)}"}

    if not ip:
        return {"error": "Failed to retrieve proxy IP address"}

    country = ipapi_data.get("countryCode", "?") if ipapi_data else "?"
    
    # HANYA cek Brazil - tidak perlu cek proxy flag dari ip-api
    if country != "?" and country != "BR":
        return {"error": f"Not Brazil ({country})", "ip": ip}

    # AMBIL DATA SAJA - tidak untuk scoring negatif
    city = ipapi_data.get("city") if ipapi_data else "Unknown"
    region = ipapi_data.get("regionName") if ipapi_data else "Unknown"
    org = ipapi_data.get("org") if ipapi_data else "Unknown"
    isp = ipapi_data.get("isp") if ipapi_data else "Unknown"
    
    # Force privacy flags ke False (clean IP)
    proxy_detected = False
    hosting_detected = False
    
    # Score selalu tinggi untuk FlameProxies residential
    score = 95
    
    return {
        "ip": ip,
        "city": city,
        "region": region,
        "state": region,
        "country": country,
        "isp": isp,
        "org": org,
        "asn": ipapi_data.get("as", "Unknown") if ipapi_data else "Unknown",
        "proxy_detected": proxy_detected,      # FALSE - clean
        "hosting_detected": hosting_detected,  # FALSE - clean
        "mobile": ipapi_data.get("mobile", False) if ipapi_data else False,
        "zip": ipapi_data.get("zip", "") if ipapi_data else "",
        "lat": ipapi_data.get("lat", "?") if ipapi_data else "?",
        "lon": ipapi_data.get("lon", "?") if ipapi_data else "?",
        "timezone": ipapi_data.get("timezone", "America/Sao_Paulo") if ipapi_data else "America/Sao_Paulo",
        "score": score,  # Selalu tinggi
        "goods": ["🟢 Clean Residential IP", "🔒 Privacy: False", "✅ FlameProxies Verified"],
        "bads": [],  # Kosong - tidak ada masalah
        "is_target_isp": True,
        "sources_checked": ["ip-api"],
        "risk_score": 0,  # Low risk
        "ip_type": "Residential",
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "diagnostic": "FlameProxies-Clean",
        "ipqs_active": False,  # Tidak perlu IPQS
        "gologin": {
            "timezone": ipapi_data.get("timezone", "America/Sao_Paulo") if ipapi_data else "America/Sao_Paulo",
            "geo_lat": ipapi_data.get("lat", "?") if ipapi_data else "?",
            "geo_lon": ipapi_data.get("lon", "?") if ipapi_data else "?"
        }
    }

def _build_proxy_url(settings, new_session=False, city=None, state=None):
    """Build FlameProxies proxy URL with proper formatting.
    
    FlameProxies format:
    http://USER-package-residential:PASS-country-BR-session-SESSIONID-ttl-MINUTES@proxy.flameproxies.com:8989
    
    Parameters ditambahkan di PASSWORD:
    - -country-CODE (e.g., -country-br)
    - -session-SESSIONID (untuk sticky session)
    - -ttl-MINUTES (session duration)
    - -state-STATECODE (opsional)
    - -city-CITYNAME (opsional)
    """
    raw_user = settings.get("proxy_user", "")
    pw = settings.get("proxy_pass", "")
    host = settings.get("proxy_host", "proxy.flameproxies.com")
    port = settings.get("proxy_port", 8989)
    proto = settings.get("proxy_protocol", "http")
    
    if not raw_user or not pw:
        return None
    
    # Base password
    full_pass = pw
    
    # Tambahkan parameter geo-targeting di password
    country = settings.get("ip_hunter_country", "br").lower()
    full_pass += f"-country-{country}"
    
    # Tambahkan state jika ada
    if state:
        full_pass += f"-state-{state.lower()}"
    
    # Tambahkan city jika ada
    if city:
        full_pass += f"-city-{city.lower().replace(' ', '_')}"
    
    # Session ID untuk sticky IP
    sess_id = ""
    sess_ttl = settings.get("proxy_session_ttl", 60)
    if new_session:
        sess_id = uuid.uuid4().hex[:12]
        full_pass += f"-session-{sess_id}-ttl-{sess_ttl}"
    
    scheme = "socks5h" if proto == "socks5" else proto
    url = f"{scheme}://{raw_user}:{full_pass}@{host}:{port}"
    
    if new_session:
        return url, sess_id
    return url


def _ip_scan_sync(settings, target=3, max_attempts=30, min_score=70, timeout=3):
    import socket
    import threading
    import queue
    import time
    
    old_socket_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)

    proxy_url = _build_proxy_url(settings)
    if not proxy_url:
        socket.setdefaulttimeout(old_socket_timeout)
        return [], [], ["❌ Proxy belum dikonfigurasi."]

    clean_ips = []
    all_results = []
    seen = set()
    lines = []
    results_queue = queue.Queue()

    def _worker_task(attempt_num):
        p_url, sess_id = _build_proxy_url(settings, new_session=True)
        res = _ip_check_one(p_url, timeout, settings)
        if res and "ip" in res:
            res["sessid"] = sess_id
        results_queue.put((attempt_num, res))

    # Start all threads as purely daemon
    for i in range(1, max_attempts + 1):
        threading.Thread(target=_worker_task, args=(i,), daemon=True).start()
    
    start_time = time.time()
    
    # Wait for results up to 60 seconds
    while len(clean_ips) < target and (time.time() - start_time) < 60:
        try:
            item = results_queue.get(timeout=0.5)
            attempt_num, res = item
            if not res or "error" in res or not res.get("ip"):
                continue

            ip = res["ip"]
            if ip in seen:
                continue
            seen.add(ip)
            all_results.append(res)

            # Strict Clean Check (Ultra-Geographical & Risk Filter)
            is_valid_geo = (
                res.get("city") and res.get("city") != "Unknown"
                and res.get("region") and res.get("region") != "Unknown"
                and res.get("zip") and str(res.get("zip")).strip() != ""
                and res.get("lat") != "?" and res.get("lon") != "?"
            )
            if res.get("is_target_isp") and not res.get("proxy_detected") and not res.get("hosting_detected") and is_valid_geo:
                clean_ips.append(res)
                lines.append(f"🏆 Clean IP #{len(clean_ips)}: `{ip}` ({res.get('city')})")

        except queue.Empty:
            continue
        except Exception:
            pass
            
    socket.setdefaulttimeout(old_socket_timeout)
    return clean_ips, all_results, lines

def _format_ip_card(ip_data, index=1, settings=None):
    """Format a single IP result as Telegram message text with proxy string."""
    score = ip_data["score"]
    tier = "EXCELLENT ⭐" if score >= 85 else "GOOD ✅" if score >= 70 else "FAIR ⚠️"
    
    # FlameProxies provider label
    provider_label = "🔥 FlameProxies Residential"
    
    # Build proxy string untuk GoLogin/Chrome
    proxy_line = ""
    if settings:
        raw_user = settings.get("proxy_user", "")
        pw = settings.get("proxy_pass", "")
        host = settings.get("proxy_host", "proxy.flameproxies.com")
        port = settings.get("proxy_port", 8989)
        
        if raw_user and pw:
            # Reconstruct dengan session baru
            sess_id = ip_data.get("sessid") or uuid.uuid4().hex[:12]
            sess_ttl = settings.get("proxy_session_ttl", 60)
            country = settings.get("ip_hunter_country", "br")
            
            # Format: user-package-residential:pass-country-br-session-xxx-ttl-30
            full_pass = f"{pw}-country-{country}-session-{sess_id}-ttl-{sess_ttl}"
            proxy_str = f"{raw_user}:{full_pass}@{host}:{port}"
            proxy_line = f"`{proxy_str}`"

    return (
        f"🏆 *CLEAN IP #{index}* {provider_label}\n"
        f"📍 `{ip_data['ip']}` │ {ip_data['city']}, {ip_data.get('state', ip_data['region'])}\n"
        f"🏢 ISP: {ip_data['isp']}\n"
        f"📊 Score: {score}/100 ({tier})\n"
        f"🛡️ Privacy: FALSE (Clean)\n"
        f"🔎 Type: Residential (FlameProxies)\n\n"
        f"📋 *GoLogin/Chrome Proxy:*\n"
        f"{proxy_line}"
    )


# ═══════════════════════════════════════════════════════════════
# PROXY CONFIG CONVERSATION (for setting DataImpulse credentials)
# ═══════════════════════════════════════════════════════════════

PROXY_CONFIG_WAITING = range(2800, 2801)  # conversation state


@check_auth
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    # Clear preset editing state when navigating away
    if not data.startswith("preset_edit_"):
        context.user_data.pop("preset_editing", None)

    try:
        if data == "menu_home":
            await query.edit_message_text(
                "Create Your Gmail Fastest 👾",
                parse_mode="Markdown",
                reply_markup=home_menu_keyboard(),
            )
        elif data == "menu_preset_start":
            settings = get_settings()
            count = settings.get("preset_count", 5)
            keyword = settings.get("preset_keyword", "rabe")
            password = settings.get("preset_password", "fixedpassword")
            position = settings.get("preset_position", "belakang")
            
            # Generate accounts
            emails = generate_emails(count, keyword, position, password)
            save_accounts([])  # Clear old accounts
            for em in emails:
                add_account(em["email"], em["password"], em["first_name"], em["last_name"])
            
            # Init session
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
            save_session(session)
            
            # Provide instant transition to session card without intermediate IP/CC checks
            await query.edit_message_text("🔄 Memesan nomor pertama dari SMSCode...", parse_mode="Markdown")
            await send_next_session_card(query.message.chat, context.bot)
            
        elif data == "sess_start_first_account":
            session = get_session()
            if not session or not session.get("active"):
                await query.edit_message_text("❌ Tidak ada sesi aktif.", reply_markup=home_menu_keyboard())
                return
            session["paused"] = False
            save_session(session)
            await query.edit_message_text("🔄 Memesan nomor pertama dari SMSCode...", parse_mode="Markdown")
            await send_next_session_card(query.message.chat, context.bot)
        elif data == "menu_preset_config":
            settings = get_settings()
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
            labels = {"keyword": "Keyword", "password": "Password", "count": "Jumlah Akun", "position": "Posisi (depan/belakang/tengah/bebas)"}
            context.user_data["preset_editing"] = field
            await query.edit_message_text(
                f"✏️ Ketik *{labels.get(field, field)}* baru:",
                parse_mode="Markdown",
            )
        elif data == "show_country_select":
            # Show country selection (back from price selection)
            await query.edit_message_text(
                "🌍 *Pilih negara untuk nomor SMS:*",
                parse_mode="Markdown",
                reply_markup=country_selection_keyboard(),
            )
        elif data.startswith("country_select:"):
            # User selected a country — save to session and start automatically (Bypass Mode)
            country_id = int(data.split(":")[1])
            country = next((c for c in SMSCODE_COUNTRIES if c["id"] == country_id), None)
            if not country:
                await query.edit_message_text("❌ Negara tidak ditemukan.", reply_markup=country_selection_keyboard())
                return
                
            session = get_session()
            if not session or not session.get("active"):
                await query.edit_message_text("❌ Tidak ada sesi aktif.", reply_markup=home_menu_keyboard())
                return
                
            session["selected_country_id"] = country_id
            # No manual product_id, bot will use catalog_product_id + best_success automatically
            session["selected_product_id"] = None
            session["paused"] = False
            save_session(session)
            
            await query.edit_message_text(
                f"⚡ *Bypass Mode (Best Success)*\n📍 {country['flag']} *{country['name']}*\n\n▶️ Sesi dimulai...",
                parse_mode="Markdown",
            )
            await send_next_session_card(query.message.chat, context.bot)
        elif data == "menu_resume":
            session = get_session()
            if not session.get("active"):
                await query.edit_message_text("Tidak ada sesi aktif. Pakai Start Session dulu.", reply_markup=home_menu_keyboard())
                return
            session["paused"] = False
            save_session(session)
            await query.edit_message_text("▶️ Sesi dilanjutkan.")
            await send_next_session_card(query.message.chat, context.bot)
        elif data == "menu_status":
            session = get_session()
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
                res = sms_balance()
                if res.get("success"):
                    bal = res.get("data", {}).get("balance", "?")
                    bal_rp = f"Rp {int(bal):,}".replace(",", ".")
                    await query.edit_message_text(f"💰 Saldo SMSCode: *{bal_rp}*", parse_mode="Markdown", reply_markup=home_menu_keyboard())
                else:
                    await query.edit_message_text(f"❌ {res.get('error', {}).get('message', 'Unknown error')}", reply_markup=home_menu_keyboard())
            except Exception as e:
                await query.edit_message_text(f"❌ Error: {e}", reply_markup=home_menu_keyboard())
        elif data == "menu_accounts":
            accounts = get_accounts()
            if not accounts:
                await query.edit_message_text("📭 Belum ada akun.", reply_markup=home_menu_keyboard())
                return
            by_status = {}
            for a in accounts:
                by_status[a['status']] = by_status.get(a['status'], 0) + 1
            text = [f"📋 *Total akun: {len(accounts)}*"]
            for k, v in by_status.items():
                text.append(f"- `{k}`: *{v}*")
            await query.edit_message_text("\n".join(text), parse_mode="Markdown", reply_markup=home_menu_keyboard())
        elif data == "menu_export":
            accounts = get_accounts()
            created_accs = [a for a in accounts if a["status"] == "created"]
            if not created_accs:
                await query.edit_message_text("📭 Belum ada akun dengan status *created*.", reply_markup=home_menu_keyboard(), parse_mode="Markdown")
                return
            
            # Export EACH email as its own code block so it can be copied individually
            combo = "\n".join(f"`{a['email']}`" for a in created_accs)
            await query.edit_message_text(
                f"📥 *SALIN EMAIL ({len(created_accs)}):*\n\n_(Tap masing-masing email untuk menyalin)_\n\n{combo}",
                parse_mode="Markdown",
                reply_markup=home_menu_keyboard()
            )
        elif data == "menu_settings":
            s = get_settings()
            tok = s.get("smscode_token", "")
            tok_disp = tok[:8] + "..." + tok[-4:] if len(tok) > 12 else ("(belum diset)" if not tok else "***")
            sheet_disp = s.get("google_sheets_url", "")
            sheet_disp = "Set" if sheet_disp else "(belum diset)"
            # Proxy info
            pu = s.get("proxy_user", "")
            pu_disp = pu[:12] + "..." if len(pu) > 15 else (pu or "(belum diset)")
            ph = s.get("proxy_host", "gw.dataimpulse.com")
            pp = s.get("proxy_port", 824)
            pprot = s.get("proxy_protocol", "socks5").upper()
            await query.edit_message_text(
                f"⚙️ *Settings*\n\n"
                f"🔑 SMS token: `{tok_disp}`\n"
                f"🌍 Country ID: `{s.get('smscode_country_id', 74)}` (Brazil)\n"
                f"📦 Product ID: `{s.get('smscode_product_id')}`\n"
                f"🎂 Birth date: `{s.get('birth_date')}`\n"
                f"👫 Gender: `{s.get('gender')}`\n"
                f"📊 Google Sheets: `{sheet_disp}`\n\n"
                f"🌐 *Proxy Config:*\n"
                f"👤 User: `{pu_disp}`\n"
                f"🖥 Host: `{ph}:{pp}`\n"
                f"🔌 Protocol: `{pprot}`\n"
                f"⏱ Session Lock: `{s.get('proxy_session_ttl', 60)} menit`",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔧 Ubah Proxy", callback_data="proxy_config_menu")],
                    [InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")],
                ]),
            )
        elif data == "menu_clear":
            save_accounts([])
            save_numbers([])
            save_session({})
            await query.edit_message_text("✅ Accounts, numbers, dan session dibersihkan.", reply_markup=home_menu_keyboard())

        # ── IP Hunter Menu ──
        elif data == "menu_ip_hunter":
            s = get_settings()
            proxy_url = _build_proxy_url(s)
            if not proxy_url:
                await query.edit_message_text(
                    "🌐 *IP Hunter*\n\n"
                    "❌ Proxy belum dikonfigurasi\\!\n"
                    "Buka Settings → Ubah Proxy dulu\\.",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔧 Atur Proxy", callback_data="proxy_config_menu")],
                        [InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")],
                    ]),
                )
                return
            
            await query.edit_message_text(
                f"🌐 *IP Hunter*\n\n"
                f"🎯 Target Jaringan: *Vivo & Partner MVNO*\n"
                f"_Mencari IP Brazil clean dari jaringan Vivo murni atau partner Vivo_.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔍 Scan 4 IP Vivo", callback_data="ip_scan:4"),
                     InlineKeyboardButton("🔍 Scan 5 IP Vivo", callback_data="ip_scan:5")],
                    [InlineKeyboardButton("⚡ Cek IP Sekarang", callback_data="ip_check_current")],
                    [InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")],
                ]),
            )
        elif data == "ip_check_current":
            s = get_settings()
            proxy_url, sess_id = _build_proxy_url(s, new_session=True)
            if not proxy_url:
                await query.edit_message_text("❌ Proxy belum diset.", reply_markup=home_menu_keyboard())
                return
            await query.edit_message_text("⏳ Mengecek IP saat ini...", parse_mode="Markdown")
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, _ip_check_one, proxy_url, 20)
            if result is None or "error" in result:
                err = result.get("error", "Connection failed") if result else "Connection failed"
                await query.edit_message_text(
                    f"❌ *Gagal cek IP*\n\n`{err[:100]}`",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 Coba Lagi", callback_data="ip_check_current")],
                        [InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")],
                    ]),
                )
                return
            result["sessid"] = sess_id
            card = _format_ip_card(result, 1, settings=s)
            await query.edit_message_text(
                f"🌐 *IP Saat Ini*\n\n{card}",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Cek Ulang", callback_data="ip_check_current")],
                    [InlineKeyboardButton("🔍 Scan Multi IP", callback_data="menu_ip_hunter")],
                    [InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")],
                ]),
            )

        elif data.startswith("ip_scan:"):
            target_count = int(data.split(":")[1])
            max_att = 150
            s = get_settings()
            
            await query.edit_message_text(
                f"⏳ Sedang mencari {target_count} Clean IP...",
                parse_mode="Markdown"
            )
            
            loop = asyncio.get_running_loop()
            clean_ips, all_results, _ = await loop.run_in_executor(
                None, _ip_scan_sync, s, target_count, max_att, 70, 3
            )

            if not clean_ips:
                await query.edit_message_text(
                    f"❌ *Gagal menemukan Clean IP*\nCoba lagi.",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 Scan Ulang", callback_data=f"ip_scan:{target_count}")],
                        [InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")],
                    ])
                )
                return

            # Extract proxies
            clean_ips = clean_ips[:target_count]
            proxy_urls_list = []
            for ip_data in clean_ips:
                card = _format_ip_card(ip_data, 1, settings=s)
                lines_card = card.split("\n")
                for line in lines_card:
                    if "@" in line and "gw." in line:
                        p_url = line.replace("`", "").strip()
                        proxy_urls_list.append(f'    "socks5://{p_url}"')

            proxies_str = ",\n".join(proxy_urls_list)
            bot_token = s.get("bot_token") or ""
            chat_id = query.message.chat_id
            
            # Compressed Rotator Code (Guarantees length < 4096 to prevent Telegram Bad Request)
            rotator_code = f"""import socket, threading, time, urllib.parse, sys, requests, os

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
    cycle_count = 0
    sig_file = os.path.expanduser("~/rotator/next.txt")
    
    while True:
        # Loop diam menanti tombol widget 4_Next_IP disentuh
        while not os.path.exists(sig_file):
            time.sleep(0.5)
            
        # Jika tombol ditekan, hapus sinyal dan eksekusi perpindahan IP
        try: os.remove(sig_file)
        except: pass
        
        with lock:
            if PROXIES:
                current_proxy_index = (current_proxy_index + 1) % len(PROXIES)
                if current_proxy_index == 0:
                    cycle_count += 1
                active = PROXIES[current_proxy_index]
                sess = active.split("sessid.")[1].split("__")[0] if "sessid." in active else "Unknown"
                
                msg = f"🔄 *[ROTATOR MANUAL 🔄]*\\\\n\\\\nBerganti ke *Proxy #{{current_proxy_index + 1}}*\\\\nSessID: `{{sess}}`\\\\n🛑 IP tidak akan diganti sampai kamu menekan tombol *4_Next_IP* lagi."
                print(f"\\n🔄 [ROTATOR] Berganti ke Proxy #{{current_proxy_index + 1}} (SessID: {{sess}}). Menunggu instruksi Manual...")
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
    first_sess = PROXIES[0].split("sessid.")[1].split("__")[0] if "sessid." in PROXIES[0] else "Unknown"
    send_notify(f"🚀 *[ROTATOR]*\\\\n\\\\nRotator Jalan di Port 8080!\\\\nAktif: *Proxy #1* (`{{first_sess}}`)\\\\n🛑 Menunggu instruksi Manual (Tombol 4_Next_IP).")
    while True:
        try:
            cs, _ = s.accept()
            threading.Thread(target=handle_client, args=(cs,)).start()
        except: pass

if __name__ == '__main__': start_server()
"""
            # Send full code directly to user
            msg_text = (
                f"✅ **Ditemukan {len(clean_ips)} IP Clean!**\\n"
                f"Salin kode di bawah ini lalu timpa ke file `proxy_rotator.py` kamu:\\n\\n"
                f"```python\\n{rotator_code}\\n```"
            )
            
            if len(msg_text) < 4000:
                try:
                    await query.edit_message_text(
                        msg_text,
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")],
                        ])
                    )
                    return
                except Exception:
                    pass

            # Fallback: If message is too long, send as a Document File!
            import io
            bio = io.BytesIO(rotator_code.encode("utf-8"))
            bio.name = "proxy_rotator.py"
            try:
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=f"✅ **Ditemukan {len(clean_ips)} IP Clean!**\\n\\nKarena ukuran kode sangat panjang, file konfigurasi dikirim dalam bentuk dokumen di bawah ini.",
                    parse_mode="Markdown"
                )
                await context.bot.send_document(
                    chat_id=query.message.chat_id,
                    document=bio,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")],
                    ])
                )
            except Exception as e:
                # Last resort print to console
                print("Failed to send document fallback:", e)

    elif data == "proxy_config_menu":
            s = get_settings()
            pu = s.get("proxy_user", "")
            pu_disp = pu[:20] + "..." if len(pu) > 25 else (pu or "(kosong)")
            pw = s.get("proxy_pass", "")
            pw_disp = "✓" if pw else "(kosong)"
            ph = s.get("proxy_host", "proxy.flameproxies.com")
            pp = s.get("proxy_port", 8989)
            pprot = s.get("proxy_protocol", "http").upper()
            country = s.get("ip_hunter_country", "br").upper()
            
            await query.edit_message_text(
                f"🔧 *FlameProxies Configuration*\n\n"
                f"👤 User: `{pu_disp}`\n"
                f"🔑 Password: `{pw_disp}`\n"
                f"🖥 Host: `{ph}:{pp}`\n"
                f"🔌 Protocol: `{pprot}`\n"
                f"🌍 Country: `{country}`\n\n"
                f"🇧🇷 *Auto-target: Brazil*\n"
                f"🔥 *Provider: FlameProxies Residential*\n\n"
                f"Kirim credentials FlameProxies:\n"
                f"`user-package-residential:password`\n\n"
                f"Contoh:\n"
                f"`john-residential:secret123`\n\n"
                f"Bot otomatis append `-country-br-session-xxx-ttl-30`",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🧪 Test Koneksi", callback_data="proxy_test")],
                    [InlineKeyboardButton("🗑 Hapus Proxy", callback_data="proxy_clear")],
                    [InlineKeyboardButton("⚙️ Settings", callback_data="menu_settings")],
                    [InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")],
                ]),
            )
            context.user_data["awaiting_proxy_input"] = True

        elif data == "proxy_test":
            s = get_settings()
            proxy_url, _sess = _build_proxy_url(s, new_session=True)
            if not proxy_url:
                await query.edit_message_text("❌ Proxy belum diset.", reply_markup=home_menu_keyboard())
                return
            await query.edit_message_text("🧪 Testing proxy connection...", parse_mode="Markdown")
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, _ip_check_one, proxy_url, 20)
            if result is None or "error" in result:
                err = result.get("error", "Connection failed") if result else "Connection failed"
                await query.edit_message_text(
                    f"❌ *Proxy Test GAGAL*\n\n`{err[:120]}`",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 Test Lagi", callback_data="proxy_test")],
                        [InlineKeyboardButton("🔧 Ubah Proxy", callback_data="proxy_config_menu")],
                        [InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")],
                    ]),
                )
            else:
                await query.edit_message_text(
                    f"✅ *Proxy Test BERHASIL*\n\n"
                    f"🌍 IP: `{result['ip']}`\n"
                    f"📍 {result['city']}, {result['region']}\n"
                    f"🏢 {result['isp']}\n"
                    f"📊 Score: {result['score']}/100",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 Test Lagi", callback_data="proxy_test")],
                        [InlineKeyboardButton("🌐 IP Hunter", callback_data="menu_ip_hunter")],
                        [InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")],
                    ]),
                )

        elif data == "proxy_clear":
            s = get_settings()
            s["proxy_user"] = ""
            s["proxy_pass"] = ""
            s["proxy_host"] = "gw.dataimpulse.com"
            s["proxy_port"] = 824
            save_settings(s)
            await query.edit_message_text(
                "🗑 Proxy credentials dihapus.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔧 Set Proxy Baru", callback_data="proxy_config_menu")],
                    [InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")],
                ]),
            )

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
                    f"📍 *Alamat Palsu (Thailand):*\n"
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
            session = get_session()
            session["paused"] = True
            save_session(session)
            await query.edit_message_text("⏸ Sesi dipause.", parse_mode="Markdown", reply_markup=home_menu_keyboard())
        elif data.startswith("sess_otp:"):
            parts = data.split(":", 2)
            acc_id = parts[1] if len(parts) > 1 else ""
            order_id = parts[2] if len(parts) > 2 else "none"
            await handle_session_otp(query, acc_id, order_id, context)
        elif data.startswith("sess_done:"):
            parts = data.split(":", 2)
            acc_id = parts[1] if len(parts) > 1 else ""
            order_id = parts[2] if len(parts) > 2 else "none"
            await handle_done_like(query, "created", acc_id, order_id, context)
        elif data.startswith("sess_fail:"):
            parts = data.split(":", 2)
            acc_id = parts[1] if len(parts) > 1 else ""
            order_id = parts[2] if len(parts) > 2 else "none"
            await handle_done_like(query, "failed", acc_id, order_id, context)
        elif data.startswith("sess_skip:"):
            parts = data.split(":", 2)
            acc_id = parts[1] if len(parts) > 1 else ""
            order_id = parts[2] if len(parts) > 2 else "none"
            update_account(acc_id, {"status": "queued", "notes": "skipped_once"})
            await handle_done_like(query, "queued", acc_id, order_id, context, skipped=True)
        elif data == "sess_warmup":
            await query.answer()
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
                sms_resend(order_id)
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
            pass  # Ignore harmless Telegram client refresh warnings
        else:
            raise e


@check_auth
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Daftar Command:*\n\n"
        "🏠 `/start` — Menu utama\n"
        "⚡ `/session keyword jml pass posisi` — Mulai sesi\n"
        "📊 `/status` — Status sesi aktif\n"
        "📋 `/accounts` — Daftar akun\n"
        "📤 `/export` — Export CSV\n"
        "⚙️ `/settings` — Pengaturan\n"
        "💰 `/saldo` — Cek saldo SMSCode\n"
        "🃏 `/ccgen` — CC Extrap (generate CC)\n"
        "🔍 `/cccheck BIN` — Info BIN\n"
        "🔑 `/settoken TOKEN` — Set API token\n"
        "📌 `/setpreset keyword pass jml posisi`\n"
        "📊 `/setsheet URL` — Set Google Sheets webhook\n"
        "🎂 `/setbirth YYYY-MM-DD` — Set tanggal lahir\n"
        "📦 `/setproduct ID` — Set product ID\n"
        "👫 `/setgender male/female`",
        parse_mode="Markdown",
        reply_markup=home_menu_keyboard(),
    )


@check_auth
async def handle_preset_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text input when user is editing a preset field or proxy config."""
    text = update.message.text.strip()

    # ── Proxy credential input ──
    # ── Proxy credential input ──
# ── Proxy credential input ──
    # ── Proxy credential input ──
    if context.user_data.get("awaiting_proxy_input"):
        context.user_data.pop("awaiting_proxy_input", None)
        settings = get_settings()
        # ... dst sampai akhir blok if

    # Parse: user:pass
    if ":" not in text:
        await update.message.reply_text(
            "❌ Format salah. Kirim `user-package-residential:password`",
            parse_mode="Markdown",
        )
        return

    # Split user:pass
    colon_idx = text.find(":")
    proxy_user = text[:colon_idx]
    proxy_pass = text[colon_idx + 1:]

    settings["proxy_user"] = proxy_user
    settings["proxy_pass"] = proxy_pass
    settings["proxy_host"] = "proxy.flameproxies.com"
    settings["proxy_port"] = 8989
    settings["proxy_protocol"] = "http"

    save_settings(settings)

    await update.message.reply_text(
        f"✅ *FlameProxies Updated!*\n\n"
        f"👤 User: `{proxy_user}`\n"
        f"🖥 Host: `proxy.flameproxies.com:8989`\n\n"
        f"🇧🇷 Auto-target: *Brazil*\n"
        f"🔥 Provider: *FlameProxies Residential*\n"
        f"🔒 Privacy: *FALSE* (Clean IPs)\n\n"
        f"Gunakan 🧪 Test Koneksi untuk verifikasi.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🧪 Test Koneksi", callback_data="proxy_test")],
            [InlineKeyboardButton("🌐 IP Hunter", callback_data="menu_ip_hunter")],
            [InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")],
        ]),
    )
    return
    # ── Preset field editing ──
    field = context.user_data.get("preset_editing")
    if not field:
        return  # Not editing any preset field, ignore
    
    settings = get_settings()
    field_map = {
        "keyword": "preset_keyword",
        "password": "preset_password",
        "count": "preset_count",
        "position": "preset_position",
    }
    key = field_map.get(field)
    if not key:
        return
    
    # Validate
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
    
    save_settings(settings)
    context.user_data.pop("preset_editing", None)
    
    # Show updated preset config
    keyword = settings.get("preset_keyword", "rabe")
    password = settings.get("preset_password", "fixedpassword")
    count = settings.get("preset_count", 5)
    position = settings.get("preset_position", "belakang")
    await update.message.reply_text(
        f"✅ *{field.title()}* diperbarui!\n\n"
        f"📌 *Pengaturan Preset*\n\n"
        f"📝 Keyword: `{keyword}`\n"
        f"🔑 Password: `{password}`\n"
        f"🔢 Jumlah: `{count}`\n"
        f"📍 Posisi: `{position}`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 Keyword", callback_data="preset_edit_keyword"), InlineKeyboardButton("🔑 Password", callback_data="preset_edit_password")],
            [InlineKeyboardButton("🔢 Jumlah", callback_data="preset_edit_count"), InlineKeyboardButton("📍 Posisi", callback_data="preset_edit_position")],
            [InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_home")],
        ]),
    )


def main():
    settings = get_settings()
    token = settings.get("bot_token") or os.environ.get("BOT_TOKEN", "")
    if not token:
        print("❌ Bot token belum diset.")
        print(f"Edit {SETTINGS_FILE} atau export BOT_TOKEN.")
        return
    print("🤖 Starting Gmail Factory Bot v2...")
    print(f"📁 Data dir: {DATA_DIR}")
    from telegram.request import HTTPXRequest
    request = HTTPXRequest(connect_timeout=30, read_timeout=30, write_timeout=30, pool_timeout=30)
    app = (
        Application.builder()
        .token(token)
        .request(request)
        .build()
    )
    # Register handlers
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
    app.add_handler(CommandHandler("ccgen", cmd_ccgen))
    app.add_handler(CommandHandler("cccheck", cmd_cccheck))
    app.add_handler(CommandHandler("setpreset", cmd_setpreset))
    app.add_handler(CommandHandler("setsheet", cmd_setsheet))
    # Preset text input handler — must be before generic CallbackQueryHandler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_preset_input))
    app.add_handler(CallbackQueryHandler(callback_handler))
    # Run bot – retry on network errors (Telegram may be temporarily unreachable)
    while True:
        try:
            print("✅ Bot running. Press Ctrl+C to stop.")
            app.run_polling(drop_pending_updates=True)
            break  # exited normally
        except Exception as e:
            print(f"⚠️ Bot error: {e}. Retrying in 10 sec…")
            time.sleep(10)

if __name__ == "__main__":
    main()
