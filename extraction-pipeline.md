

### Overview

**Goal**: This repository implements a two‑stage extraction pipeline for the DPWH Transparency API:

1. **Base “projects list” extraction** (`base-data/`) — fetches paginated lists of projects.
2. **Per‑contract “project details” extraction** (`projects-data/`) — fetches detailed JSON for each `contractId`, using proxies and TLS fingerprinting for Cloudflare.

Downstream, JSON outputs are combined and transformed into Parquet for analysis.

---

### High‑Level Pipeline Flow

In logical order, the pipeline looks like this:

- **Step 1 – Base list extraction (paginated)**  
  `base-data/fetch_dpwh_projects_paginated.py`  
  → writes `base-data/json/dump-page-{page}-{limit}.json`  
  → maintains per‑page success/fail lists and TLS stats.

- **Step 2 – Combine paginated JSON into Parquet**  
  `archive/combine_json_to_parquet.py` (and related tooling)  
  → reads all `*.json` page files  
  → writes a combined Parquet dataset (flattened `location` fields).

- **Step 3 – Per‑contract detail extraction**  
  `projects-data/extraction-script/fetch_dpwh_projects_curlcffi.py`  
  → reads `contractId` values from a Parquet dataset  
  → fetches `https://api.transparency.dpwh.gov.ph/projects/{contractId}`  
  → writes per‑ID JSON + rich tracking/metrics under `projects-data/dpwh-projects-api/`.

- **Step 4 – Post‑processing & enrichment (current state)**  
  - Project JSON is optionally archived (`projects-json.tar.xz.*`).
  - Enriched Parquets (`dpwh_projects_enriched_flat.parquet`, `dpwh_projects_enriched_nested.parquet`) live in `projects-data/dpwh-projects-api/parquet/` and are produced by separate enrichment/flattening scripts (under `archive/` and related dirs).

---

### Component 1: Base Data Extractor (`base-data/fetch_dpwh_projects_paginated.py`)

**Purpose**

- Fetches large pages of project listings from  
  `https://api.transparency.dpwh.gov.ph/projects?page={page}&limit={limit}`.
- Handles Cloudflare / TLS fingerprinting via `curl_cffi` when available.
- Designed to be resumable and to track TLS fingerprint quality.

**Key Inputs**

- **Endpoint**: `API_BASE = "https://api.transparency.dpwh.gov.ph/projects"`.
- **Paging parameters**:
  - `LIMIT` (default `5000`) — items per page; up to API max of 5000.
  - `TOTAL_CONTRACTS = 247187` → `compute_max_pages()` derives total pages.
- **TLS fingerprints**:
  - `base-data/impersonate_pool.json` — active list of curl_cffi `impersonate` profiles.
  - `base-data/never_success_tls.json` — persistent blacklist; fingerprints are removed from the active pool when they are detected as unsupported, or when they continuously fail across runs.
  - `base-data/impersonate_health.json` — persistent per-fingerprint health (success/fail counts + consecutive failure streak) used for automatic demotion.
- **Concurrency & retries**:
  - `MAX_WORKERS` (CLI: `--workers`) — thread pool size.
  - `MAX_RETRIES = 4` — per‑page retry budget.
  - `MIN_DELAY` / `MAX_DELAY` — random delay between attempts to avoid rate limits.

**Directory Layout & Key Paths**

- **Base dir**: `BASE_DIR = base-data/`.
- **JSON output**: `JSON_DIR = base-data/json/`  
  Files: `dump-page-{page}-{limit}.json`.
- **Lists**: `LISTS_DIR = base-data/lists/`
  - `successful_pages.txt` — one page number per successfully saved page.
  - `failed_pages.txt` — pages that exhausted retries without success.
  - `dump-page-{page}-{limit}-raw.txt` — raw non‑JSON or error responses.
  - `dump-page-{page}-{limit}-error.txt` — exception text when request errors.
- **Progress log**: `PROGRESS_PATH = base-data/progress_stats.json`.
- **TLS blacklist**: `NEVER_SUCCESS_TLS_PATH = base-data/never_success_tls.json`.

**Core Logic (Simplified)**

- **Existing pages detection** (`existing_pages()`):
  - Scans `JSON_DIR` for filenames matching `dump-page-*-{limit}.json`.
  - Reads `successful_pages.txt` and merges into a “done” pages set.
  - This drives resume behavior: already successful pages are skipped.

- **Request building** (`fetch_page()`):
  - Constructs URL via `build_url(page, limit)`.
  - Builds headers:
    - `Accept`, `Origin`, `Referer` (rotated from `REFERERS`),  
      `Accept-Language` (rotated from `ACCEPT_LANGUAGES`),  
      `Accept-Encoding`, `DNT`, `Connection`, `Sec-Fetch-*`.
  - If `curl_cffi` is available:
    - Chooses a random `impersonate_choice` from `IMPERSONATE_POOL`.
    - Initializes/updates `tls_stats[impersonate_choice]`.

- **Response handling & retries**:
  - If HTTP `200` with JSON content and not blocked (no Cloudflare 1015 / “just a moment” / “rate limited” markers):
    - Returns `resp.json()` and records `retries[page] = attempt`.
  - If `403`, `429`, or Cloudflare block:
    - Logs `[RETRY]`, increments appropriate TLS stats (`block` or `rate_limited`).
    - Performs exponential backoff (`time.sleep(5 * attempt)`).
    - Retries up to `MAX_RETRIES`.
  - On other status codes:
    - Retries with smaller backoff.
    - On final failure, writes `dump-page-{page}-{limit}-raw.txt` and returns `None`.
  - On exceptions:
    - If TLS fingerprint is “not supported”:
    - Immediately demotes it (removes from `base-data/impersonate_pool.json`).
    - Adds to `base-data/never_success_tls.json` and records metadata in `base-data/impersonate_health.json`.
      - **Does not** count against retry budget.
    - Otherwise:
      - Logs exception, updates TLS stats (`exception`, optionally `timeout`).
      - On final failure, writes `dump-page-{page}-{limit}-error.txt` and returns `None`.

- **Concurrent orchestration** (`main()`):
  - Determines `end_page` if not provided via CLI.
  - Computes `pages` to fetch = `[start_page..end_page] - existing_pages`.
  - Spawns a progress logger thread that:
    - Every 10 seconds writes `progress_stats.json`:
      - `total`, `success`, `fail`, `retries`, `timestamp`, `tls_stats`.
  - Uses `ThreadPoolExecutor(max_workers)` to:
    - Call `fetch_and_save_concurrent(page, ...)`:
      - Skips pages already “done”.
      - Calls `fetch_page()`.
      - On success: counts items (via `count_items()`), calls `save_json()`, appends to `successful_pages.txt`.
      - On failure: appends page to `failed_pages.txt`.

**CLI Usage**

- Typical commands (also in `README.md`):

```bash
python base-data/fetch_dpwh_projects_paginated.py
python base-data/fetch_dpwh_projects_paginated.py --start 1 --end 10
python base-data/fetch_dpwh_projects_paginated.py --start 1 --end 50 --limit 5000 --workers 10
```

---

### Component 2: Combining JSON to Parquet (`archive/combine_json_to_parquet.py`)

**Purpose**

- Reads all JSON page files from a directory (designed for a “dwph‑transparency‑api” JSON dump).
- Extracts the nested `data.data` list from each JSON.
- Flattens the `location` field into multiple `location_*` columns.
- Writes a consolidated Parquet file.

**Key Behavior**

- **Input directory**: `DATA_DIR = "dwph-transparency-api"`  
  (You’d point this at wherever the paginated JSON files are stored.)
- **Output**: `OUTPUT_FILE = "combined_data_only.parquet"`.
- Iterates over all `*.json`:
  - If file is a dict: looks up `obj["data"]["data"]` (if present).
  - If file is a list: for each item, again looks up `item["data"]["data"]`.
  - Each record is passed through `flatten_location()`:
    - Pops `record["location"]` (dict) and converts keys to `location_{k}` fields.
- After aggregation:
  - Builds a `pandas.DataFrame`.
  - Converts to `pyarrow.Table` then writes Parquet.

**Role in the Pipeline**

- This is **the bridge** between the **paginated base data** and the **contract‑level extractor**:
  - Base data JSON → flattened Parquet with `contractId` and other fields.
  - Later used by `fetch_dpwh_projects_curlcffi.py` to get unique `contractId`s.

---

### Component 3: Per‑Contract Extractor (`projects-data/extraction-script/fetch_dpwh_projects_curlcffi.py`)

**Purpose**

- For each unique `contractId` from a Parquet dataset, call  
  `https://api.transparency.dpwh.gov.ph/projects/{contractId}`.
- Use `curl_cffi` with TLS impersonation and an HTTP proxy pool to reduce Cloudflare blocking.
- Track extensive stats per TLS fingerprint and per proxy.
- Persist progress to disk (JSON logs + .txt/.json lists of IDs).

**Key Inputs**

- **Paths & dataset**:
  - `BASE_DIR` = `projects-data/extraction-script/`.
  - `REPO_ROOT` = two levels up from `BASE_DIR`.
  - `DATA_ROOT` = `projects-data/`.
  - `OUTPUT_DIR` = `projects-data/dpwh-projects-api/`.
  - `PARQUET_PATH` = a Parquet file containing base data (and `contractId` column).  
    - Script reads it via `pd.read_parquet(PARQUET_PATH)`.
    - Drops null `contractId`s and extracts unique values: `contract_ids`.
    - Raises `FileNotFoundError` if `PARQUET_PATH` is missing.

- **Networking & concurrency**:
  - Endpoint: `API_URL = "https://api.transparency.dpwh.gov.ph/projects/{}`"`.
  - `MAX_WORKERS = 50` — high concurrency (tune down to be gentler).
  - `MAX_RETRIES = 3` per contract ID.
  - `MIN_DELAY = 1.8`, `MAX_DELAY = 4.0` — randomized delays per attempt.

- **Proxies**:
  - `free_proxies.json` — required; generated by `generate_proxy_list.py`.
  - Optional `premium_proxies.json` — appended if present.
  - `PROXIES` list is built at import; also maintains:
    - `BLACKLISTED_PROXIES` — global set, proxies that are unusable.
    - Per‑proxy stats in `proxy_stats` and health tracking attributes on `fetch_and_save`.

- **TLS fingerprints**:
  - `IMPERSONATE_POOL` — Chrome/Firefox/Safari/Edge/Opera labels.
  - `never_success_tls.json` under `OUTPUT_DIR` — used to filter out fingerprints that previously never succeeded.
  - `tls_stats` — dynamic dict of fingerprint → counts for various outcome types  
    (`success`, `fail`, `block`, `exception`, `timeout`, `curl_7`, `curl_35`, `curl_56`, `rate_limited`).

- **Rate limit state**:
  - `rate_limit_state` dict tracks whether non‑proxy requests are currently considered rate limited, and when to re‑check without proxy.

**Output Layout**

Under `projects-data/dpwh-projects-api/`:

- `dpwh_projects.duckdb` — DuckDB database file (primary sink); table `projects_raw(contract_id TEXT PRIMARY KEY, json TEXT)` holds the raw JSON per contract.
- `json/` — optional one JSON file per successful contract ID: `{contractId}.json` (only written if `WRITE_JSON_FILES = True` in the extractor).
- `raw/` — text files with raw HTML/error messages per failed attempt: `{contractId}_raw.txt`.
- `lists/`:
  - `successful_ids.txt` / `.json` — IDs fetched successfully.
  - `failed_ids.txt` / `.json` — IDs with non‑JSON or error responses.
  - `exception_ids.txt` / `.json` — IDs where exceptions occurred.
  - `blocked_ids.txt` / `.json` — IDs blocked by Cloudflare (no success at all).
  - `dropped_ids.txt` / `.json` — IDs that ended in any of fail/exception/block paths.
  - Additional lists like `curl_7_ids`, `curl_35_ids`, `curl_56_ids` are kept in `stats` and logged via `progress_stats.json`.
  - `diff.*`, `json_files_list.*` — comparison and file‑listing utilities used to validate completeness; summarized in `extraction_summary_report.json`.

- `progress_stats.json` — periodically updated with:
  - Overall stats: totals, success/fail/blocked/exception counts, retry counts, skipped counts.
  - `proxy_stats`, `tls_stats`, `rate_limit_state`.
  - Timestamp.

- `never_success_tls.json` — TLS fingerprints that never succeeded for per‑contract extraction.

- `extraction_summary_report.json` — final high‑level summary of completeness:
  - `total_successful_ids`
  - `total_extracted_files`
  - `matched_count`, `missing_count`, `extra_count`
  - `completion_percentage`

- `parquet/` — enriched downstream artifacts:
  - `dpwh_projects_enriched_flat.parquet`
  - `dpwh_projects_enriched_nested.parquet`

**Core Processing: `fetch_and_save(cid)`**

For each `contractId`:

1. **Skip if already successful**:
   - `successful_ids_cache` is loaded once from `lists/successful_ids.txt` at startup.
   - If `cid` is in cache: increments `skipped_success_count` and returns early.

2. **Per‑ID state**:
   - Tracks:
     - `blocked_this_id`, `fail_this_id`, `exception_this_id`, `retries_for_id`.
   - Maintains function‑level attributes on `fetch_and_save`:
     - `proxy_timeouts`, `proxy_error_times`, `proxy_consecutive_failures`, `proxy_successes`.

3. **Proxy selection** (`get_valid_proxy()`):
   - Filters out:
     - Proxies in `BLACKLISTED_PROXIES`.
     - Proxies in `stats["skipped_proxies"]`.
   - If a proxy has ≥2 consecutive failures and **no** successes ever:
     - Immediately blacklisted and skipped.
   - Considers only proxies with ≤3 recent errors within last 30 seconds.
   - Prefers proxies in `proxy_successes` (those with known successes).

4. **Non‑proxy vs proxy strategy**:
   - If `non_proxy_rate_limited` is `True`:
     - Uses a proxy for all attempts, unless re‑check interval has passed.
   - Else:
     - Attempts 1–2: no proxy (direct).
     - Attempts ≥3: uses a proxy from `get_valid_proxy()`, if available.

5. **Headers & TLS**:
   - Random delay between `MIN_DELAY` and `MAX_DELAY`.
   - Random `Accept-Language` and `Referer`, plus fixed set of realistic headers.
   - Optional cookie rotation if `COOKIES_LIST` is populated (currently empty).
   - Picks random `impersonate_choice` from `IMPERSONATE_POOL` per request.
   - Initializes and updates `tls_stats[impersonate_choice]`.

6. **Response handling**:
   - If HTTP `200`, JSON content, not Cloudflare “just a moment” / 1015:
     - Writes raw JSON text into DuckDB table `projects_raw` keyed by `contract_id` (using `INSERT OR REPLACE` for idempotence).  
       - If `duckdb` is not available or `USE_DUCKDB = False`, falls back to per‑ID JSON files in `json/{cid}.json`.  
       - If `WRITE_JSON_FILES = True`, it writes both to DuckDB and to per‑ID JSON files.
     - Appends `cid` to `successful_ids.txt` and `successful_ids.json`.
     - Adds `cid` to `successful_ids_cache` (for skip on other threads).
     - Updates per‑proxy and global `stats["success"]`.
     - If non‑proxy was previously rate limited and succeeds again: resets `non_proxy_rate_limited`.

   - If rate limit or Cloudflare block (429, 403, or 1015 markers):
     - Updates `tls_stats[impersonate_choice]["rate_limited"]`.
     - If non‑proxy: sets `non_proxy_rate_limited = True` and timestamps.
     - Increments `stats["rate_limited_429"]` or `stats["rate_limited_403"]`.
     - Sleeps (longer for 429/Cloudflare: 30–60s; shorter for 403: 5–10s) and continues to next attempt.

   - Other non‑success responses:
     - Writes response body to `raw/{cid}_raw.txt`.
     - Updates `tls_stats` (e.g., `fail`, `timeout`, `curl_7/35/56` depending on content).
     - Increments per‑proxy fail counts.
     - Appends `cid` to `failed_ids.txt` and `failed_ids.json`.
     - Updates `stats["fail"]` and ends loop.

7. **Exception handling**:
   - On exception:
     - Writes `str(e)` to `raw/{cid}_raw.txt`.
     - Updates `tls_stats[impersonate_choice]["exception"]` and error‑type counts.
     - For proxies:
       - Increments `proxy_stats[proxy]["exception"]` and specific curl/timeout counters.
       - Increments `proxy_consecutive_failures[proxy]`.
       - Adds timestamp to `proxy_error_times`.
       - For connection‑style errors (`curl: (7|35|56)` or “failed to connect”): immediately blacklists proxy.
     - Updates global `stats` (e.g., `timeout`, `curl_7/35/56` counters and ID lists).
     - Appends `cid` to `exception_ids.txt` / `.json`.
     - Ends loop.

8. **Post‑loop classification and logging**:
   - If `blocked_this_id` and no success/fail/exception recorded:
     - Writes `blocked_ids.*`, increments `stats["blocked"]`, `stats["blocked_ids"]`, and `block_retries_per_id[cid]`.
   - If `fail_this_id` or `exception_this_id` or (blocked without success):
     - Writes `dropped_ids.*`.
   - Always increments `stats["total"]`.

**Progress logging**

- `ProgressLogger` (daemon thread) writes `progress_stats.json` every N seconds (default 10) with:
  - `stats` copy,
  - `proxy_stats`,
  - `tls_stats`,
  - `rate_limit_state`,
  - Timestamp.

**Main entrypoint**

- At bottom of script (`if __name__ == "__main__":`):
  - Validates Parquet path and loads contract IDs.
  - Initializes `stats_lock`.
  - Starts `ProgressLogger`.
  - Uses `ThreadPoolExecutor(max_workers=MAX_WORKERS)` to call `fetch_and_save` for each `cid`.
  - After completion:
    - Stops logger, writes a final `progress_stats.json`.
    - Logs aggregate stats to stdout (success/fail/blocked, block rate, average retries, IDs by category).

**Typical Usage**

From repo root:

```bash
cd projects-data/extraction-script
python fetch_dpwh_projects_curlcffi.py
```

You can adjust `MAX_WORKERS`, `MAX_RETRIES`, and delays inside the script to tune aggressiveness vs reliability.

---

### Component 4: Proxy Generation & File Listing Utilities

**Proxy list generator** — `projects-data/extraction-script/generate_proxy_list.py`

- Fetches `https://free-proxy-list.net/`.
- Uses a regex on the HTML table to extract only HTTPS‑capable proxies.
- Outputs `free_proxies.json` as:

```json
[
  "http://ip1:port1",
  "http://ip2:port2",
  ...
]
```

- This file is read at import time by `fetch_dpwh_projects_curlcffi.py` and combined with any `premium_proxies.json` present in the same directory.

**JSON file lister** — `projects-data/extraction-script/list_json_files.py`

- Intended to list JSON files in a `projects-data/json` directory (or tar archives within it) without reading contents.
- Writes:
  - `json_files_list.txt` — one filename per line.
  - `json_files_list.json` — array of filenames.
- Helps validate completeness (e.g., match `successful_ids` vs actual files on disk) and feeds into summary comparisons (`diff.*`, `extraction_summary_report.json`).

---

### End‑to‑End Operational View

Putting it together in “how you’d run it” terms:

1. **Extract base paginated data**
   - Run `base-data/fetch_dpwh_projects_paginated.py` with desired `--start`, `--end`, `--limit`, `--workers`.
   - Monitor:
     - `base-data/progress_stats.json` (live status & TLS stats),
     - `base-data/lists/successful_pages.txt` and `failed_pages.txt`.

2. **Combine base JSON into Parquet**
   - Run `archive/combine_json_to_parquet.py` (or your equivalent) pointing `DATA_DIR` at the JSON dump directory.
   - Ensure output Parquet (with `contractId`) is placed where `fetch_dpwh_projects_curlcffi.py` expects it (`PARQUET_PATH`).

3. **Generate proxy list (if needed)**
   - From `projects-data/extraction-script/`, run `python generate_proxy_list.py` to create/update `free_proxies.json`.
   - Optionally, create `premium_proxies.json` with additional high‑quality proxies.

4. **Extract per‑contract details**
   - From `projects-data/extraction-script/`, run `python fetch_dpwh_projects_curlcffi.py`  
     or, from repo root, use the wrapper: `python run_data_pipeline.py` (which can also run the base extractor).
   - Monitor:
     - `projects-data/dpwh-projects-api/progress_stats.json`,
     - `lists/` files for success/fail/blocked/exception/dropped IDs,
     - stdout logs for TLS/proxy health patterns.

5. **Validate completeness**
   - Use `list_json_files.py` or existing `json_files_list.*` and `diff.*` in `projects-data/dpwh-projects-api/lists/`.
   - Review `extraction_summary_report.json` for:
     - Matched vs missing vs extra IDs,
     - `completion_percentage`.

6. **Enrichment and analysis**
   - Use (or extend) the enrichment/flattening scripts under `archive/` and the generated Parquets in `projects-data/dpwh-projects-api/parquet/` for downstream analytics.
