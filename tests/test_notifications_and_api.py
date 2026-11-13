import io
import json
import os
import smtplib
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import booking.server as server_mod
from booking.core import (
    initialize,
    availability,
    month_availability,
    create_booking,
    block_day,
    list_bookings
)
from booking.notifications import (
    build_booking_email,
    get_booking_details,
    send_booking_notification
)


class _InMemoryHandler(server_mod.Handler):
    def __init__(self, method, path, headers=None, body_bytes=b''):
        self.path = path
        self.command = method
        self.headers = headers or {}
        self.rfile = io.BytesIO(body_bytes)
        self.wfile = io.BytesIO()
        self.status_code = None
        self.response_headers = {}

    def send_response(self, code, message=None):
        self.status_code = code

    def send_header(self, keyword, value):
        self.response_headers[keyword] = value

    def end_headers(self):
        pass


class _DummySMTP:
    instances = []
    should_fail = False

    def __init__(self, host, port, timeout=12):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.logged_in = None
        self.sent_messages = []
        _DummySMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def login(self, user, password):
        if _DummySMTP.should_fail:
            raise smtplib.SMTPAuthenticationError(535, b'Authentication failed')
        self.logged_in = (user, password)

    def send_message(self, msg):
        if _DummySMTP.should_fail:
            raise smtplib.SMTPException('Simulated delivery failure')
        self.sent_messages.append(msg)


class NotificationAndApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / 'test_api.sqlite3')
        initialize(self.db)
        d = datetime.now().date() + timedelta(days=2)
        while d.weekday() >= 5:
            d += timedelta(days=1)
        self.day = d.isoformat()
        self.month = d.strftime('%Y-%m')
        self.start = self.day + 'T10:00'
        _DummySMTP.instances.clear()
        _DummySMTP.should_fail = False
        self._orig_env = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._orig_env)
        self.tmp.cleanup()

    def test_month_and_day_availability_states(self):
        month_data = month_availability(self.db, 1, self.month)
        self.assertEqual(month_data['service_id'], 1)
        self.assertEqual(month_data['month'], self.month)
        self.assertIn(self.day, month_data['days'])
        self.assertEqual(month_data['days'][self.day]['status'], 'available')
        self.assertGreater(month_data['days'][self.day]['available_count'], 0)

        # Book 10:00 and verify unavailable_times tracks it
        create_booking(self.db, 1, 'Clara Vance', 'clara@example.com', self.start)
        day_data = availability(self.db, 1, self.day)
        self.assertNotIn('10:00', day_data['available_times'])
        self.assertIn('10:00', day_data['unavailable_times'])
        self.assertEqual(day_data['day_status'], 'available')

        # Block another future weekday and verify month_availability marks it blocked
        d2 = datetime.fromisoformat(self.day).date() + timedelta(days=1)
        while d2.weekday() >= 5:
            d2 += timedelta(days=1)
        if d2.strftime('%Y-%m') == self.month:
            block_day(self.db, d2.isoformat(), 'Studio Event')
            updated_month = month_availability(self.db, 1, self.month)
            self.assertEqual(updated_month['days'][d2.isoformat()]['status'], 'blocked')
            self.assertEqual(updated_month['days'][d2.isoformat()]['available_count'], 0)

    def test_email_generation_and_html_escaping(self):
        created = create_booking(
            self.db,
            1,
            'Clara <script>alert(1)</script>',
            'clara@example.com',
            self.start
        )
        details = get_booking_details(self.db, created['booking_id'])
        msg = build_booking_email(details)

        self.assertEqual(msg['To'], 'wingscraft.studio@gmail.com')
        self.assertIn(f"#{created['booking_id']}", msg['Subject'])
        self.assertIn('Consultation', msg['Subject'])

        plain = msg.get_body(preferencelist=('plain',)).get_content()
        html_part = msg.get_body(preferencelist=('html',)).get_content()

        self.assertIn(f"#{created['booking_id']}", plain)
        self.assertIn('Consultation', plain)
        self.assertIn('clara@example.com', plain)
        self.assertIn('10:00', plain)

        # Verify XSS payload is escaped in HTML email and Wingscraft colors are present
        self.assertNotIn('<script>alert(1)</script>', html_part)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', html_part)
        self.assertIn('#10110f', html_part)
        self.assertIn('#c8ab7c', html_part)
        self.assertIn('#f4ebdd', html_part)

    def test_duplicate_notification_prevention_and_fault_tolerance(self):
        os.environ['SMTP_HOST'] = 'smtp.gmail.com'
        os.environ['SMTP_PORT'] = '465'
        os.environ['BOOKING_NOTIFY_EMAIL'] = 'wingscraft.studio@gmail.com'
        os.environ['SMTP_USER'] = 'wingscraft.studio@gmail.com'
        os.environ['SMTP_PASSWORD'] = 'abcd efgh ijkl mnop'

        created = create_booking(self.db, 1, 'Elena Rostova', 'elena@example.com', self.start)
        bid = created['booking_id']

        first = send_booking_notification(self.db, bid, smtp_cls=_DummySMTP)
        self.assertTrue(first['sent'])
        self.assertEqual(len(_DummySMTP.instances), 1)
        self.assertEqual(_DummySMTP.instances[0].logged_in, ('wingscraft.studio@gmail.com', 'abcdefghijklmnop'))
        self.assertEqual(len(_DummySMTP.instances[0].sent_messages), 1)

        # Second call for same booking_id must be skipped (no duplicate email)
        second = send_booking_notification(self.db, bid, smtp_cls=_DummySMTP)
        self.assertFalse(second['sent'])
        self.assertEqual(second['reason'], 'already_sent')
        self.assertEqual(len(_DummySMTP.instances), 1)

        # Simulated SMTP failure must not lose or roll back the booking
        _DummySMTP.should_fail = True
        created2 = create_booking(self.db, 1, 'Marcus Vance', 'marcus@example.com', self.day + 'T11:00')
        failed_res = send_booking_notification(self.db, created2['booking_id'], smtp_cls=_DummySMTP)
        self.assertFalse(failed_res['sent'])
        all_bookings = list_bookings(self.db)
        self.assertEqual(len(all_bookings), 2)

    def _call_route(self, method, path, headers=None, json_body=None):
        body_bytes = b''
        req_headers = dict(headers or {})
        if json_body is not None:
            body_bytes = json.dumps(json_body).encode('utf-8')
            req_headers['Content-Length'] = str(len(body_bytes))
            req_headers['Content-Type'] = 'application/json'
        h = _InMemoryHandler(method, path, headers=req_headers, body_bytes=body_bytes)
        h.route(method)
        return h.status_code, h.wfile.getvalue().decode('utf-8')

    def test_http_endpoints_and_static_assets(self):
        server_mod.DB_PATH = self.db
        server_mod.ADMIN_TOKEN = 'test_secret_token_12345'
        os.environ.pop('SMTP_PASSWORD', None)

        # Verify static pages load
        code, html_index = self._call_route('GET', '/')
        self.assertEqual(code, 200)
        self.assertIn('step4', html_index)
        self.assertIn('cal-grid', html_index)

        code_adm, html_adm = self._call_route('GET', '/admin')
        self.assertEqual(code_adm, 200)
        self.assertIn('filter-search', html_adm)

        # Verify month availability endpoint
        code_m, raw_m = self._call_route('GET', f'/api/availability?service_id=1&month={self.month}')
        self.assertEqual(code_m, 200)
        m_json = json.loads(raw_m)
        self.assertEqual(m_json['month'], self.month)
        self.assertIn(self.day, m_json['days'])

        # Verify booking creation via POST /api/bookings
        code_b, raw_b = self._call_route(
            'POST',
            '/api/bookings',
            json_body={
                'service_id': 1,
                'customer_name': 'Aria Montgomery',
                'customer_email': 'aria@example.com',
                'start_at': self.start
            }
        )
        self.assertEqual(code_b, 201)
        b_json = json.loads(raw_b)
        self.assertEqual(b_json['status'], 'confirmed')

        # Verify admin bookings endpoint requires auth and lists booking
        code_unauth, _ = self._call_route('GET', '/api/admin/bookings')
        self.assertEqual(code_unauth, 401)

        code_list, raw_list = self._call_route(
            'GET',
            '/api/admin/bookings',
            headers={'Authorization': 'Bearer test_secret_token_12345'}
        )
        self.assertEqual(code_list, 200)
        adm_json = json.loads(raw_list)
        self.assertEqual(len(adm_json['bookings']), 1)
        self.assertEqual(adm_json['bookings'][0]['customer_name'], 'Aria Montgomery')


if __name__ == '__main__':
    unittest.main()
