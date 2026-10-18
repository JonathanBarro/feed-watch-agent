"""Build the digest email and send it over SMTP."""

import logging
import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape

logger = logging.getLogger("feed-watch.notify")


def build_digest(items: list[dict], today: date, title: str) -> tuple[str, str, str]:
    """Return (subject, html_body, text_body) for the new items."""
    noun = "update" if len(items) == 1 else "updates"
    subject = f"[{title}] {len(items)} new {noun} - {today.isoformat()}"

    html_rows = "".join(
        '<li style="margin-bottom:12px">'
        f'<span style="font-size:11px;font-weight:bold;color:#225">{escape(i["feed"])}</span><br>'
        f'<strong>{escape(i["title"])}</strong><br>'
        f'<span>{escape(i["date"])}</span><br>'
        f'<span>{escape(i["summary"])}</span><br>'
        f'<a href="{escape(i["url"])}">{escape(i["url"])}</a></li>'
        for i in items
    )
    html = (
        '<html><body style="font-family:sans-serif">'
        f"<h2>{escape(title)}</h2><ul>{html_rows}</ul>"
        "<p><em>Sent automatically by feed-watch-agent.</em></p></body></html>"
    )

    text_rows = "\n".join(
        f"- [{i['feed']}] {i['title']}\n  {i['date']}\n  {i['summary']}\n  {i['url']}\n" for i in items
    )
    text = f"{title}\n\n{text_rows}\n--\nSent automatically by feed-watch-agent.\n"
    return subject, html, text


def send_email(host: str, port: int, user: str, password: str,
               recipients: list[str], subject: str, html: str, text: str) -> None:
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = user
    message["To"] = ", ".join(recipients)
    message.attach(MIMEText(text, "plain", "utf-8"))
    message.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP(host, port, timeout=30) as server:
        server.starttls()
        server.login(user, password)
        server.sendmail(user, recipients, message.as_string())
    logger.info("Email sent to %s recipient(s)", len(recipients))
