"""Automated IT News Intelligence Platform.

Python 3.10+; standard library for RSS, reports, and email.
Optional: pip install pillow (video frames); install FFmpeg for MP4.

Environment variables for GitHub Actions:
    NEWS_EMAIL_USER  Gmail address used to send messages
    NEWS_EMAIL_PASSWORD  Gmail app password (GitHub Actions secret)
    NEWS_EMAIL_TO    Comma/semicolon/newline-separated recipients

On Windows, optional fallback: keyring service 'it_news_intelligence',
username matching NEWS_EMAIL_USER (requires pip install keyring).

Run: python it_news_platform.py --no-video
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
import html
import json
import os
from pathlib import Path
import re
import shutil
import smtplib
import subprocess
import tempfile
import textwrap
import urllib.request
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / 'news_output'
WEBSITE_JSON = ROOT / 'website' / 'latest-news.json'
TZ = ZoneInfo('America/Toronto')
FEEDS = {
    'BBC Technology': 'https://feeds.bbci.co.uk/news/technology/rss.xml',
    'Ars Technica': 'https://feeds.arstechnica.com/arstechnica/index',
    'The Register': 'https://www.theregister.com/headlines.atom',
    'Hacker News': 'https://hnrss.org/frontpage',
}
KEYWORDS = {
    'artificial intelligence': 5, 'ai': 2, 'machine learning': 5,
    'python': 6, 'security': 4, 'cybersecurity': 6, 'cloud': 4,
    'aws': 5, 'microsoft': 2, 'google': 2, 'developer': 5,
    'software': 3, 'open source': 4, 'data': 2, 'linux': 4,
    'api': 4, 'robot': 3,
}
HEADERS = {'User-Agent': 'ITNewsPortfolio/1.0 (+personal RSS reader)'}


def clean(value: str) -> str:
    value = re.sub(r'<[^>]+>', ' ', value or '')
    return re.sub(r'\s+', ' ', html.unescape(value)).strip()


def child_text(node: ET.Element, name: str) -> str:
    for child in node:
        if child.tag.split('}')[-1] == name:
            return ''.join(child.itertext()).strip()
    return ''


def parse_date(value: str):
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
    except (ValueError, TypeError, IndexError):
        try:
            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def fetch_feed(source: str, url: str) -> list[dict]:
    try:
        request = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read(3_000_000)
        root = ET.fromstring(raw)
        entries = [n for n in root.iter() if n.tag.split('}')[-1] in ('item', 'entry')]
        articles = []
        for entry in entries[:35]:
            title = clean(child_text(entry, 'title'))
            summary = clean(child_text(entry, 'description') or child_text(entry, 'summary') or child_text(entry, 'content'))
            link = child_text(entry, 'link')
            if not link.startswith(('http://', 'https://')):
                link = ''
                for element in entry:
                    if element.tag.split('}')[-1] == 'link' and element.attrib.get('href'):
