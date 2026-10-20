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
        print(f"[WARN] Could not fetch {source}: {exc}")
        return []


def select_stories(stories: list[dict], count: int, hours: int) -> list[dict]:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=hours)
    selected, seen = [], set()
    for story in stories:
        if story["published"] and story["published"].astimezone(timezone.utc) < cutoff:
            continue
        normalized = re.sub(r"[^a-z0-9]+", " ", story["title"].lower()).strip()
        if normalized in seen:
            continue
        seen.add(normalized)
        body = f'{story["title"]} {story["summary"]}'.lower()
        score = sum(weight for term, weight in KEYWORDS.items()
                    if re.search(r"\b" + re.escape(term) + r"\b", body))
        story["score"] = score
        selected.append(story)
    selected.sort(key=lambda s: (s["score"], s["published"] or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
    return selected[:count]


def brief(story: dict, max_chars=250) -> str:
    summary = story["summary"] or "Read the original article for the full story."
    if len(summary) > max_chars:
        summary = summary[:max_chars].rsplit(" ", 1)[0].rstrip(" ,.;:") + "…"
    return summary


def save_reports(stories: list[dict], output: Path, now: datetime) -> tuple[Path, Path, Path]:
    date = now.strftime("%Y-%m-%d")
    text_path, html_path, json_path = (output / f"IT_News_{date}.{ext}" for ext in ("txt", "html", "json"))
    intro = f"IT NEWS INTELLIGENCE | {now.strftime('%B %d, %Y')} | Ontario\n\n"
    text_content = intro + "\n\n".join(
        f'{i}. {s["title"]}\nSource: {s["source"]}\n{brief(s)}\nRead: {s["url"]}'
        for i, s in enumerate(stories, 1))
    if not stories:
        text_content += "No recent stories found. Check feeds or expand the time window."
    text_path.write_text(text_content, encoding="utf-8")
    blocks = []
    for i, s in enumerate(stories, 1):
        blocks.append(f'<section><h2>{i}. {html.escape(s["title"])}</h2>'
                      f'<small>{html.escape(s["source"])}</small>'
                      f'<p>{html.escape(brief(s))}</p>'
                      f'<a href="{html.escape(s["url"], quote=True)}">Read original article</a></section>')
    html_content = ('<!doctype html><html><head><meta charset="utf-8"><style>'
                    'body{font:16px Arial,sans-serif;background:#f3f6fb;color:#17243b;padding:28px;}'
                    'main{max-width:760px;margin:auto}section{background:white;padding:20px;margin:16px 0;'
                    'border-radius:12px}a{color:#1762b2}small{color:#64748b}</style></head><body><main>'
                    f'<h1>IT News Intelligence</h1><p>{now.strftime("%B %d, %Y")} · Ontario</p>'
                    + ("".join(blocks) if blocks else "<p>No recent stories found.</p>")
                    + '</main></body></html>')
    html_path.write_text(html_content, encoding="utf-8")
    json_path.write_text(json.dumps([{**s, "published": s["published"].isoformat() if s["published"] else None}
                                     for s in stories], indent=2, ensure_ascii=False), encoding="utf-8")
    return text_path, html_path, json_path


def find_font(size: int):
    from PIL import ImageFont
    candidates = ["C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                  "/Library/Fonts/Arial.ttf"]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def create_video(stories: list[dict], output: Path, now: datetime) -> Path | None:
    if not stories:
        return None
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("[INFO] Video skipped: install Pillow with 'pip install pillow'")
        return None
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("[INFO] Video skipped: FFmpeg is not installed or not in PATH")
        return None
    video = output / f'IT_News_{now.strftime("%Y-%m-%d")}.mp4'
    slides_dir = output / "slides"
    slides_dir.mkdir(exist_ok=True)
    cards = [("TODAY IN TECHNOLOGY", f"{now.strftime('%B %d, %Y')}\nYour daily IT news briefing", "IT NEWS")]
    cards += [(s["title"], brief(s, 180), s["source"]) for s in stories]
    cards += [("THAT'S YOUR BRIEFING", "Open the written report for original article links.", "IT NEWS")]
    slide_paths = []
    for idx, (heading, description, source) in enumerate(cards):
        image = Image.new("RGB", (1280, 720), "#101a32")
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((64, 60, 1216, 660), radius=28, fill="#1c2b49")
        draw.rectangle((95, 112, 1170, 118), fill="#56d8e8")
        draw.text((95, 145), source.upper()[:42], font=find_font(29), fill="#56d8e8")
        # Wrap long headlines to fit within the card.
        words, lines, line = heading.split(), [], ""
        for word in words:
            candidate = f"{line} {word}".strip()
            if draw.textbbox((0, 0), candidate, font=find_font(48))[2] > 1040 and line:
                lines.append(line)
                line = word
            else:
                line = candidate
        if line:
            lines.append(line)
        for j, item in enumerate(lines[:4]):
            draw.text((95, 210 + j * 62), item, font=find_font(48), fill="white")
        desc_y = min(500, 230 + len(lines[:4]) * 62)
        for j, item in enumerate(textwrap.wrap(description, width=80)[:3]):
            draw.text((95, desc_y + j * 37), item, font=find_font(25), fill="#cad7ec")
        draw.text((95, 615), f"STORY {idx + 1} OF {len(cards)}", font=find_font(20), fill="#91a9c9")
        slide_path = slides_dir / f"slide_{idx:02}.png"
        image.save(slide_path)
        slide_paths.append(slide_path)
    # Create a silent, widely compatible MP4 from the generated slides.
    args = [ffmpeg, "-y", "-loglevel", "error"]
    for slide in slide_paths:
        args += ["-loop", "1", "-framerate", "1", "-t", "5", "-i", str(slide)]
    filter_parts = []
    for i in range(len(slide_paths)):
        filter_parts.append(f"[{i}:v]fps=25,scale=1280:720,setsar=1,format=yuv420p[v{i}]")
    filter_parts.append("".join(f"[v{i}]" for i in range(len(slide_paths))) +
                        f"concat=n={len(slide_paths)}:v=1:a=0[out]")
    args += ["-filter_complex", ";".join(filter_parts), "-map", "[out]",
             "-c:v", "libx264", "-preset", "ultrafast", "-crf", "27", "-movflags", "+faststart", str(video)]
    try:
        subprocess.run(args, check=True, timeout=180)
        print(f"[OK] Video: {video}")
        return video
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        print(f"[WARN] Video creation failed: {exc}")
        return None


def send_email(text_path: Path, html_path: Path, video_path: Path | None, now: datetime) -> None:
    # The address can be overridden with NEWS_EMAIL_USER / NEWS_EMAIL_TO.
    # The App Password is read from Windows Credential Manager (keyring).
    user = os.getenv("NEWS_EMAIL_USER", "deekarunakaran@gmail.com").strip()
    recipient = os.getenv("NEWS_EMAIL_TO", user).strip()
    password = keyring.get_password("ITNewsIntelligence", "gmail")
    if not password:
        print("[ERROR] Gmail App Password missing from Windows Credential Manager")
        print("[INFO] Save it using the keyring setup command before scheduling")
        raise RuntimeError("Gmail App Password not found in keyring")
    if not user or not recipient:
        raise RuntimeError("Email sender or recipient is missing")
    message = EmailMessage()
    message["Subject"] = f"Daily IT News | {now.strftime('%B %d, %Y')}"
    message["From"] = user
    message["To"] = recipient
    message.set_content(text_path.read_text(encoding="utf-8"))
    message.add_alternative(html_path.read_text(encoding="utf-8"), subtype="html")
    if video_path and video_path.stat().st_size < 18_000_000:
        message.add_attachment(video_path.read_bytes(), maintype="video", subtype="mp4", filename=video_path.name)
    elif video_path:
        print("[WARN] Video is too large to attach; saved locally instead")
    server = os.getenv("NEWS_SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("NEWS_SMTP_PORT", "465"))
    with smtplib.SMTP_SSL(server, port, timeout=30) as smtp:
        smtp.login(user, password)
        smtp.send_message(message)
    print(f"[OK] Email delivered to {recipient}")


def main():
    parser = argparse.ArgumentParser(description="Collect IT news, create reports/video, optionally email them.")
    parser.add_argument("--count", type=int, default=5, help="Number of top stories (default 5)")
    parser.add_argument("--hours", type=int, default=48, help="Lookback hours (default 48)")
    parser.add_argument("--no-video", action="store_true", help="Skip MP4 generation")
    parser.add_argument("--no-email", action="store_true", help="Skip email delivery")
    parser.add_argument("--output", default="news_output", help="Output folder")
    args = parser.parse_args()
    now = datetime.now(TZ)
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    stories = []
    for source, url in FEEDS.items():
        stories.extend(fetch_feed(source, url))
    chosen = select_stories(stories, max(1, args.count), max(1, args.hours))
    print(f"[INFO] Selected {len(chosen)} news stories")
    txt, webpage, data = save_reports(chosen, output, now)
    print(f"[OK] Reports: {txt}, {webpage}, {data}")
    video = None if args.no_video else create_video(chosen, output, now)
    if not args.no_email:
        try:
            send_email(txt, webpage, video, now)
        except Exception as exc:
            print(f"[ERROR] Email failed: {exc}")
            raise SystemExit(1) from exc
    print("[DONE] News automation complete")


if __name__ == "__main__":
    main()
