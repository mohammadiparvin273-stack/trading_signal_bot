"""
Free news headline fetcher using plain RSS (no API key, no paid news
vendor). Used only to feed the optional Sentiment layer — if this fails
for any reason (offline, feed down), it returns an empty list and the
LLM/keyword sentiment module falls back to Neutral automatically.
"""
from __future__ import annotations

import re
import urllib.request
from typing import List
from xml.etree import ElementTree

from config.settings import SETTINGS


def fetch_headlines(max_headlines: int = None) -> List[str]:
    max_headlines = max_headlines or SETTINGS.llm.max_headlines
    headlines: List[str] = []

    for url in SETTINGS.llm.rss_feeds:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                raw = resp.read()
            root = ElementTree.fromstring(raw)
            for item in root.iter("item"):
                title_el = item.find("title")
                if title_el is not None and title_el.text:
                    headlines.append(_clean(title_el.text))
                if len(headlines) >= max_headlines:
                    break
        except Exception:
            # Any network/parsing failure just means fewer/no headlines —
            # sentiment gracefully falls back to Neutral. Never raises.
            continue
        if len(headlines) >= max_headlines:
            break

    return headlines[:max_headlines]


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()
