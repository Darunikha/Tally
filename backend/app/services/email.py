"""Transactional email (password reset, verification, security notices).

Providers (EMAIL_PROVIDER):
  console - development only: prints the email to the server console (links included)
  resend  - Resend HTTP API (RESEND_API_KEY)
  smtp    - any SMTP server (SMTP_HOST/PORT/USER/PASSWORD)
  memory  - tests: appended to `OUTBOX`
Emails never contain transaction data. Failures are logged (without addresses/links) and do
not surface to the user, so responses cannot be used to probe which emails are registered.
"""
from __future__ import annotations

import html
import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage as MimeMessage

from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings

log = logging.getLogger("tally.email")

OUTBOX: list["Email"] = []  # memory provider (tests)


@dataclass
class Email:
    to: str
    subject: str
    text: str
    html: str


def email_configured() -> bool:
    s = get_settings()
    if s.email_provider == "resend":
        return bool(s.resend_api_key)
    if s.email_provider == "smtp":
        return bool(s.smtp_host)
    return s.email_provider in ("console", "memory")


async def send_email(msg: Email) -> None:
    s = get_settings()
    provider = s.email_provider
    try:
        if provider == "memory":
            OUTBOX.append(msg)
        elif provider == "console":
            if s.is_production:
                log.warning("EMAIL_PROVIDER=console in production - email '%s' was NOT sent", msg.subject)
                return
            # print (not log): the redacting log filter would mangle the link
            print(f"\n=== [dev email] To: {msg.to}\nSubject: {msg.subject}\n\n{msg.text}\n=== end email\n", flush=True)
        elif provider == "resend":
            import httpx

            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {s.resend_api_key}"},
                    json={"from": s.email_from, "to": [msg.to], "subject": msg.subject, "text": msg.text, "html": msg.html},
                )
                if r.status_code >= 300:
                    log.error("Resend rejected email '%s' (HTTP %s)", msg.subject, r.status_code)
        elif provider == "smtp":
            await run_in_threadpool(_send_smtp, msg)
        else:
            log.error("Unknown EMAIL_PROVIDER '%s'", provider)
    except Exception as exc:  # never let email failure break the request
        log.error("Sending email '%s' failed: %s", msg.subject, type(exc).__name__)


def _send_smtp(msg: Email) -> None:
    s = get_settings()
    m = MimeMessage()
    m["From"], m["To"], m["Subject"] = s.email_from, msg.to, msg.subject
    m.set_content(msg.text)
    m.add_alternative(msg.html, subtype="html")
    with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20) as smtp:
        if s.smtp_starttls:
            smtp.starttls()
        if s.smtp_user:
            smtp.login(s.smtp_user, s.smtp_password)
        smtp.send_message(m)


# ---------------------------------------------------------------- templates
def _layout(title: str, body_html: str) -> str:
    return f"""<!doctype html><html><body style="margin:0;background:#F6F6F1;font-family:Arial,Helvetica,sans-serif;color:#14213D">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:32px 16px">
<table role="presentation" width="100%" style="max-width:520px;background:#ffffff;border-radius:16px;border:1px solid #E8E8E1">
<tr><td style="padding:28px 32px">
<p style="margin:0 0 20px;font-size:20px;font-weight:800;color:#2F7D55">Tally</p>
<h1 style="margin:0 0 12px;font-size:20px">{html.escape(title)}</h1>
{body_html}
<p style="margin:28px 0 0;font-size:12px;color:#6B7280">You're receiving this because of activity on your Tally account.
Tally will never ask for your bank login, OTP or card details.</p>
</td></tr></table></td></tr></table></body></html>"""


def _button(link: str, label: str) -> str:
    return (f'<p style="margin:24px 0"><a href="{html.escape(link)}" style="background:#2F7D55;color:#ffffff;'
            f'text-decoration:none;padding:12px 22px;border-radius:10px;font-weight:bold;display:inline-block">'
            f'{html.escape(label)}</a></p><p style="font-size:12px;color:#6B7280;word-break:break-all">'
            f'Or paste this link into your browser:<br>{html.escape(link)}</p>')


def password_reset_email(to: str, name: str, link: str, minutes: int) -> Email:
    text = (f"Hi {name},\n\nWe received a request to reset your Tally password. Open this link to choose a new one "
            f"(valid for {minutes} minutes, single use):\n\n{link}\n\nIf you didn't ask for this, you can ignore this "
            "email - your password stays the same.\n\n- Tally")
    body = (f"<p>Hi {html.escape(name)},</p><p>We received a request to reset your Tally password. "
            f"This link works once and expires in {minutes} minutes.</p>{_button(link, 'Reset password')}"
            "<p>If you didn't ask for this, ignore this email - your password stays the same.</p>")
    return Email(to, "Reset your Tally password", text, _layout("Reset your password", body))


def verification_email(to: str, name: str, link: str, hours: int) -> Email:
    text = (f"Hi {name},\n\nWelcome to Tally! Please confirm your email address (link valid for {hours} hours):\n\n"
            f"{link}\n\nIf you didn't create a Tally account, ignore this email.\n\n- Tally")
    body = (f"<p>Hi {html.escape(name)},</p><p>Welcome to Tally! Please confirm this is your email address.</p>"
            f"{_button(link, 'Verify email')}<p>If you didn't create a Tally account, ignore this email.</p>")
    return Email(to, "Verify your email for Tally", text, _layout("Confirm your email", body))


def password_changed_email(to: str, name: str, support_hint: str) -> Email:
    text = (f"Hi {name},\n\nThe password for your Tally account was just changed and all other sessions were signed "
            f"out.\n\nIf this wasn't you, reset your password immediately at {support_hint}.\n\n- Tally")
    body = (f"<p>Hi {html.escape(name)},</p><p>The password for your Tally account was just changed and all other "
            "sessions were signed out.</p><p><b>If this wasn't you</b>, reset your password immediately using "
            f'<a href="{html.escape(support_hint)}">Forgot password</a>.</p>')
    return Email(to, "Your Tally password was changed", text, _layout("Password changed", body))
