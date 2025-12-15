import pandas as pd
import os
import json
import random
import time
import threading
from curl_cffi import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import sys

try:
    import duckdb
    DUCKDB_AVAILABLE = True
except Exception:
    duckdb = None
    DUCKDB_AVAILABLE = False

# TLS fingerprint pool for curl_cffi impersonate (expanded, filtered)
BASE_DIR = os.path.dirname(__file__)
# Root of repo (two levels up from this script: projects-data/extraction-script -> repo root)
REPO_ROOT = os.path.abspath(os.path.join(BASE_DIR, "..", ".."))
DATA_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))  # projects-data
OUTPUT_DIR = os.path.join(DATA_ROOT, "dpwh-projects-api")

# Allow importing shared helpers from repo root when running this script directly.
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from impersonation_pool_manager import default_manager

# Correct path to parquet dataset built from base-data JSON pages
PARQUET_PATH = os.path.join(REPO_ROOT, "base-data", "archive", "combined_dpwh_transparency_data.parquet")

# DuckDB configuration
DUCKDB_PATH = os.path.join(OUTPUT_DIR, "dpwh_projects.duckdb")
# When True, successful contract responses are written into DuckDB instead of per-ID JSON files.
USE_DUCKDB = True
# Optionally keep the old per-ID JSON files alongside DuckDB for debugging/backups.
WRITE_JSON_FILES = False

duckdb_conn = None
duckdb_lock = threading.Lock() if DUCKDB_AVAILABLE else None

impersonation_manager = default_manager(REPO_ROOT)

 # (Replaced above with absolute paths for robustness)
API_URL = "https://api.transparency.dpwh.gov.ph/projects/{}"
MAX_WORKERS = 50  # Concurrency - lower for better success rate
NUM_ENTRIES = 100  # Limit for testing
MAX_RETRIES = 3  # Reduced retries to fail faster on bad proxies

# Load proxies from free_proxies.json
with open(os.path.join(os.path.dirname(__file__), "free_proxies.json"), "r") as f:
    PROXIES = json.load(f)

# Global proxy blacklist (proxies that consistently fail)
BLACKLISTED_PROXIES = set()

# Optionally load additional paid/premium proxies from premium_proxies.json
try:
    premium_proxies_path = os.path.join(os.path.dirname(__file__), "premium_proxies.json")
    if os.path.exists(premium_proxies_path):
        with open(premium_proxies_path, "r") as f:
            premium_proxies = json.load(f)
            PROXIES.extend(premium_proxies)
            print(f"[INFO] Loaded {len(premium_proxies)} premium proxies")
except Exception as e:
    print(f"[WARNING] Could not load premium proxies: {e}")

# Optional: List of browser-exported cookies (as strings)
# COOKIES_LIST = [
#     'visid_incap_2383679=nGJV6iPpTWmFRJ4Kg2UTfgqL7mgAAAAAQkIPAAAAAACAcKHAAXDMpPmIX7fgHoN4SdL+29PLnMyJ;visid_incap_2383686=Whp2netdSt+H6M0YLK2my8UtE2kAAAAAQUIPAAAAAAB/qqvUwRRB7sRZwmS14/Rv;visid_incap_2749398=E9MB8/T/RWq/+yF5Cy8UBnxgEWkAAAAAQUIPAAAAAACxa+aScEP6uEgYsuO+MPXE;visid_incap_2759657=0avbES+aTyKJQqNuLvmYqmArE2kAAAAAQUIPAAAAAAAwNf0MDu/ce0l/XOZ0OoY1;',
#     # Add more cookie strings here for rotation
# ]
COOKIES_LIST = [] # Disabled to avoid fingerprinting via old cookies

# Variable delay range (seconds) - increased for better rate limit avoidance
MIN_DELAY = 1.8
MAX_DELAY = 4.0

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, "json"), exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, "raw"), exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, "lists"), exist_ok=True)

if not os.path.exists(PARQUET_PATH):
    raise FileNotFoundError(f"Parquet dataset not found at {PARQUET_PATH}")
df = pd.read_parquet(PARQUET_PATH)
contract_ids = df['contractId'].dropna().unique()

progress_log_path = os.path.join(OUTPUT_DIR, "progress_stats.json")


def init_duckdb():
    """
    Initialize DuckDB connection and target table.

    We purposely keep the schema minimal – a raw JSON column keyed by contractId –
    so we don't have to chase upstream schema changes. Downstream analytics can
    use DuckDB's JSON extension to work with the data.
    """
    global duckdb_conn
    if not DUCKDB_AVAILABLE or not USE_DUCKDB:
        return
    # Ensure output directory exists (already created above, but keep this safe)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    # Open connection once for the whole process
    duckdb_conn = duckdb.connect(DUCKDB_PATH)
    # Create table if it doesn't exist; contract_id is primary key so re-runs can upsert
    duckdb_conn.execute(
        """
        CREATE TABLE IF NOT EXISTS projects_raw (
            contract_id TEXT PRIMARY KEY,
            json TEXT
        )
        """
    )


# Accept-Language headers for rotation
ACCEPT_LANGUAGES = [
    "en-US,en;q=0.9",
    "en-GB,en;q=0.9",
    "en-PH,en;q=0.9,tl;q=0.8",
    "fil-PH,fil;q=0.9,en;q=0.8",
    "en;q=0.9"
]

# Referer options
REFERERS = [
    "https://www.google.com/",
    "https://transparency.dpwh.gov.ph/",
    "https://www.dpwh.gov.ph/",
    ""
]

stats = {
    "total": 0,
    "blocked": 0,
    "total_retries": 0,
    "success": 0,
    "fail": 0,
    "exception": 0,
    "timeout": 0,
    "curl_7": 0,
    "curl_35": 0,
    "curl_56": 0,
    "skipped_count": 0,
    "skipped_success_count": 0,
    "rate_limited_429": 0,
    "rate_limited_403": 0,
    # ID lists and details below
    "blocked_ids": [],
    "fail_ids": [],
    "exception_ids": [],
    "curl_7_ids": [],
    "curl_35_ids": [],
    "curl_56_ids": [],
    "skipped_proxies": [],
    "block_retries_per_id": {}  # New: Track retries per blocked ID
}

stats_lock = None
try:
    from threading import Lock
    stats_lock = Lock()
except ImportError:
    pass


proxy_stats = {proxy: {"success": 0, "fail": 0, "block": 0, "exception": 0, "timeout": 0, "curl_7": 0, "curl_35": 0, "curl_56": 0, "rate_limited": 0} for proxy in PROXIES}

# TLS fingerprint stats
tls_stats = {}
tls_error_types = ["success", "fail", "block", "exception", "timeout", "curl_7", "curl_35", "curl_56", "rate_limited"]


def _blacklist_impersonation(fp: str, *, reason: str) -> None:
    fp = (fp or "").strip()
    if not fp:
        return
    impersonation_manager.disable(fp, reason=reason)

# Global rate limit tracking for non-proxy requests
rate_limit_state = {
    "non_proxy_rate_limited": False,
    "last_rate_limit_time": 0,
    "last_non_proxy_check": 0,
    "non_proxy_check_interval": 300  # Check every 5 minutes (300 seconds)
}

# Function to write latest stats to progress log
def write_progress_log():
    log_data = {}
    if stats_lock:
        with stats_lock:
            log_data["stats"] = stats.copy()
    else:
        log_data["stats"] = stats.copy()
    # Add proxy stats
    log_data["proxy_stats"] = proxy_stats.copy()
    # Add TLS fingerprint stats
    log_data["tls_stats"] = tls_stats.copy()
    # Add rate limit state
    log_data["rate_limit_state"] = rate_limit_state.copy()
    log_data["timestamp"] = time.strftime('%Y-%m-%d %H:%M:%S')
    try:
        with open(progress_log_path, "w") as f:
            json.dump(log_data, f, indent=2)
    except Exception as e:
        print(f"[PROGRESS LOG ERROR] {e}")

# Background thread to update progress log every 10 seconds
class ProgressLogger(threading.Thread):
    def __init__(self, interval=5):
        super().__init__()
        self.interval = interval
        self.running = True
    def run(self):
        while self.running:
            write_progress_log()
            time.sleep(self.interval)
    def stop(self):
        self.running = False

# Load successful IDs once at startup for fast lookup
def load_ids_from_file(path):
    if not os.path.exists(path):
        return set()
    with open(path, "r") as f:
        return set(line.strip() for line in f if line.strip())

lists_dir = os.path.join(OUTPUT_DIR, "lists")
successful_ids_cache = load_ids_from_file(os.path.join(lists_dir, "successful_ids.txt"))
print(f"[INFO] Loaded {len(successful_ids_cache)} successful IDs from cache")

def fetch_and_save(cid):
    dropped_this_id = False
    url = API_URL.format(cid)
    out_path = os.path.join(OUTPUT_DIR, "json", f"{cid}.json")
    raw_path = os.path.join(OUTPUT_DIR, "raw", f"{cid}_raw.txt")

    # Skip if already successful (using cached set)
    if str(cid) in successful_ids_cache:
        print(f"[SKIP] {cid}: Already successful.")
        if stats_lock:
            with stats_lock:
                stats["skipped_success_count"] += 1
        else:
            stats["skipped_success_count"] += 1
        return
    print(f"[START] {cid}: {url}")
    blocked_this_id = False
    fail_this_id = False
    exception_this_id = False
    retries_for_id = 0
    # Track proxy timeouts
    if not hasattr(fetch_and_save, "proxy_timeouts"):
        fetch_and_save.proxy_timeouts = {}
    # Dynamic proxy usage based on timeout rate
    # Track error timestamps for proxies
    if not hasattr(fetch_and_save, "proxy_error_times"):
        fetch_and_save.proxy_error_times = {}
    # Track consecutive failures for proxies
    if not hasattr(fetch_and_save, "proxy_consecutive_failures"):
        fetch_and_save.proxy_consecutive_failures = {}
    # Track successful proxies
    if not hasattr(fetch_and_save, "proxy_successes"):
        fetch_and_save.proxy_successes = set()

    def get_valid_proxy():
        now = time.time()
        valid_proxies = []
        for proxy in PROXIES:
            # Skip blacklisted proxies
            if proxy in BLACKLISTED_PROXIES or proxy in stats["skipped_proxies"]:
                continue
            
            # Check consecutive failures
            failures = fetch_and_save.proxy_consecutive_failures.get(proxy, 0)
            if failures >= 2 and proxy not in fetch_and_save.proxy_successes:
                # If 2 consecutive failures and NO successes ever, blacklist it immediately
                BLACKLISTED_PROXIES.add(proxy)
                print(f"[PROXY BLACKLISTED] {proxy} - 2 consecutive failures, no successes")
                continue
            
            times = fetch_and_save.proxy_error_times.get(proxy, [])
            # Only count errors in last 30 seconds
            recent_errors = [t for t in times if now - t < 30]
            if len(recent_errors) <= 3:  # More strict
                valid_proxies.append(proxy)
        
        # Prioritize proxies with previous successes
        successful_proxies = [p for p in valid_proxies if p in fetch_and_save.proxy_successes]
        if successful_proxies:
            return random.choice(successful_proxies)
        return random.choice(valid_proxies) if valid_proxies else None

    for attempt in range(1, MAX_RETRIES + 1):
        now = time.time()
        req_headers = {}  # Initialize headers for this attempt
        
        # Rate limit logic: try non-proxy first, but switch to proxies if rate limited
        # Re-check non-proxy every 5 minutes
        if rate_limit_state["non_proxy_rate_limited"]:
            if now - rate_limit_state["last_non_proxy_check"] >= rate_limit_state["non_proxy_check_interval"]:
                # Time to re-check if rate limit is lifted
                print(f"[RATE LIMIT CHECK] {cid}: Testing non-proxy after {rate_limit_state['non_proxy_check_interval']}s cooldown")
                proxy = None
                rate_limit_state["last_non_proxy_check"] = now
            else:
                # Still rate limited, use proxy for ALL attempts
                proxy = get_valid_proxy()
                print(f"[PROXY MODE] {cid}: Using proxy (attempt {attempt}) due to rate limit state")
        else:
            # No rate limit detected yet
            # First 2 attempts: try without proxy (since different devices on same network work)
            # This suggests the rate limit is per-session/cookie, not per-IP
            if attempt <= 2:
                proxy = None
                print(f"[DIRECT] {cid}: Attempt {attempt} without proxy")
            else:
                # After 2 failures, use proxy
                proxy = get_valid_proxy()
                if proxy:
                    print(f"[PROXY] {cid}: Using proxy on attempt {attempt}")
                else:
                    print(f"[NO PROXY] {cid}: No valid proxies available, attempt {attempt}")
                    proxy = None
        
        delay = random.uniform(MIN_DELAY, MAX_DELAY)
        time.sleep(delay)
        
        # Cookie rotation
        if COOKIES_LIST:
            cookie_str = random.choice(COOKIES_LIST)
            req_headers["Cookie"] = cookie_str
        
        # User-Agent is handled by curl_cffi impersonate to match the TLS fingerprint
        # Do NOT manually set User-Agent here to avoid mismatches
        
        # Add more realistic headers
        req_headers["Accept"] = "application/json, text/plain, */*"
        req_headers["Accept-Language"] = random.choice(ACCEPT_LANGUAGES)
        req_headers["Accept-Encoding"] = "gzip, deflate, br"
        req_headers["DNT"] = "1"
        req_headers["Connection"] = "keep-alive"
        req_headers["Sec-Fetch-Dest"] = "empty"
        req_headers["Sec-Fetch-Mode"] = "cors"
        req_headers["Sec-Fetch-Site"] = "same-site"
        
        # Rotate Referer header
        referer = random.choice(REFERERS)
        if referer:
            req_headers["Referer"] = referer
        else:
            req_headers["Referer"] = "https://transparency.dpwh.gov.ph/"
        
        # Always add Origin
        req_headers["Origin"] = "https://transparency.dpwh.gov.ph"
        # Rotate impersonate (TLS fingerprint) for each request
        impersonate_choice = impersonation_manager.choose().fingerprint
        if impersonate_choice not in tls_stats:
            tls_stats[impersonate_choice] = {err: 0 for err in tls_error_types}
        try:
            resp = requests.get(
                url,
                headers=req_headers,
                impersonate=impersonate_choice,
                proxy=proxy,
                timeout=10 if proxy else 20,  # Reduced timeout for proxies to fail fast
                allow_redirects=True
            )
            print(f"[TLS] {cid}: Using impersonate={impersonate_choice}")

            # Monitor for Cloudflare rate limit (error 1015) in body, as well as status codes
            body_lower = resp.text.lower()
            is_cf_1015 = "error 1015" in body_lower or "you are being rate limited" in body_lower

            if resp.status_code == 429 or is_cf_1015:
                print(f"[RATE LIMIT] {cid}: Rate limit detected (HTTP {resp.status_code} or Cloudflare error 1015)")
                tls_stats[impersonate_choice]["rate_limited"] += 1
                if proxy:
                    proxy_stats[proxy]["rate_limited"] += 1
                else:
                    print(f"[RATE LIMIT] Non-proxy rate limited. Switching to proxies for future requests.")
                    rate_limit_state["non_proxy_rate_limited"] = True
                    rate_limit_state["last_rate_limit_time"] = time.time()
                    rate_limit_state["last_non_proxy_check"] = time.time()
                if stats_lock:
                    with stats_lock:
                        stats["rate_limited_429"] += 1
                else:
                    stats["rate_limited_429"] += 1
                time.sleep(random.uniform(30, 60))
                continue
            elif resp.status_code == 403:
                print(f"[RATE LIMIT 403] {cid}: Possible rate limit (403 Forbidden)")
                tls_stats[impersonate_choice]["rate_limited"] += 1
                if proxy:
                    proxy_stats[proxy]["rate_limited"] += 1
                else:
                    print(f"[RATE LIMIT] Non-proxy possibly rate limited (403). Switching to proxies.")
                    rate_limit_state["non_proxy_rate_limited"] = True
                    rate_limit_state["last_rate_limit_time"] = time.time()
                    rate_limit_state["last_non_proxy_check"] = time.time()
                if stats_lock:
                    with stats_lock:
                        stats["rate_limited_403"] += 1
                else:
                    stats["rate_limited_403"] += 1
                time.sleep(random.uniform(5, 10))
                continue

            if resp.status_code == 200 and resp.headers.get('content-type', '').startswith('application/json') and 'just a moment' not in body_lower and not is_cf_1015:
                # If non-proxy succeeded after being rate limited, reset flag
                if proxy is None and rate_limit_state["non_proxy_rate_limited"]:
                    print(f"[RATE LIMIT LIFTED] Non-proxy rate limit appears to be lifted.")
                    rate_limit_state["non_proxy_rate_limited"] = False
                # Persist successful response
                if DUCKDB_AVAILABLE and USE_DUCKDB and duckdb_conn is not None:
                    # Store raw JSON text keyed by contract_id; guarded by a lock for thread safety
                    if duckdb_lock is not None:
                        with duckdb_lock:
                            duckdb_conn.execute(
                                "INSERT OR REPLACE INTO projects_raw (contract_id, json) VALUES (?, ?)",
                                [str(cid), resp.text],
                            )
                    else:
                        duckdb_conn.execute(
                            "INSERT OR REPLACE INTO projects_raw (contract_id, json) VALUES (?, ?)",
                            [str(cid), resp.text],
                        )
                    print(f"[SUCCESS] {cid}: Saved JSON to DuckDB at {DUCKDB_PATH}")
                    # Optionally keep per-ID JSON files for debugging/backups
                    if WRITE_JSON_FILES:
                        with open(out_path, 'w', encoding='utf-8') as f:
                            f.write(resp.text)
                else:
                    # Fallback: preserve original per-ID JSON behavior
                    with open(out_path, 'w', encoding='utf-8') as f:
                        f.write(resp.text)
                    print(f"[SUCCESS] {cid}: Saved JSON to {out_path}")
                # TLS fingerprint success stat
                tls_stats[impersonate_choice]["success"] += 1
                impersonation_manager.report_success(impersonate_choice)
                # Append to successful log files and cache
                with open(os.path.join(lists_dir, "successful_ids.txt"), "a") as stxt:
                    stxt.write(f"{cid}\n")
                with open(os.path.join(lists_dir, "successful_ids.json"), "a") as sj:
                    sj.write(json.dumps(cid) + "\n")
                # Add to cache so other threads can skip it
                successful_ids_cache.add(str(cid))
                if proxy:
                    proxy_stats[proxy]["success"] += 1
                    fetch_and_save.proxy_successes.add(proxy)
                    fetch_and_save.proxy_consecutive_failures[proxy] = 0 # Reset failures
                if stats_lock:
                    with stats_lock:
                        stats["success"] += 1
                else:
                    stats["success"] += 1
                break
            elif 'Just a moment' in resp.text:
                print(f"[BLOCKED] {cid}: Cloudflare block detected (attempt {attempt}). Retrying after delay.")
                tls_stats[impersonate_choice]["block"] += 1
                impersonation_manager.report_failure(impersonate_choice, reason="block")
                blocked_this_id = True
                retries_for_id += 1
                if proxy:
                    proxy_stats[proxy]["block"] += 1
                if stats_lock:
                    with stats_lock:
                        stats["total_retries"] += 1
                else:
                    stats["total_retries"] += 1
                time.sleep(random.uniform(2, 5))  # Slightly longer delay after block
            else:
                print(f"[ERROR] {cid}: Non-JSON or error response (attempt {attempt}). Saving raw response to {raw_path}")
                with open(raw_path, 'w', encoding='utf-8') as f:
                    f.write(resp.text)
                # Detect impersonation-not-supported messages in response body and blacklist
                try:
                    body_lower = resp.text.lower()
                    if "impersonating" in body_lower and "not supported" in body_lower:
                        m = re.search(r"impersonating\s+([a-z0-9_]+)\s+is not supported", body_lower)
                        if m:
                            fp = m.group(1)
                            print(f"[BLACKLIST] Detected unsupported fingerprint: {fp}")
                            _blacklist_impersonation(fp, reason="not_supported")
                except Exception:
                    pass
                fail_this_id = True
                # TLS fingerprint error stats
                tls_stats[impersonate_choice]["fail"] += 1
                impersonation_manager.report_failure(impersonate_choice, reason="http_fail")
                # Exception/error types
                msg = resp.text.lower()
                if "exception" in msg:
                    tls_stats[impersonate_choice]["exception"] += 1
                if "timeout" in msg:
                    tls_stats[impersonate_choice]["timeout"] += 1
                if "curl: (7)" in msg:
                    tls_stats[impersonate_choice]["curl_7"] += 1
                if "curl: (35)" in msg:
                    tls_stats[impersonate_choice]["curl_35"] += 1
                if "curl: (56)" in msg:
                    tls_stats[impersonate_choice]["curl_56"] += 1
                if proxy:
                    proxy_stats[proxy]["fail"] += 1
                # Append to fail log files
                with open(os.path.join(lists_dir, "failed_ids.txt"), "a") as ftxt:
                    ftxt.write(f"{cid}\n")
                with open(os.path.join(lists_dir, "failed_ids.json"), "a") as fj:
                    fj.write(json.dumps(cid) + "\n")
                if stats_lock:
                    with stats_lock:
                        stats["fail"] += 1
                else:
                    stats["fail"] += 1
                break
        except Exception as e:
            print(f"[ERROR] {cid}: {e} (attempt {attempt}). Saving raw response to {raw_path}")
            with open(raw_path, 'w', encoding='utf-8') as f:
                f.write(str(e))
            exception_this_id = True
            msg = str(e).lower()
            # TLS fingerprint error stats
            tls_stats[impersonate_choice]["exception"] += 1
            # If exception message indicates unsupported impersonation, blacklist it
            try:
                msg = str(e).lower()
                if "not supported" in msg and "impersonating" in msg:
                    m = re.search(r"impersonating\s+([a-z0-9_]+)\s+is not supported", msg)
                    if m:
                        fp = m.group(1)
                        print(f"[BLACKLIST] Detected unsupported fingerprint from exception: {fp}")
                        _blacklist_impersonation(fp, reason="not_supported")
            except Exception:
                pass

            # Track continuous failures for this fingerprint (used to auto-demote across runs)
            try:
                reason = "exception"
                low = str(e).lower()
                if "curl: (35)" in low:
                    reason = "curl_35"
                elif "curl: (56)" in low:
                    reason = "curl_56"
                elif "curl: (7)" in low or "failed to connect" in low:
                    reason = "curl_7"
                elif "timeout" in low:
                    reason = "timeout"
                impersonation_manager.report_failure(impersonate_choice, reason=reason)
            except Exception:
                pass
            if "timeout" in msg:
                tls_stats[impersonate_choice]["timeout"] += 1
            if "curl: (7)" in msg:
                tls_stats[impersonate_choice]["curl_7"] += 1
            if "curl: (35)" in msg:
                tls_stats[impersonate_choice]["curl_35"] += 1
            if "curl: (56)" in msg:
                tls_stats[impersonate_choice]["curl_56"] += 1
            if proxy:
                proxy_stats[proxy]["exception"] += 1
                # Track consecutive failures
                fetch_and_save.proxy_consecutive_failures[proxy] = fetch_and_save.proxy_consecutive_failures.get(proxy, 0) + 1
                # Track error timestamps for proxy
                fetch_and_save.proxy_error_times.setdefault(proxy, []).append(time.time())
                
                # Immediate blacklist for connection errors (curl 7, 35, 56)
                if "curl: (7)" in msg or "curl: (35)" in msg or "curl: (56)" in msg or "failed to connect" in msg:
                    BLACKLISTED_PROXIES.add(proxy)
                    print(f"[PROXY BLACKLISTED] {proxy} - connection error: {msg[:50]}")
                
                if "timeout" in msg:
                    proxy_stats[proxy]["timeout"] += 1
                if "curl: (7)" in msg:
                    proxy_stats[proxy]["curl_7"] += 1
                if "curl: (35)" in msg:
                    proxy_stats[proxy]["curl_35"] += 1
                if "curl: (56)" in msg:
                    proxy_stats[proxy]["curl_56"] += 1
            if "timeout" in msg:
                if stats_lock:
                    with stats_lock:
                        stats["timeout"] += 1
                else:
                    stats["timeout"] += 1
            if "curl: (7)" in msg:
                if stats_lock:
                    with stats_lock:
                        stats["curl_7"] += 1
                        stats["curl_7_ids"].append(cid)
                else:
                    stats["curl_7"] += 1
                    stats["curl_7_ids"].append(cid)
            if "curl: (35)" in msg:
                if stats_lock:
                    with stats_lock:
                        stats["curl_35"] += 1
                        stats["curl_35_ids"].append(cid)
                else:
                    stats["curl_35"] += 1
                    stats["curl_35_ids"].append(cid)
            if "curl: (56)" in msg:
                if stats_lock:
                    with stats_lock:
                        stats["curl_56"] += 1
                        stats["curl_56_ids"].append(cid)
                else:
                    stats["curl_56"] += 1
                    stats["curl_56_ids"].append(cid)
            # Append to exception log files
            with open(os.path.join(lists_dir, "exception_ids.txt"), "a") as etxt:
                etxt.write(f"{cid}\n")
            with open(os.path.join(lists_dir, "exception_ids.json"), "a") as ej:
                ej.write(json.dumps(cid) + "\n")
            if stats_lock:
                with stats_lock:
                    stats["exception"] += 1
            else:
                stats["exception"] += 1
            break
        # If the request never succeeded, mark as dropped and log
        if not (fail_this_id or exception_this_id or blocked_this_id):
            # If it succeeded, do nothing
            pass
        elif fail_this_id or exception_this_id or (blocked_this_id and not (fail_this_id or exception_this_id)):
            dropped_this_id = True
            with open(os.path.join(lists_dir, "dropped_ids.txt"), "a") as dtxt:
                dtxt.write(f"{cid}\n")
            with open(os.path.join(lists_dir, "dropped_ids.json"), "a") as dj:
                dj.write(json.dumps(cid) + "\n")
    # Only log blocked ID if all retries failed and never succeeded
    if blocked_this_id and not (fail_this_id or exception_this_id or (stats_lock and stats["success"] > 0) or (not stats_lock and stats["success"] > 0)):
        with open(os.path.join(lists_dir, "blocked_ids.txt"), "a") as btxt:
            btxt.write(f"{cid}\n")
        with open(os.path.join(lists_dir, "blocked_ids.json"), "a") as bj:
            bj.write(json.dumps(cid) + "\n")
        if stats_lock:
            with stats_lock:
                stats["blocked"] += 1
                stats["blocked_ids"].append(cid)
                stats["block_retries_per_id"][cid] = retries_for_id
        else:
            stats["blocked"] += 1
            stats["blocked_ids"].append(cid)
            stats["block_retries_per_id"][cid] = retries_for_id
    if fail_this_id:
        if stats_lock:
            with stats_lock:
                stats["fail_ids"].append(cid)
        else:
            stats["fail_ids"].append(cid)
    if exception_this_id:
        if stats_lock:
            with stats_lock:
                stats["exception_ids"].append(cid)
        else:
            stats["exception_ids"].append(cid)
    
    # Always increment total at the end
    if stats_lock:
        with stats_lock:
            stats["total"] += 1
    else:
        stats["total"] += 1
    print(f"[FINISH] {cid}")

if __name__ == "__main__":
    start_time = time.time()
    print(f"[INFO] Starting extraction for {len(contract_ids)} contract IDs with {MAX_WORKERS} workers")
    print(f"[INFO] Rate limit state: {rate_limit_state['non_proxy_rate_limited']}")
    print(f"[INFO] Using {len(PROXIES)} proxies")
    from threading import Lock
    stats_lock = Lock()
    if DUCKDB_AVAILABLE and USE_DUCKDB:
        try:
            init_duckdb()
            print(f"[INFO] DuckDB enabled. Writing successful responses to {DUCKDB_PATH}")
        except Exception as e:
            # If DuckDB initialization fails, fall back to JSON files only
            print(f"[WARNING] Failed to initialize DuckDB at {DUCKDB_PATH}: {e}")
            print("[WARNING] Falling back to per-ID JSON files.")
    # Start progress logger thread
    progress_logger = ProgressLogger(interval=10)
    progress_logger.daemon = True
    progress_logger.start()
    try:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(fetch_and_save, cid) for cid in contract_ids]
            for future in as_completed(futures):
                pass  # All logging is handled in fetch_and_save
    finally:
        progress_logger.stop()
        progress_logger.join()
        # Write one last snapshot at the end
        write_progress_log()
    elapsed = time.time() - start_time
    print(f"[INFO] Extraction complete. Elapsed time: {elapsed:.2f} seconds.")
    print("[PROXY STATS]")
    for proxy, stat in proxy_stats.items():
        print(f"Proxy: {proxy}")
        print(f"  Success: {stat['success']}")
        print(f"  Fail: {stat['fail']}")
        print(f"  Block: {stat['block']}")
        print(f"  Exception: {stat['exception']}")
    print(f"[STATS] Total requests: {stats['total']}")
    print(f"[STATS] Success: {stats['success']}")
    print(f"[STATS] Fail: {stats['fail']}")
    print(f"[STATS] Exception: {stats['exception']}")
    print(f"[STATS] Blocked (at least once): {stats['blocked']}")
    print(f"[STATS] Total retries due to block: {stats['total_retries']}")
    block_rate = (stats['blocked'] / stats['total'] * 100) if stats['total'] else 0
    print(f"[STATS] Block rate: {block_rate:.2f}%")
    avg_retries = (stats['total_retries'] / stats['blocked']) if stats['blocked'] else 0
    print(f"[STATS] Average retries per blocked request: {avg_retries:.2f}")
    print(f"[STATS] Blocked IDs: {stats['blocked_ids']}")
    print(f"[STATS] Fail IDs: {stats['fail_ids']}")
    print(f"[STATS] Exception IDs: {stats['exception_ids']}")
    # New: Max block retries for a single ID
    if stats["block_retries_per_id"]:
        max_block = max(stats["block_retries_per_id"].values())
        max_block_ids = [cid for cid, val in stats["block_retries_per_id"].items() if val == max_block]
        print(f"[STATS] Max block retries for a single ID: {max_block}")
        print(f"[STATS] ID(s) with max block retries: {max_block_ids}")
    else:
        print(f"[STATS] No blocked IDs to report max block retries.")
