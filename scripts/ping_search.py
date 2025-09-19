#!/usr/bin/env python3
# Simple ping to search engines after deploy (optional if hosting gives hook)
import os, urllib.parse, urllib.request

sitemap = os.environ.get("SITEMAP_URL", "https://example.com/sitemap.xml")
targets = [
    "https://www.google.com/ping?sitemap=",
    "https://www.bing.com/ping?sitemap=",
]

for t in targets:
    url = t + urllib.parse.quote_plus(sitemap)
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            print("Pinged:", url, resp.status)
    except Exception as e:
        print("Fail:", url, e)
