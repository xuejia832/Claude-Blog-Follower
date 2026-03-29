"""Send weekly digest emails via SMTP."""

import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from jinja2 import Environment, FileSystemLoader

from . import config
from .utils import parse_json_field


def render_weekly_email(articles: list) -> str:
    """Render weekly digest HTML from article list."""
    env = Environment(loader=FileSystemLoader(str(config.TEMPLATE_DIR)))
    template = env.get_template("weekly.html")

    processed = []
    for a in articles:
        article = dict(a)
        article["key_tech_list"] = parse_json_field(article.get("key_tech", "[]"))
        processed.append(article)

    today = datetime.now()
    week_ago = today - timedelta(days=7)
    date_range = f"{week_ago.strftime('%m/%d')} - {today.strftime('%m/%d')}"

    return template.render(articles=processed, date_range=date_range)


def send_email(subject: str, html_body: str):
    """Send an HTML email via SMTP."""
    if not config.SMTP_USER or not config.EMAIL_TO:
        raise ValueError(
            "Email not configured. Please set SMTP_USER, SMTP_PASS, EMAIL_TO in .env"
        )

    msg = MIMEMultipart("alternative")
    msg["From"] = config.SMTP_USER
    msg["To"] = config.EMAIL_TO
    msg["Subject"] = subject

    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
        server.starttls()
        server.login(config.SMTP_USER, config.SMTP_PASS)
        server.send_message(msg)


def send_weekly_digest(articles: list):
    """Render and send weekly digest email.

    Args:
        articles: List of new articles (sqlite3.Row or dict).
    """
    if not articles:
        return False

    html = render_weekly_email(articles)
    today = datetime.now().strftime("%Y-%m-%d")
    subject = f"Anthropic 博客周报 - {today}"
    send_email(subject, html)
    return True
