# DPWH Transparency API Data Scraper

A comprehensive Python-based data extraction toolkit for scraping project and contract data from the Department of Public Works and Highways (DPWH) Transparency Portal API.

## 📋 Overview

This repository contains two main extraction scripts designed to collect data from the DPWH Transparency API:

1. **Base Data Extractor** (`base-data/`) - Pagination-based extraction for bulk project listings
2. **Projects Data Extractor** (`projects-data/`) - Individual contract detail extraction with proxy support

### API Endpoints
- **Base API**: `https://api.transparency.dpwh.gov.ph/projects`
- **Project Details**: `https://api.transparency.dpwh.gov.ph/projects/{contractId}`

## 🚀 Features

### Base Data Extractor (`base-data/fetch_dpwh_projects_paginated.py`)
- ✅ Concurrent page fetching with ThreadPoolExecutor
- ✅ Automatic TLS fingerprint rotation (70+ browser profiles)
- ✅ Smart fingerprint blacklisting (instantly removes unsupported TLS versions)
- ✅ Resume capability (tracks completed pages)
- ✅ Real-time progress tracking with 10-second snapshots
- ✅ Comprehensive retry logic with exponential backoff
- ✅ Rate limit detection and handling (403, 429, Cloudflare 1015)
- ✅ Detailed statistics and success rate reporting

### Projects Data Extractor (`projects-data/extraction-script/fetch_dpwh_projects_curlcffi.py`)
- ✅ Proxy support (free + premium proxy rotation)
- ✅ Advanced proxy health monitoring and blacklisting
- ✅ TLS fingerprint diversity (Chrome, Firefox, Safari, Edge, Opera)
- ✅ Per-proxy and per-fingerprint statistics tracking
- ✅ Automatic retry with intelligent proxy selection
- ✅ Background progress logging
- ✅ Parquet dataset integration for contract ID sourcing

## 📦 Installation

### Prerequisites
- Python 3.8+
- pip

### Install Dependencies

```bash
# Core dependencies
pip install curl-cffi requests pandas

# Optional for advanced features
pip install pyarrow  # For parquet file support
```

### Required Python Packages
```
curl-cffi>=0.5.0    # Cloudflare-friendly TLS fingerprinting
requests>=2.28.0     # HTTP fallback library
pandas>=1.5.0        # Data processing (projects extractor)
```

## 🎯 Usage

### Base Data Extraction (Paginated Projects)

Extract paginated project listings with automatic pagination:

```bash
# Extract all pages (auto-calculates ~50 pages for 247,187 contracts)
python base-data/fetch_dpwh_projects_paginated.py

# Extract specific page range
python base-data/fetch_dpwh_projects_paginated.py --start 1 --end 10

# Custom configuration
python base-data/fetch_dpwh_projects_paginated.py --start 1 --end 50 --limit 5000 --workers 10
```

#### Command-line Arguments
- `--start`: Starting page number (default: 1)
- `--end`: Ending page number (default: auto-calculated from total contracts)
- `--limit`: Items per page (default: 5000, API max)
- `--workers`: Concurrent workers (default: 10)

#### Output Structure
```
base-data/
├── base-data-json.tar.xz          # Bulk archive of all extracted JSON data
├── lists/                         # Tracking files
│   ├── successful_pages.txt       # Completed pages
│   ├── failed_pages.txt           # Failed pages
│   ├── dump-page-*-error.txt      # Error messages
│   └── dump-page-*-raw.txt        # Raw error responses
├── progress_stats.json            # Real-time progress
└── never_success_tls.json         # Blacklisted fingerprints
```

### Projects Data Extraction (Individual Contracts)

Extract detailed data for individual contracts using contract IDs:

```bash
cd projects-data/extraction-script
python fetch_dpwh_projects_curlcffi.py
```

**Note**: This script requires a parquet dataset with contract IDs. Adjust `PARQUET_PATH` in the script or create `free_proxies.json` with your proxy list.

#### Output Structure
```
projects-data/dpwh-projects-api/
├── projects-json.tar.xz.001       # Bulk archive part 1 of contract JSON files
├── projects-json.tar.xz.002       # Bulk archive part 2 of contract JSON files
├── lists/                         # Tracking files
│   ├── successful_ids.txt
│   ├── failed_ids.txt
│   ├── exception_ids.txt
│   └── blocked_ids.txt
├── raw/                           # Error responses
│   └── {contractId}_raw.txt
├── progress_stats.json            # Real-time stats
└── never_success_tls.json         # Blacklisted fingerprints
```

## 🔧 Configuration

### TLS Fingerprints
Both scripts use 70+ browser fingerprints for TLS diversity:
- Chrome 100-120
- Firefox 100-119
- Safari 14-17
- Edge 110-119
- Opera 95-102

**Auto-Blacklisting**: Fingerprints that return "not supported" errors are immediately blacklisted and saved to `never_success_tls.json` for exclusion in future runs.

### Rate Limiting
- **Detection**: Monitors HTTP 403, 429, and Cloudflare error 1015
- **Handling**: Exponential backoff (5-20 seconds per retry)
- **Retry Logic**: Up to 4 attempts per page/contract

### Progress Tracking
Real-time statistics updated every 10 seconds:
```json
{
  "total": 50,
  "success": 45,
  "fail": 5,
  "retries": {"33": 2, "46": 4},
  "tls_stats": {
    "chrome116": {"success": 10, "fail": 0, "block": 0},
    "firefox119": {"success": 8, "exception": 2}
  }
}
```

## 📊 Features Explained

### Smart Fingerprint Management
- **Automatic Detection**: Identifies unsupported TLS versions
- **Instant Blacklisting**: Removes failed fingerprints immediately
- **Persistent Storage**: Saves blacklist to `never_success_tls.json`
- **No Retry Waste**: Unsupported fingerprints don't count against retry limit

### Resume Capability
- Checks `successful_pages.txt` before fetching
- Skips already-downloaded pages automatically
- Safe to interrupt and resume at any time

### Concurrent Processing
- ThreadPoolExecutor for parallel requests
- Configurable worker count (default: 10)
- Thread-safe statistics tracking with locks

### Comprehensive Logging
- `[FETCH]` - Starting page/contract fetch
- `[TLS]` - Fingerprint selection per attempt
- `[RETRY]` - Retry attempts with reason
- `[BLACKLIST]` - Fingerprint removal
- `[SAVE]` - Successful data save
- `[FAIL]` - Final failure after all retries

## 🛠️ Troubleshooting

### No Valid Fingerprints Remaining
If all fingerprints are blacklisted:
1. Delete `never_success_tls.json`
2. Update `curl-cffi` to latest version: `pip install --upgrade curl-cffi`
3. Reduce worker count: `--workers 5`

### High Failure Rate
- Reduce concurrent workers: `--workers 5`
- Increase delays in script (modify `MIN_DELAY`/`MAX_DELAY`)
- Check internet connection stability
- Consider using proxies (projects extractor only)
- For DPWH Transparency dashboard, it seems to limit to a max off 300 requests per 10 minutes. (Around 1 request every 2 seconds) 
- You can try going faster than that but you risk being rate limited after exceeding 1000 fast requests. (Cloudlflare Error 1015). Error 1015 will reset after 10 minutes.

### Rate Limited
- Script automatically handles rate limits with backoff
- For persistent rate limits, reduce `MAX_WORKERS`
- Projects extractor will switch to proxy mode automatically

## 📈 Statistics & Monitoring

### View Progress During Extraction
```bash
# Watch progress in real-time
watch -n 2 cat base-data/progress_stats.json

# Check successful pages
wc -l base-data/lists/successful_pages.txt

# View TLS fingerprint stats
python -c "import json; print(json.dumps(json.load(open('base-data/progress_stats.json'))['tls_stats'], indent=2))"
```

### Analyze Results
```bash
# Count extracted files (if not using tar.xz)
ls base-data/json/*.json | wc -l

# If using tar.xz archives, extract and analyze as needed:
tar -xJf base-data/base-data-json.tar.xz -C /tmp/json_extract/
ls /tmp/json_extract/*.json | wc -l

# Total contracts extracted (from extracted files)
python -c "import json, glob; print(sum(len(json.load(open(f))['data']['data']) for f in glob.glob('/tmp/json_extract/*.json')))"
```

## 🏗️ Project Structure

```
dpwh-transparency-api-data/
├── base-data/                              # Pagination extractor
│   ├── fetch_dpwh_projects_paginated.py   # Main script
│   ├── json/                               # Output data
│   ├── lists/                              # Tracking files
│   ├── progress_stats.json                 # Progress snapshot
│   └── never_success_tls.json              # Blacklisted fingerprints
│
├── projects-data/                          # Contract details extractor
│   ├── extraction-script/
│   │   ├── fetch_dpwh_projects_curlcffi.py
│   │   ├── free_proxies.json
│   │   ├── premium_proxies.json
│   │   └── generate_proxy_list.py
│   └── dpwh-projects-api/                  # Output directory
│
├── samples/                                # Sample data files
├── archive/                                # Archived data (git-ignored)
├── .gitignore                              # Git ignore rules
└── README.md                               # This file
```

## 🤝 Contributing

Contributions welcome! Areas for improvement:
- Additional error handling
- Performance optimizations
- Proxy rotation enhancements
- Data validation and cleaning
- Alternative API endpoint support

## ⚠️ Disclaimer

This tool is for educational and research purposes. Please:
- Respect the DPWH API rate limits
- Use responsibly and ethically
- Comply with the DPWH Transparency Portal Terms of Service
- Do not overload the API servers

## 📝 License

This project is open source and available for educational purposes.

## 🔗 Related Links

- [DPWH Transparency Portal](https://transparency.dpwh.gov.ph/)
- [curl-cffi Documentation](https://curl-cffi.readthedocs.io/)

---

**Total Contracts**: ~247,187  
**Estimated Pages**: ~50 (at 5000 items/page)  
**API Max Limit**: 5000 items per request
