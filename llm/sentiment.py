"""
Optional LLM-based News/Sentiment layer.

Disabled by default (config/settings.py -> LLMConfig.enabled = False).
The Signal core NEVER depends on this module — if disabled, or if
generation fails for any reason, `get_sentiment()` returns "Neutral"
and the rest of the pipeline proceeds unaffected.

Two supported free/local backends (bring your own, nothing is bundled
or required):
  - "local_hf": a local Hugging Face transformers pipeline (CPU ok, slow)
  - "ollama":   a local Ollama server (e.g. `ollama run llama3`)
Both run entirely on your machine — no paid API calls are made.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from config.settings import SETTINGS


class Sentiment(str, Enum):
    BULLISH = "Bullish"
    NEUTRAL = "Neutral"
    BEARISH = "Bearish"


def get_sentiment(headlines: Optional[list[str]] = None) -> Sentiment:
    if not SETTINGS.llm.enabled or not headlines:
        return Sentiment.NEUTRAL

    try:
        if SETTINGS.llm.backend == "keyword":
            return _sentiment_via_keywords(headlines)
        if SETTINGS.llm.backend == "ollama":
            return _sentiment_via_ollama(headlines)
        if SETTINGS.llm.backend == "local_hf":
            return _sentiment_via_local_hf(headlines)
    except Exception:
        # Never let an optional LLM/sentiment failure break signal generation.
        return Sentiment.NEUTRAL

    return Sentiment.NEUTRAL


# Small open finance/crypto lexicon — free, zero-setup, no download, no
# server. This is intentionally simple: it is a safety-net sentiment
# signal, not a substitute for the core rule-based + ML signal.
_BULLISH_WORDS = {
    "surge", "soar", "rally", "bullish", "breakout", "record high", "all-time high",
    "gains", "jumps", "rebound", "upgrade", "adoption", "inflow", "approval",
    "outperform", "recovery", "boom", "climb", "buy", "upside",
}
_BEARISH_WORDS = {
    "crash", "plunge", "slump", "bearish", "sell-off", "selloff", "collapse",
    "hack", "exploit", "ban", "lawsuit", "downgrade", "outflow", "rejection",
    "underperform", "recession", "fear", "decline", "drop", "liquidation",
}


def _sentiment_via_keywords(headlines: list[str]) -> Sentiment:
    text = " ".join(h.lower() for h in headlines)
    bull_hits = sum(text.count(w) for w in _BULLISH_WORDS)
    bear_hits = sum(text.count(w) for w in _BEARISH_WORDS)
    if bull_hits == bear_hits:
        return Sentiment.NEUTRAL
    return Sentiment.BULLISH if bull_hits > bear_hits else Sentiment.BEARISH


def _sentiment_via_ollama(headlines: list[str]) -> Sentiment:
    import json
    import urllib.request

    prompt = (
        "Classify the overall market sentiment of these headlines as exactly "
        "one word: Bullish, Neutral, or Bearish.\n\n" + "\n".join(headlines)
    )
    payload = json.dumps({"model": "llama3", "prompt": prompt, "stream": False}).encode()
    req = urllib.request.Request(
        "http://localhost:11434/api/generate", data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        text = json.loads(resp.read())["response"].strip().lower()
    if "bull" in text:
        return Sentiment.BULLISH
    if "bear" in text:
        return Sentiment.BEARISH
    return Sentiment.NEUTRAL


def _sentiment_via_local_hf(headlines: list[str]) -> Sentiment:
    from transformers import pipeline  # local model, downloaded once, runs offline after

    clf = pipeline("sentiment-analysis")  # e.g. distilbert-base-uncased-finetuned-sst-2-english
    scores = clf(headlines)
    pos = sum(1 for s in scores if s["label"] == "POSITIVE")
    neg = sum(1 for s in scores if s["label"] == "NEGATIVE")
    if pos > neg:
        return Sentiment.BULLISH
    if neg > pos:
        return Sentiment.BEARISH
    return Sentiment.NEUTRAL
