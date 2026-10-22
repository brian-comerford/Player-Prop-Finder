"""Prints a site's robots.txt and the clauses of its terms pages that
mention automated access, so whether a data source may be collected can
be checked from CI (this repo's dev sandbox can't reach most sites).

Usage: python scripts/check_site_terms.py <url> [<url> ...]
"""
import re
import sys
from html import unescape
from urllib.parse import urlparse

import requests

KEYWORDS = re.compile(
    r"robot|spider|scrap|crawl|automat|data min|bot\b|harvest|extract|"
    r"commercial|reproduc|redistribut|machine learning|artificial intelligence",
    re.IGNORECASE,
)
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; player-prop-finder terms check)"}


def text_of(html):
    html = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    return re.sub(r"\s+", " ", unescape(re.sub(r"(?s)<[^>]+>", " ", html)))


def main():
    seen_hosts = set()
    for url in sys.argv[1:]:
        host = urlparse(url).netloc
        if host not in seen_hosts:
            seen_hosts.add(host)
            try:
                robots = requests.get(f"https://{host}/robots.txt", headers=HEADERS, timeout=30)
                print(f"===== https://{host}/robots.txt ({robots.status_code})\n{robots.text[:4000]}\n")
            except requests.RequestException as exc:
                print(f"===== robots.txt for {host} unavailable: {exc}\n")
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
        except requests.RequestException as exc:
            print(f"===== {url} unavailable: {exc}\n")
            continue
        print(f"===== {url} ({resp.status_code}, final URL {resp.url})")
        sentences = re.split(r"(?<=[.;:])\s+", text_of(resp.text))
        hits = [s for s in sentences if KEYWORDS.search(s) and len(s) < 1200]
        for s in hits[:60]:
            print(f"  - {s}")
        if not hits:
            print("  (no matching clauses)")
        print()


if __name__ == "__main__":
    main()
