"""Transactional mail via Resend HTTPS (cloud-friendly) or SMTP (local).
Never emails plaintext credentials or logs secrets / token links.
"""
from __future__ import annotations
import json
import smtplib
from email.message import EmailMessage
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from .config import (MAIL_FROM, RESEND_API_KEY, SMTP_HOST, SMTP_PORT,
                     SMTP_USERNAME, SMTP_PASSWORD)

def email_ready() -> bool:
    return bool(MAIL_FROM and (RESEND_API_KEY or (SMTP_HOST and SMTP_USERNAME and SMTP_PASSWORD)))

def send_transactional_email(recipient: str, subject: str, text: str) -> bool:
    if not email_ready():
        return False
    try:
        if RESEND_API_KEY:
            payload = json.dumps({'from': MAIL_FROM, 'to': [recipient],
                                  'subject': subject, 'text': text}, ensure_ascii=False).encode('utf-8')
            req = Request('https://api.resend.com/emails', payload,
                          {'Authorization': 'Bearer ' + RESEND_API_KEY,
                           'Content-Type': 'application/json'}, method='POST')
            with urlopen(req, timeout=12) as r:
                return 200 <= r.status < 300
        msg = EmailMessage()
        msg['From'] = MAIL_FROM
        msg['To'] = recipient
        msg['Subject'] = subject
        msg.set_content(text)
        if SMTP_PORT == 465:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=12) as server:
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.send_message(msg)
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=12) as server:
                server.starttls()
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.send_message(msg)
        return True
    except (OSError, URLError, HTTPError, smtplib.SMTPException, ValueError):
        return False
