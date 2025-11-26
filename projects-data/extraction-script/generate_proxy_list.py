import requests
import re
import json

URL = "https://free-proxy-list.net/"
OUTPUT_FILE = "free_proxies.json"

# Fetch the proxy list page
resp = requests.get(URL)
resp.raise_for_status()
html = resp.text

# Extract proxies from the HTML table (IP, Port, HTTPS column)
# Table row structure: IP, Port, Code, Country, Anonymity, Google, Https, Last Checked
# We need to handle potential attributes in td tags like class='hm'
pattern = re.compile(r'<tr><td>([\d.]+)</td><td>(\d+)</td>(?:<td[^>]*>.*?</td>){4}<td[^>]*>(yes|no)</td>')
proxies = []
for match in pattern.finditer(html):
    ip, port, https = match.groups()
    if https == "yes":
        proxies.append(f"http://{ip}:{port}") # Add http:// prefix for curl_cffi

# Save to JSON file
with open(OUTPUT_FILE, "w") as f:
    json.dump(proxies, f, indent=2)

print(f"Saved {len(proxies)} HTTPS proxies to {OUTPUT_FILE}")
