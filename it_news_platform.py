"""Automated IT News Intelligence Platform — one-file Python portfolio project.

Install: pip install pillow
Optional video: install FFmpeg and add it to PATH.
Install: pip install pillow tzdata keyring
Save Gmail App Password in Windows Credential Manager using keyring.
Gmail address defaults to the owner address; NEWS_EMAIL_USER/TO can override.
Run: python it_news_platform.py
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
import html
import json
import keyring
import os
from pathlib import Path
import re
import shutil
import smtplib
import subprocess
import textwrap
import urllib.request
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

FEEDS = {
    "BBC Technology": "https://feeds.bbci.co.uk/news/technology/rss.xml",
    "Ars Technica": "https://feeds.arstechnica.com/arstechnica/index",
    "The Register": "https://www.theregister.com/headlines.atom",
    "Hacker News": "https://hnrss.org/frontpage",
}
KEYWORDS = {
    "artificial intelligence": 5, "ai": 2, "machine learning": 5,
    "python": 6, "security": 4, "cybersecurity": 6,
    "cloud": 4, "aws": 5, "microsoft": 2, "google": 2,
    "developer": 5, "software": 3, "open source": 4,
    "data": 2, "linux": 4, "api": 4, "robot": 3,
}
HEADERS = {"User-Agent": "ITNewsPortfolio/1.0 (personal RSS reader)"}
TZ = ZoneInfo("America/Toronto")


def clean(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def child_text(node, name: str) -> str:
    for child in node:
        if child.tag.split("}")[-1] == name:
            return "".join(child.itertext()).strip()
    return ""


def parse_date(value: str):
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
    except (ValueError, TypeError):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def fetch_feed(source: str, url: str) -> list[dict]:
    try:
        request = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(request, timeout=15) as response:
            xml = response.read(3_000_000)
        root = ET.fromstring(xml)
        entries = [n for n in root.iter() if n.tag.split("}")[-1] in ("item", "entry")]
        result = []
        for entry in entries[:35]:
            title = clean(child_text(entry, "title"))
            summary = clean(child_text(entry, "description") or child_text(entry, "summary") or child_text(entry, "content"))
            link = child_text(entry, "link")
            if not link:
                for el in entry:
                    if el.tag.split("}")[-1] == "link" and el.attrib.get("href"):
                        link = el.attrib["href"]
                        if el.attrib.get("rel", "alternate") == "alternate":
                            break
            published = parse_date(child_text(entry, "pubDate") or child_text(entry, "published") or child_text(entry, "updated"))
            if title and link.startswith(("https://", "http://")):
                result.append({"title": title, "summary": summary, "url": link,
                               "source": source, "published": published})
        print(f"[OK] {source}: {len(result)} articles")
        return result
    except Exception as exc:
