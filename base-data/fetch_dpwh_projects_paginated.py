import os
import time
import json
import random
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import sys

try:
    # Prefer curl_cffi for Cloudflare-friendly TLS fingerprints if available
    from curl_cffi import requests as http
    CURL_CFFI = True
except Exception:
    import requests as http
    CURL_CFFI = False

BASE_DIR = os.path.dirname(__file__)
JSON_DIR = os.path.join(BASE_DIR, "json")
os.makedirs(JSON_DIR, exist_ok=True)
LISTS_DIR = os.path.join(BASE_DIR, "lists")
os.makedirs(LISTS_DIR, exist_ok=True)
SUCCESS_PATH = os.path.join(LISTS_DIR, "successful_pages.txt")
FAIL_PATH = os.path.join(LISTS_DIR, "failed_pages.txt")
PROGRESS_PATH = os.path.join(BASE_DIR, "progress_stats.json")

# Allow importing shared helpers from repo root when running from subdir.
REPO_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from impersonation_pool_manager import default_manager

API_BASE = "https://api.transparency.dpwh.gov.ph/projects"
LIMIT = 5000  # default max as requested; can override via CLI
TOTAL_CONTRACTS = 247187  # provided info
def compute_max_pages(limit: int) -> int:
    return (TOTAL_CONTRACTS + limit - 1) // limit

# Basic headers; when curl_cffi is used, UA is handled by impersonate
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://transparency.dpwh.gov.ph",
    "Referer": "https://transparency.dpwh.gov.ph/",
}

ACCEPT_LANGUAGES = [
    "en-US,en;q=0.9",
    "en-GB,en;q=0.9",
    "en-PH,en;q=0.9,tl;q=0.8",
    "fil-PH,fil;q=0.9,en;q=0.8",
    "en;q=0.9"
]

REFERERS = [
    "https://www.google.com/",
    "https://transparency.dpwh.gov.ph/",
    "https://www.dpwh.gov.ph/",
    ""
]

MIN_DELAY = 0.8
MAX_DELAY = 2.5
MAX_RETRIES = 4

# TLS fingerprint stats tracking
tls_stats = {}
tls_stats_lock = threading.Lock()

impersonation_manager = default_manager(REPO_ROOT)


def build_url(page: int, limit: int = LIMIT) -> str:
    return f"{API_BASE}?page={page}&limit={limit}"


def existing_pages(limit: int, prefix: str = "dump-page-") -> set:
    pages = set()
    for name in os.listdir(JSON_DIR):
        if name.startswith(prefix) and name.endswith(f"-{limit}.json"):
            try:
                num = int(name[len(prefix):].split("-")[0])
                pages.add(num)
            except Exception:
                pass
    # Also check successful_pages.txt
    if os.path.exists(SUCCESS_PATH):
        with open(SUCCESS_PATH, "r") as f:
            for line in f:
                try:
                    num = int(line.strip())
                    pages.add(num)
                except Exception:
                    pass
    return pages


def save_json(page: int, limit: int, data: dict) -> str:
    out = os.path.join(JSON_DIR, f"dump-page-{page}-{limit}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return out


def fetch_page(page: int, limit: int = LIMIT, retries: dict = None) -> Optional[dict]:
    url = build_url(page, limit)
    # rotate Accept-Language and Referer
    headers = dict(HEADERS)
    headers["Accept-Language"] = random.choice(ACCEPT_LANGUAGES)
    headers["Accept-Encoding"] = "gzip, deflate, br"
    headers["DNT"] = "1"
    headers["Connection"] = "keep-alive"
    headers["Sec-Fetch-Dest"] = "empty"
    headers["Sec-Fetch-Mode"] = "cors"
    headers["Sec-Fetch-Site"] = "same-site"
    
    # Rotate Referer
    referer = random.choice(REFERERS)
    if referer:
        headers["Referer"] = referer

    attempt = 0
    while attempt < MAX_RETRIES:
        attempt += 1
        delay = random.uniform(MIN_DELAY, MAX_DELAY)
        time.sleep(delay)
        kwargs = {"headers": headers, "timeout": 30}
        impersonate_choice = None
        if CURL_CFFI:
            pool = impersonation_manager.get_active_pool()
            if len(pool) == 0:
                print(f"[ERROR] Page {page}: No valid fingerprints remaining!")
                return None
            impersonate_choice = impersonation_manager.choose().fingerprint
            kwargs["impersonate"] = impersonate_choice
            print(f"[TLS] Page {page} attempt {attempt}/{MAX_RETRIES}: {impersonate_choice}")
            # Initialize TLS stats entry if not exists
            with tls_stats_lock:
                if impersonate_choice not in tls_stats:
                    tls_stats[impersonate_choice] = {"success": 0, "fail": 0, "block": 0, "exception": 0, "timeout": 0, "rate_limited": 0}
        try:
            resp = http.get(url, **kwargs)
            body_lower = resp.text.lower()
            is_cf_block = ("error 1015" in body_lower) or ("just a moment" in body_lower) or ("rate limited" in body_lower)
            
            if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("application/json") and not is_cf_block:
                if retries is not None:
                    retries[page] = attempt
                # Track TLS fingerprint success
                if impersonate_choice:
                    with tls_stats_lock:
                        tls_stats[impersonate_choice]["success"] += 1
                    impersonation_manager.report_success(impersonate_choice)
                return resp.json()
            
            # Handle rate limit/backoff
            if resp.status_code in (403, 429) or is_cf_block:
                print(f"[RETRY] Page {page} attempt {attempt}/{MAX_RETRIES}: Rate limit/block detected")
                if impersonate_choice:
                    with tls_stats_lock:
                        if is_cf_block:
                            tls_stats[impersonate_choice]["block"] += 1
                        else:
                            tls_stats[impersonate_choice]["rate_limited"] += 1
                    # Rate limit / Cloudflare blocks are usually not fingerprint-specific, so don't auto-disable.
                    impersonation_manager.report_failure(impersonate_choice, reason="block" if is_cf_block else "rate_limited")
                if retries is not None:
                    retries[page] = attempt
                time.sleep(5 * attempt)
                continue  # Retry
            
            # Other non-200 errors: save raw and retry
            print(f"[RETRY] Page {page} attempt {attempt}/{MAX_RETRIES}: HTTP {resp.status_code}")
            if impersonate_choice:
                with tls_stats_lock:
                    tls_stats[impersonate_choice]["fail"] += 1
                impersonation_manager.report_failure(impersonate_choice, reason=f"http_{resp.status_code}")
            if attempt == MAX_RETRIES:
                raw_path = os.path.join(LISTS_DIR, f"dump-page-{page}-{limit}-raw.txt")
                with open(raw_path, "w", encoding="utf-8") as f:
                    f.write(resp.text)
                if retries is not None:
                    retries[page] = MAX_RETRIES
                return None
            time.sleep(2 * attempt)
            continue  # Retry
            
        except Exception as e:
            error_msg = str(e).lower()
            
            # Check if fingerprint is not supported - blacklist immediately and DON'T count as retry
            if "not supported" in error_msg and impersonate_choice:
                print(f"[BLACKLIST] {impersonate_choice} is not supported - removing from pool")
                with tls_stats_lock:
                    tls_stats[impersonate_choice]["exception"] += 1
                impersonation_manager.report_failure(impersonate_choice, reason="not_supported")
                # Check if we have any fingerprints left
                if len(impersonation_manager.get_active_pool()) == 0:
                    print(f"[ERROR] No valid fingerprints remaining!")
                    return None
                # IMPORTANT: Don't count this against retry limit - decrement counter
                attempt -= 1
                time.sleep(0.5)  # Short delay before retrying
                continue  # Retry immediately with different fingerprint
            
            print(f"[RETRY] Page {page} attempt {attempt}/{MAX_RETRIES}: {str(e)[:100]}")
            if impersonate_choice:
                with tls_stats_lock:
                    tls_stats[impersonate_choice]["exception"] += 1
                    if "timeout" in error_msg:
                        tls_stats[impersonate_choice]["timeout"] += 1
                reason = "timeout" if "timeout" in error_msg else "exception"
                impersonation_manager.report_failure(impersonate_choice, reason=reason)
            if attempt == MAX_RETRIES:
                error_path = os.path.join(LISTS_DIR, f"dump-page-{page}-{limit}-error.txt")
                with open(error_path, "w", encoding="utf-8") as f:
                    f.write(str(e))
                if retries is not None:
                    retries[page] = MAX_RETRIES
                return None
            if retries is not None:
                retries[page] = attempt
            time.sleep(2 * attempt)
            continue  # Retry
            time.sleep(2 * attempt)
            continue  # Retry
    
    return None


def count_items(data):
    items = None
    if isinstance(data, dict):
        inner = data.get("data")
        if isinstance(inner, dict) and isinstance(inner.get("data"), list):
            items = inner.get("data")
        else:
            for key in ("data", "results", "items"):
                if isinstance(data.get(key), list):
                    items = data[key]
                    break
    if items is None and isinstance(data, list):
        items = data
    return items if items is not None else []

def fetch_and_save_concurrent(page, limit, done_pages, retries, lock, success_list, fail_list):
    if page in done_pages:
        print(f"[SKIP] Page {page} already saved")
        return 0
    print(f"[FETCH] Page {page} -> {build_url(page, limit)}")
    data = fetch_page(page, limit, retries)
    if not data:
        print(f"[FAIL] Page {page} failed after {retries.get(page, MAX_RETRIES)} attempts")
        with lock:
            fail_list.append(page)
            with open(FAIL_PATH, "a") as f:
                f.write(f"{page}\n")
        return 0
    items = count_items(data)
    count = len(items)
    save_json(page, limit, data)
    print(f"[SAVE] Page {page} count={count}")
    with lock:
        success_list.append(page)
        with open(SUCCESS_PATH, "a") as f:
            f.write(f"{page}\n")
    return count

def main(start_page: int = 1, end_page: Optional[int] = None, limit: int = LIMIT, max_workers: int = 10):
    start_time = time.time()
    if end_page is None:
        end_page = compute_max_pages(limit)
    done = existing_pages(limit)
    print(f"[INFO] Existing pages: {len(done)} found")
    total_items = 0
    pages = [p for p in range(start_page, end_page + 1) if p not in done]
    if not pages:
        print("[INFO] All pages already saved.")
        return
    success_list = []
    fail_list = []
    retries = {}
    lock = threading.Lock()
    def write_progress():
        progress = {
            "total": len(pages),
            "success": len(success_list),
            "fail": len(fail_list),
            "retries": retries,
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
        }
        # Add TLS stats
        with tls_stats_lock:
            progress["tls_stats"] = tls_stats.copy()
        with open(PROGRESS_PATH, "w") as f:
            json.dump(progress, f, indent=2)
    # Progress logger thread
    stop_flag = threading.Event()
    def progress_logger():
        while not stop_flag.is_set():
            write_progress()
            time.sleep(10)
    t = threading.Thread(target=progress_logger)
    t.daemon = True
    t.start()
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_page = {executor.submit(fetch_and_save_concurrent, page, limit, done, retries, lock, success_list, fail_list): page for page in pages}
        for future in as_completed(future_to_page):
            page = future_to_page[future]
            try:
                count = future.result()
                total_items += count
            except Exception as e:
                print(f"[ERROR] Page {page}: {e}")
    stop_flag.set()
    t.join()
    write_progress()
    elapsed = time.time() - start_time
    print(f"\n[INFO] Extraction complete. Elapsed time: {elapsed:.2f} seconds.")
    print(f"[STATS] Total pages attempted: {len(pages)}")
    print(f"[STATS] Success: {len(success_list)}")
    print(f"[STATS] Fail: {len(fail_list)}")
    print(f"[STATS] Total items: {total_items}")
    success_rate = (len(success_list) / len(pages) * 100) if pages else 0
    print(f"[STATS] Success rate: {success_rate:.2f}%")
    
    # TLS fingerprint stats summary
    if CURL_CFFI and tls_stats:
        print(f"\n[TLS FINGERPRINT STATS]")
        with tls_stats_lock:
            tls_copy = tls_stats.copy()
        never_success = []
        for fp, stats in sorted(tls_copy.items()):
            total = stats["success"] + stats["fail"] + stats["block"] + stats["exception"]
            if total > 0:
                success_pct = (stats["success"] / total * 100) if total else 0
                print(f"  {fp}: success={stats['success']}, fail={stats['fail']}, block={stats['block']}, exception={stats['exception']}, timeout={stats['timeout']}, rate_limited={stats['rate_limited']} ({success_pct:.1f}% success)")
                # Identify fingerprints that never succeeded
                if stats["success"] == 0 and total >= 2:  # At least 2 attempts with 0 success
                    never_success.append(fp)
        
        # Note: fingerprint demotion is handled persistently by the shared pool manager.
    
    print(f"[SUMMARY] Saved pages {start_page}-{end_page}; total_items ~ {total_items}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Fetch DPWH projects pages into base-data/json")
    parser.add_argument("--start", type=int, default=1, help="Start page (default: 1)")
    parser.add_argument("--end", type=int, default=None, help="End page (default: computed from total)")
    parser.add_argument("--limit", type=int, default=LIMIT, help="Items per page (default: 5000; API supports up to 5000)")
    parser.add_argument("--workers", type=int, default=10, help="Number of concurrent workers (default: 10)")
    args = parser.parse_args()
    main(start_page=args.start, end_page=args.end, limit=args.limit, max_workers=args.workers)
