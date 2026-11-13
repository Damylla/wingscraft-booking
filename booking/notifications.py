"""Server-side email notification integration for Wingscraft Booking."""
from __future__ import annotations
import html
import logging
import os
import smtplib
import ssl
import threading
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from .core import connect

logger = logging.getLogger('wingscraft.notifications')
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s %(name)s: %(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RECIPIENT = 'wingscraft.studio@gmail.com'

_notify_lock = threading.Lock()
_in_flight_bookings: set[int] = set()

_PLACEHOLDER_SECRETS = {
    '',
    'REPLACE_WITH_GMAIL_APP_PASSWORD',
    'YOUR_16_CHAR_GMAIL_APP_PASSWORD',
    'REPLACE_WITH_APP_PASSWORD',
    'changeme'
}


def load_dotenv(env_path: Path | str | None = None) -> None:
    """Lightweight dependency-free .env loader."""
    path = Path(env_path) if env_path else (PROJECT_ROOT / '.env')
    if not path.is_file():
        return
    try:
        for raw_line in path.read_text(encoding='utf-8').splitlines():
            line = raw_line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, val = line.split('=', 1)
            key = key.strip()
            val = val.strip()
            if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
                val = val[1:-1]
            if key:
                os.environ.setdefault(key, val)
    except OSError as exc:
        logger.warning('Could not read .env file: %s', type(exc).__name__)


def _clean_header(value: str) -> str:
    """Prevent header injection by stripping CR/LF characters."""
    return str(value or '').replace('\r', ' ').replace('\n', ' ').strip()


def _format_display_datetime(start_at: str, end_at: str) -> tuple[str, str]:
    """Return human-friendly (date_str, time_range_str) from ISO strings."""
    try:
        start_dt = datetime.strptime(start_at, '%Y-%m-%dT%H:%M')
        date_str = start_dt.strftime('%A, %B %d, %Y') + f' ({start_dt.strftime("%Y-%m-%d")})'
        start_time = start_dt.strftime('%H:%M')
    except ValueError:
        parts = (start_at or '').split('T')
        date_str = parts[0] if parts else start_at
        start_time = parts[1] if len(parts) > 1 else ''
    end_time = (end_at or '').split('T')[1] if 'T' in (end_at or '') else ''
    time_range = f'{start_time} – {end_time}' if end_time else start_time
    return date_str, time_range


def get_booking_details(db_path: str, booking_id: int) -> dict | None:
    with connect(db_path) as db:
        row = db.execute(
            '''
            SELECT b.id AS booking_id,
                   b.service_id,
                   b.customer_name,
                   b.customer_email,
                   b.start_at,
                   b.end_at,
                   b.status,
                   b.created_at,
                   b.notification_sent_at,
                   s.name AS service_name,
                   s.duration_minutes
            FROM bookings b
            JOIN services s ON s.id = b.service_id
            WHERE b.id = ?
            ''',
            (booking_id,)
        ).fetchone()
        return dict(row) if row else None


def build_booking_email(
    booking: dict,
    recipient: str | None = None,
    sender: str | None = None
) -> EmailMessage:
    """Construct a safely escaped plain-text + HTML email matching Wingscraft design."""
    to_addr = _clean_header(
        recipient or os.environ.get('BOOKING_NOTIFY_EMAIL', DEFAULT_RECIPIENT) or DEFAULT_RECIPIENT
    )
    from_addr = _clean_header(
        sender or os.environ.get('SMTP_FROM_EMAIL') or os.environ.get('SMTP_USER') or to_addr
    )

    booking_id = booking['booking_id']
    service_name = str(booking.get('service_name') or f"Service #{booking.get('service_id', '')}")
    duration_minutes = int(booking.get('duration_minutes') or 30)
    customer_name = str(booking.get('customer_name') or '')
    customer_email = str(booking.get('customer_email') or '')
    start_at = str(booking.get('start_at') or '')
    end_at = str(booking.get('end_at') or '')

    date_display, time_display = _format_display_datetime(start_at, end_at)

    # Escape all user/dynamic fields for HTML safety
    esc_ref = html.escape(f'#{booking_id}', quote=True)
    esc_service = html.escape(service_name, quote=True)
    esc_duration = html.escape(f'{duration_minutes} minutes', quote=True)
    esc_date = html.escape(date_display, quote=True)
    esc_time = html.escape(time_display, quote=True)
    esc_name = html.escape(customer_name, quote=True)
    esc_email = html.escape(customer_email, quote=True)

    subject = _clean_header(
        f'[Wingscraft Booking] New Reservation #{booking_id} — {service_name} ({start_at.replace("T", " ")})'
    )

    plain_body = (
        f'WINGSCRAFT BOOKING — NEW RESERVATION CONFIRMED\n'
        f'================================================\n\n'
        f'Booking Reference : #{booking_id}\n'
        f'Service           : {service_name} ({duration_minutes} minutes)\n'
        f'Date              : {date_display}\n'
        f'Time              : {time_display} (Studio local time)\n'
        f'Customer Name     : {customer_name}\n'
        f'Customer Email    : {customer_email}\n\n'
        f'Manage reservations in your local Wingscraft Admin Workspace.\n'
    )

    html_body = f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{html.escape(subject, quote=True)}</title>
</head>
<body style="margin:0;padding:32px 16px;background-color:#10110f;color:#f4ebdd;font-family:Inter,-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:580px;margin:0 auto;background-color:#201f1b;border:1px solid #514637;border-radius:20px;overflow:hidden;">
    <tr>
      <td style="padding:32px 36px 24px;border-bottom:1px solid #352f25;">
        <div style="font-size:11px;letter-spacing:0.2em;color:#c8ab7c;font-weight:700;text-transform:uppercase;margin-bottom:10px;">
          &#10035; WINGSCRAFT / BOOKING
        </div>
        <h1 style="margin:0;font-size:26px;font-weight:600;letter-spacing:-0.03em;color:#f4ebdd;">
          New Reservation <span style="color:#c8ab7c;">Confirmed.</span>
        </h1>
        <p style="margin:8px 0 0;font-size:13px;color:#bfb6a5;line-height:1.6;">
          A new session has been scheduled and locked into the studio calendar.
        </p>
      </td>
    </tr>
    <tr>
      <td style="padding:28px 36px;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:#171714;border:1px solid #493f32;border-radius:14px;padding:8px 20px;">
          <tr>
            <td style="padding:14px 0;border-bottom:1px solid #2a2720;font-size:12px;color:#bfb6a5;text-transform:uppercase;letter-spacing:0.08em;">Booking Reference</td>
            <td style="padding:14px 0;border-bottom:1px solid #2a2720;font-size:14px;font-weight:700;color:#c8ab7c;text-align:right;">{esc_ref}</td>
          </tr>
          <tr>
            <td style="padding:14px 0;border-bottom:1px solid #2a2720;font-size:12px;color:#bfb6a5;text-transform:uppercase;letter-spacing:0.08em;">Selected Service</td>
            <td style="padding:14px 0;border-bottom:1px solid #2a2720;font-size:14px;font-weight:600;color:#f4ebdd;text-align:right;">{esc_service} <span style="color:#bfb6a5;font-weight:400;">({esc_duration})</span></td>
          </tr>
          <tr>
            <td style="padding:14px 0;border-bottom:1px solid #2a2720;font-size:12px;color:#bfb6a5;text-transform:uppercase;letter-spacing:0.08em;">Date</td>
            <td style="padding:14px 0;border-bottom:1px solid #2a2720;font-size:14px;font-weight:600;color:#f4ebdd;text-align:right;">{esc_date}</td>
          </tr>
          <tr>
            <td style="padding:14px 0;border-bottom:1px solid #2a2720;font-size:12px;color:#bfb6a5;text-transform:uppercase;letter-spacing:0.08em;">Time</td>
            <td style="padding:14px 0;border-bottom:1px solid #2a2720;font-size:14px;font-weight:600;color:#c8ab7c;text-align:right;">{esc_time}</td>
          </tr>
          <tr>
            <td style="padding:14px 0;border-bottom:1px solid #2a2720;font-size:12px;color:#bfb6a5;text-transform:uppercase;letter-spacing:0.08em;">Customer Name</td>
            <td style="padding:14px 0;border-bottom:1px solid #2a2720;font-size:14px;font-weight:600;color:#f4ebdd;text-align:right;">{esc_name}</td>
          </tr>
          <tr>
            <td style="padding:14px 0;font-size:12px;color:#bfb6a5;text-transform:uppercase;letter-spacing:0.08em;">Customer Email</td>
            <td style="padding:14px 0;font-size:14px;font-weight:600;color:#f4ebdd;text-align:right;">
              <a href="mailto:{esc_email}" style="color:#c8ab7c;text-decoration:none;">{esc_email}</a>
            </td>
          </tr>
        </table>
      </td>
    </tr>
    <tr>
      <td style="padding:18px 36px 28px;border-top:1px solid #2b261e;font-size:11px;color:#bfb6a5;display:flex;justify-content:space-between;">
        <span>Wingscraft Studio · Automated Booking Notification</span>
      </td>
    </tr>
  </table>
</body>
</html>'''

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = f'Wingscraft Booking <{from_addr}>'
    msg['To'] = to_addr
    if customer_email and '@' in customer_email:
        msg['Reply-To'] = _clean_header(customer_email)
    msg.set_content(plain_body)
    msg.add_alternative(html_body, subtype='html')
    return msg


def send_booking_notification(db_path: str, booking_id: int, smtp_cls=None) -> dict:
    """
    Send a reservation notification email to wingscraft.studio@gmail.com via Gmail SMTP SSL/TLS.
    Guarantees:
    - Never raises an exception that would roll back or break a booking.
    - Prevents duplicate notifications for the same booking_id.
    - Never logs passwords or secrets.
    """
    with _notify_lock:
        if booking_id in _in_flight_bookings:
            return {'sent': False, 'reason': 'duplicate_in_flight', 'booking_id': booking_id}
        _in_flight_bookings.add(booking_id)

    try:
        booking = get_booking_details(db_path, booking_id)
        if not booking:
            logger.error('Notification skipped: booking #%s not found.', booking_id)
            return {'sent': False, 'reason': 'not_found', 'booking_id': booking_id}

        if booking.get('notification_sent_at'):
            return {'sent': False, 'reason': 'already_sent', 'booking_id': booking_id}

        host = os.environ.get('SMTP_HOST', 'smtp.gmail.com').strip() or 'smtp.gmail.com'
        try:
            port = int(os.environ.get('SMTP_PORT', '465').strip())
        except ValueError:
            port = 465
        encryption = os.environ.get('SMTP_ENCRYPTION', 'SSL').strip().upper()
        recipient = os.environ.get('BOOKING_NOTIFY_EMAIL', DEFAULT_RECIPIENT).strip() or DEFAULT_RECIPIENT
        smtp_user = (os.environ.get('SMTP_USER') or recipient).strip()
        # Gmail App Passwords are 16 chars (often copied with spaces like "abcd efgh ijkl mnop")
        raw_password = (
            os.environ.get('SMTP_PASSWORD')
            or os.environ.get('GMAIL_APP_PASSWORD')
            or ''
        ).strip()

        if raw_password in _PLACEHOLDER_SECRETS:
            logger.warning(
                'Notification email for booking #%s skipped: SMTP_PASSWORD is not configured in environment/.env.',
                booking_id
            )
            return {'sent': False, 'reason': 'unconfigured', 'booking_id': booking_id}

        smtp_password = raw_password.replace(' ', '')
        msg = build_booking_email(booking, recipient=recipient, sender=smtp_user)

        context = ssl.create_default_context()
        if smtp_cls is not None:
            with smtp_cls(host, port, timeout=12) as server:
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
        elif encryption in ('SSL', 'TLS', 'SSL/TLS') or port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=12, context=context) as server:
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=12) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(smtp_user, smtp_password)
                server.send_message(msg)

        with connect(db_path) as db:
            db.execute(
                "UPDATE bookings SET notification_sent_at = datetime('now') WHERE id = ? AND notification_sent_at IS NULL",
                (booking_id,)
            )

        logger.info('Booking #%s notification delivered to %s.', booking_id, recipient)
        return {'sent': True, 'booking_id': booking_id, 'recipient': recipient}

    except smtplib.SMTPAuthenticationError:
        logger.error(
            'Email delivery failed for booking #%s: Gmail SMTP authentication rejected. '
            'Verify SMTP_USER and ensure SMTP_PASSWORD is a valid 16-character Google App Password.',
            booking_id
        )
        return {'sent': False, 'reason': 'auth_error', 'booking_id': booking_id}
    except Exception as exc:
        logger.error(
            'Email delivery failed for booking #%s (%s). Reservation #%s remains confirmed in database.',
            booking_id,
            type(exc).__name__,
            booking_id
        )
        return {'sent': False, 'reason': 'delivery_error', 'error_type': type(exc).__name__, 'booking_id': booking_id}
    finally:
        with _notify_lock:
            _in_flight_bookings.discard(booking_id)
