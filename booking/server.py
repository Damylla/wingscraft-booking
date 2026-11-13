"""Dependency-free local booking web app and API. Not a public production server."""
import hmac
import json
import os
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs
from .core import (initialize, list_services, availability, month_availability, create_booking, list_bookings,
                   cancel_booking, block_day, create_service, BookingError,
                   get_schedule, set_schedule, list_blocked_days, unblock_day)
from .notifications import load_dotenv, send_booking_notification

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = PROJECT_ROOT / 'web'
DB_PATH = os.environ.get('BOOKING_DB', str(PROJECT_ROOT / 'data' / 'bookings.sqlite3'))
ADMIN_TOKEN = os.environ.get('BOOKING_ADMIN_TOKEN', '')
HOST = os.environ.get('BOOKING_HOST', '127.0.0.1')
PORT = int(os.environ.get('BOOKING_PORT', '8080'))

class Handler(BaseHTTPRequestHandler):
    def response_bytes(self, code, data, content_type):
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(data)

    def reply(self, code, result):
        self.response_bytes(code, json.dumps(result, ensure_ascii=False).encode('utf-8'), 'application/json; charset=utf-8')

    def serve_static(self, path):
        files = {'/': ('index.html','text/html; charset=utf-8'),
                 '/admin': ('admin.html','text/html; charset=utf-8'),
                 '/styles.css': ('styles.css','text/css; charset=utf-8'),
                 '/app.js': ('app.js','text/javascript; charset=utf-8'),
                 '/admin.js': ('admin.js','text/javascript; charset=utf-8')}
        item = files.get(path)
        if not item:
            return self.reply(404, {'error': 'Not found'})
        filename, mime = item
        return self.response_bytes(200, (STATIC_DIR / filename).read_bytes(), mime)

    def body(self):
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            raise BookingError('Invalid request length')
        if length < 1 or length > 16384:
            raise BookingError('Request body size invalid')
        try:
            value = json.loads(self.rfile.read(length))
        except (ValueError, UnicodeDecodeError):
            raise BookingError('Invalid JSON')
        if not isinstance(value, dict):
            raise BookingError('JSON object required')
        return value

    def admin(self):
        auth = self.headers.get('Authorization', '')
        if not ADMIN_TOKEN or not hmac.compare_digest(auth, 'Bearer ' + ADMIN_TOKEN):
            self.reply(401, {'error': 'Invalid admin key'})
            return False
        return True

    def route(self, method):
        path = urlsplit(self.path).path
        try:
            if method == 'GET' and not path.startswith('/api/') and path != '/health':
                return self.serve_static(path)
            if method == 'GET' and path == '/health':
                return self.reply(200, {'status': 'ok'})
            if method == 'GET' and path == '/api/services':
                return self.reply(200, {'services': list_services(DB_PATH)})
            if method == 'GET' and path == '/api/availability':
                q = parse_qs(urlsplit(self.path).query)
                service_id = int(q.get('service_id', [''])[0])
                if 'month' in q and q['month'][0]:
                    return self.reply(200, month_availability(DB_PATH, service_id, q['month'][0]))
                return self.reply(200, availability(DB_PATH, service_id, q.get('date', [''])[0]))
            if method == 'POST' and path == '/api/bookings':
                data = self.body()
                result = create_booking(DB_PATH, int(data['service_id']), data['customer_name'], data['customer_email'], data['start_at'])
                send_booking_notification(DB_PATH, result['booking_id'])
                return self.reply(201, result)
            if path.startswith('/api/admin/'):
                if not self.admin():
                    return
                if method == 'GET' and path == '/api/admin/bookings':
                    return self.reply(200, {'bookings': list_bookings(DB_PATH)})
                if method == 'POST' and path.startswith('/api/admin/bookings/') and path.endswith('/cancel'):
                    return self.reply(200, cancel_booking(DB_PATH, int(path.split('/')[4])))
                if method == 'GET' and path == '/api/admin/blocked-days':
                    return self.reply(200, {'days': list_blocked_days(DB_PATH)})
                if method == 'POST' and path == '/api/admin/blocked-days':
                    data = self.body()
                    return self.reply(201, block_day(DB_PATH, data['date'], data.get('reason', '')))
                if method == 'DELETE' and path.startswith('/api/admin/blocked-days/'):
                    return self.reply(200, unblock_day(DB_PATH, path.rsplit('/', 1)[-1]))
                if method == 'POST' and path == '/api/admin/services':
                    data = self.body()
                    return self.reply(201, create_service(DB_PATH, data['name'], data['duration_minutes']))
                if method == 'GET' and path == '/api/admin/schedule':
                    return self.reply(200, {'schedule': get_schedule(DB_PATH)})
                if method == 'PUT' and path == '/api/admin/schedule':
                    data = self.body()
                    return self.reply(200, {'schedule': set_schedule(DB_PATH, data['schedule'])})
            return self.reply(404, {'error': 'Not found'})
        except (BookingError, KeyError, TypeError, ValueError) as e:
            self.reply(400, {'error': str(e)})
        except Exception:
            import traceback
            traceback.print_exc()
            self.reply(500, {'error': 'Internal server error'})

    def do_GET(self): self.route('GET')
    def do_POST(self): self.route('POST')
    def do_PUT(self): self.route('PUT')
    def do_DELETE(self): self.route('DELETE')


def main():
    if not ADMIN_TOKEN or len(ADMIN_TOKEN) < 16:
        raise SystemExit('BOOKING_ADMIN_TOKEN must be set to a secret at least 16 characters long. See README.')
    initialize(DB_PATH)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f'Wingscraft Booking: http://{HOST}:{PORT}/')
    print(f'Admin panel:        http://{HOST}:{PORT}/admin')
    print('Press Ctrl+C to stop. LOCAL DEVELOPMENT ONLY.')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == '__main__': main()
