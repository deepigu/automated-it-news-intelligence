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
                        candidate = element.attrib['href']
                        if candidate.startswith(('http://', 'https://')):
                            link = candidate
                            if element.attrib.get('rel', 'alternate') == 'alternate':
                                break
            published = parse_date(child_text(entry, 'pubDate') or child_text(entry, 'published') or child_text(entry, 'updated'))
            if title and link:
                articles.append({'title': title, 'summary': summary, 'url': link,
                                 'source': source, 'published': published})
        print(f'[OK] {source}: {len(articles)} articles')
        return articles
    except Exception as exc:
        print(f'[WARN] Could not fetch {source}: {exc}')
        return []


def score_article(article: dict) -> float:
    title = article['title'].lower()
    summary = article['summary'].lower()
    score = 0.0
    for keyword, weight in KEYWORDS.items():
        pattern = r'(?<!\w)' + re.escape(keyword) + r'(?!\w)'
        if re.search(pattern, title):
            score += weight * 2
        elif re.search(pattern, summary):
            score += weight
    published = article.get('published')
    if published:
        age_hours = max(0, (datetime.now(timezone.utc) - published.astimezone(timezone.utc)).total_seconds() / 3600)
        if age_hours < 24:
            score += 5
        elif age_hours < 72:
            score += 2
    return score


def choose_articles(all_articles: list[dict], limit: int = 5) -> list[dict]:
    unique = {}
    for article in all_articles:
        key = re.sub(r'[^a-z0-9]+', '', article['title'].lower())
        if key and key not in unique:
            article['score'] = score_article(article)
            unique[key] = article
    ranked = sorted(unique.values(), key=lambda a: (a['score'], a['published'] or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
    return ranked[:limit]


def serialize(article: dict) -> dict:
    return {
        'title': article['title'], 'summary': article['summary'][:600],
        'url': article['url'], 'source': article['source'],
        'published': article['published'].isoformat() if article['published'] else None,
        'score': article['score'],
    }


def make_reports(articles: list[dict], now: datetime) -> tuple[Path, Path, Path]:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    date_str = now.strftime('%Y-%m-%d')
    prefix = OUTPUT / f'IT_News_{date_str}'
    text_path = prefix.with_suffix('.txt')
    html_path = prefix.with_suffix('.html')
    json_path = prefix.with_suffix('.json')

    payload = {
        'date': date_str,
        'generated_at': now.isoformat(),
        'timezone': 'America/Toronto',
        'total_articles': len(articles),
        'articles': [serialize(a) for a in articles],
    }
    json_text = json.dumps(payload, ensure_ascii=False, indent=2)
    json_path.write_text(json_text, encoding='utf-8')
    WEBSITE_JSON.parent.mkdir(parents=True, exist_ok=True)
    WEBSITE_JSON.write_text(json_text, encoding='utf-8')

    lines = [f'DAILY IT NEWS — {date_str}', '']
    for index, article in enumerate(articles, 1):
        lines.extend([f'{index}. {article["title"]}', f'   Source: {article["source"]}',
                      f'   {article["summary"][:350]}', f'   {article["url"]}', ''])
    text_path.write_text('\n'.join(lines), encoding='utf-8')

    cards = []
    for article in articles:
        cards.append('<article style="padding:18px;margin:14px 0;background:#14263d;border-radius:12px">'
                     f'<h2 style="margin:0 0 8px"><a style="color:#8dd5ff" href="{html.escape(article["url"], quote=True)}">{html.escape(article["title"])}</a></h2>'
                     f'<small>{html.escape(article["source"])}</small>'
                     f'<p>{html.escape(article["summary"][:450])}</p></article>')
    html_doc = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width,initial-scale=1">'
                f'<title>Daily IT News {date_str}</title></head>'
                '<body style="font-family:Arial,sans-serif;background:#091626;color:#f5f7fa;max-width:850px;margin:30px auto;padding:15px">'
                f'<h1>Daily IT News — {date_str}</h1>{"".join(cards)}</body></html>')
    html_path.write_text(html_doc, encoding='utf-8')
    print(f'[OK] Reports saved to {OUTPUT}')
    print(f'[OK] Dashboard JSON saved to {WEBSITE_JSON}')
    return text_path, html_path, json_path


def get_recipients() -> list[str]:
    raw = os.getenv('NEWS_EMAIL_TO', '')
    recipients_file = ROOT / 'recipients.txt'
    if recipients_file.exists():
        raw += '\n' + recipients_file.read_text(encoding='utf-8')
    recipients = []
    for value in re.split(r'[,;\n]+', raw):
        address = value.strip()
        if address and not address.startswith('#') and address not in recipients:
            recipients.append(address)
    return recipients


def get_password(sender: str) -> str:
    password = os.getenv('NEWS_EMAIL_PASSWORD', '') or os.getenv('GMAIL_APP_PASSWORD', '')
    if password:
        return password.replace(' ', '')
    try:
        import keyring  # optional Windows-only fallback
        for service in ('it_news_intelligence', 'IT News Intelligence', 'gmail', 'Gmail'):
            password = keyring.get_password(service, sender)
            if password:
                return password.replace(' ', '')
    except (ImportError, Exception):
        pass
    return ''


def send_email(articles: list[dict], text_path: Path, html_path: Path, *, skip: bool = False) -> None:
    if skip:
        print('[INFO] Email disabled by --no-email')
        return
    sender = os.getenv('NEWS_EMAIL_USER', '').strip()
    recipients = get_recipients()
    password = get_password(sender) if sender else ''
    if not sender or not recipients or not password:
        missing = [name for name, present in [('NEWS_EMAIL_USER', bool(sender)),
                    ('NEWS_EMAIL_TO or recipients.txt', bool(recipients)),
                    ('NEWS_EMAIL_PASSWORD', bool(password))] if not present]
        print('[WARN] Email skipped. Missing: ' + ', '.join(missing))
        return
    message = EmailMessage()
    message['Subject'] = f'Daily IT News Intelligence — {datetime.now(TZ):%Y-%m-%d}'
    message['From'] = sender
    message['To'] = ', '.join(recipients)
    message.set_content(text_path.read_text(encoding='utf-8'))
    message.add_alternative(html_path.read_text(encoding='utf-8'), subtype='html')
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=30) as smtp:
            smtp.login(sender, password)
            smtp.send_message(message)
        print(f'[OK] Email sent to {len(recipients)} recipient(s)')
    except (smtplib.SMTPException, OSError) as exc:
        raise RuntimeError(f'Email delivery failed: {exc}') from exc


def make_video(articles: list[dict], now: datetime) -> None:
    ffmpeg = shutil.which('ffmpeg')
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print('[INFO] Video skipped: install Pillow (pip install pillow)')
        return
    if not ffmpeg:
        print('[INFO] Video skipped: FFmpeg is not installed or not in PATH')
        return
    if not articles:
        return
    output_path = OUTPUT / f'IT_News_{now:%Y-%m-%d}.mp4'
    with tempfile.TemporaryDirectory() as directory:
        frames = Path(directory)
        try:
            font = ImageFont.truetype('DejaVuSans.ttf', 38)
            small_font = ImageFont.truetype('DejaVuSans.ttf', 25)
        except OSError:
            font = ImageFont.load_default()
            small_font = ImageFont.load_default()
        for index, article in enumerate(articles):
            image = Image.new('RGB', (1280, 720), '#0b1930')
            draw = ImageDraw.Draw(image)
            draw.text((70, 65), f'IT NEWS  •  {now:%Y-%m-%d}', font=small_font, fill='#7dd3fc')
            title_lines = textwrap.wrap(article['title'], width=40)[:4]
            draw.multiline_text((70, 155), '\n'.join(title_lines), font=font, fill='white', spacing=18)
            summary_lines = textwrap.wrap(article['summary'][:240], width=73)[:4]
            draw.multiline_text((70, 410), '\n'.join(summary_lines), font=small_font, fill='#c9d9eb', spacing=12)
            draw.text((70, 645), f'{article["source"]}  |  {index + 1}/{len(articles)}', font=small_font, fill='#7dd3fc')
            image.save(frames / f'frame_{index:03d}.png')
        command = [ffmpeg, '-y', '-loglevel', 'error', '-framerate', '1/5',
                   '-i', str(frames / 'frame_%03d.png'), '-c:v', 'libx264',
                   '-pix_fmt', 'yuv420p', '-r', '25', str(output_path)]
        try:
            subprocess.run(command, check=True, timeout=120)
            print(f'[OK] Video saved to {output_path}')
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
            print(f'[WARN] Video creation failed: {exc}')


def main() -> int:
    parser = argparse.ArgumentParser(description='Generate daily IT news reports, dashboard JSON, and email.')
    parser.add_argument('--no-video', action='store_true', help='Skip optional MP4 creation')
    parser.add_argument('--no-email', action='store_true', help='Skip sending Gmail')
    args = parser.parse_args()
    now = datetime.now(TZ)
    print(f'[INFO] Starting daily news: {now.isoformat()}')
    articles = []
    for source, url in FEEDS.items():
        articles.extend(fetch_feed(source, url))
    if not articles:
        print('[ERROR] No articles fetched from any RSS feed; not publishing empty report')
        return 1
    selected = choose_articles(articles)
    text_path, html_path, _ = make_reports(selected, now)
    if not args.no_video:
        make_video(selected, now)
    send_email(selected, text_path, html_path, skip=args.no_email)
    print(f'[OK] Finished. Selected {len(selected)} articles.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f'[ERROR] {exc}')
        raise SystemExit(1)
