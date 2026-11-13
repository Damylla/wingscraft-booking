"""SQLite-backed booking engine. Times are local ISO strings (YYYY-MM-DDTHH:MM)."""
from __future__ import annotations
import calendar
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

OPEN_HOUR = 9
CLOSE_HOUR = 18
SLOT_MINUTES = 30

class BookingError(ValueError):
    pass


class _ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            return super().__exit__(exc_type, exc_val, exc_tb)
        finally:
            self.close()


def connect(db_path: str):
    db = sqlite3.connect(db_path, timeout=10, isolation_level=None, factory=_ClosingConnection)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA busy_timeout=10000')
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA journal_mode=WAL')
    return db


def initialize(db_path: str):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with connect(db_path) as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS services (
          id INTEGER PRIMARY KEY,
          name TEXT NOT NULL,
          duration_minutes INTEGER NOT NULL CHECK(duration_minutes > 0),
          active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS bookings (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          service_id INTEGER NOT NULL REFERENCES services(id),
          customer_name TEXT NOT NULL,
          customer_email TEXT NOT NULL,
          start_at TEXT NOT NULL,
          end_at TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'confirmed' CHECK(status IN ('confirmed','cancelled')),
          created_at TEXT NOT NULL DEFAULT (datetime('now')),
          notification_sent_at TEXT DEFAULT NULL
        );
        CREATE INDEX IF NOT EXISTS booking_time_idx ON bookings(start_at, end_at, status);
        CREATE TABLE IF NOT EXISTS blocked_days (
          day TEXT PRIMARY KEY,
          reason TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS weekly_hours (
          weekday INTEGER PRIMARY KEY CHECK(weekday BETWEEN 0 AND 6),
          open_time TEXT NOT NULL,
          close_time TEXT NOT NULL,
          is_open INTEGER NOT NULL DEFAULT 1
        );
        ''')
        cols = {row['name'] for row in db.execute('PRAGMA table_info(bookings)')}
        if 'notification_sent_at' not in cols:
            db.execute('ALTER TABLE bookings ADD COLUMN notification_sent_at TEXT DEFAULT NULL')
        db.execute("INSERT OR IGNORE INTO services (id,name,duration_minutes,active) VALUES (1,'Consultation',30,1)")
        for weekday in range(7):
            db.execute('INSERT OR IGNORE INTO weekly_hours(weekday,open_time,close_time,is_open) VALUES (?,?,?,?)',
                       (weekday,'09:00','18:00',int(weekday < 5)))


def parse_day(value: str):
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError
        return parsed
    except (ValueError, TypeError):
        raise BookingError('Date must be YYYY-MM-DD')


def parse_start(value: str):
    try:
        parsed = datetime.strptime(value, '%Y-%m-%dT%H:%M')
        if parsed.strftime('%Y-%m-%dT%H:%M') != value:
            raise ValueError
        return parsed
    except (ValueError, TypeError):
        raise BookingError('start_at must be YYYY-MM-DDTHH:MM')


def _service(db, service_id):
    row = db.execute('SELECT * FROM services WHERE id=? AND active=1', (service_id,)).fetchone()
    if not row:
        raise BookingError('Service not found or inactive')
    return row


def _hours(db, weekday):
    return db.execute('SELECT * FROM weekly_hours WHERE weekday=?', (weekday,)).fetchone()


def get_schedule(db_path):
    with connect(db_path) as db:
        return [dict(row) for row in db.execute('SELECT * FROM weekly_hours ORDER BY weekday')]


def _minute(value):
    try:
        hh, mm = value.split(':')
        if len(value) != 5 or not hh.isdigit() or not mm.isdigit(): raise ValueError
        hour, minute = int(hh), int(mm)
        if hour > 23 or minute > 59 or minute % 30: raise ValueError
        return hour * 60 + minute
    except (ValueError, TypeError, AttributeError):
        raise BookingError('Hours must be HH:MM, aligned to 30-minute intervals')


def set_schedule(db_path, schedule):
    if not isinstance(schedule, list) or len(schedule) != 7:
        raise BookingError('Provide all seven weekdays')
    checked = []
    for i, entry in enumerate(schedule):
        if not isinstance(entry, dict) or type(entry.get('weekday')) is not int or entry['weekday'] != i:
            raise BookingError('Weekdays must be ordered from 0 to 6')
        opened = entry.get('is_open')
        if type(opened) not in (bool, int) or opened not in (0, 1, True, False):
            raise BookingError('Invalid day status')
        o, c = entry.get('open_time'), entry.get('close_time')
        first, last = _minute(o), _minute(c)
        if first >= last or last - first < 30:
            raise BookingError('Closing time must be after opening time')
        checked.append((i, o, c, int(opened)))
    with connect(db_path) as db:
        db.execute('BEGIN IMMEDIATE')
        try:
            # Existing reservations must remain valid under new opening hours.
            for item in db.execute("SELECT start_at, end_at FROM bookings WHERE status='confirmed'"):
                start, end = parse_start(item['start_at']), parse_start(item['end_at'])
                weekday = start.weekday()
                _, o, c, enabled = checked[weekday]
                clock = start.hour*60 + start.minute
                finish = end.hour*60 + end.minute
                if not enabled or clock < _minute(o) or finish > _minute(c):
                    raise BookingError('New hours conflict with existing confirmed bookings; cancel them first')
            for row in checked:
                db.execute('UPDATE weekly_hours SET open_time=?,close_time=?,is_open=? WHERE weekday=?',
                           (row[1],row[2],row[3],row[0]))
            db.execute('COMMIT')
        except Exception:
            db.execute('ROLLBACK')
            raise
    return get_schedule(db_path)


def list_blocked_days(db_path):
    with connect(db_path) as db:
        return [dict(x) for x in db.execute('SELECT day,reason FROM blocked_days ORDER BY day DESC')]


def unblock_day(db_path, day):
    parse_day(day)
    with connect(db_path) as db:
        db.execute('DELETE FROM blocked_days WHERE day=?', (day,))
    return {'date': day, 'blocked': False}


def _valid_slot(db, start, duration):
    if start.date() < datetime.now().date():
        return False
    hours = _hours(db, start.weekday())
    if not hours or not hours['is_open']:
        return False
    if db.execute('SELECT 1 FROM blocked_days WHERE day=?', (start.date().isoformat(),)).fetchone():
        return False
    end = start + timedelta(minutes=duration)
    if start.hour*60 + start.minute < _minute(hours['open_time']) or start.minute % SLOT_MINUTES != 0:
        return False
    if end.date() != start.date() or end.hour*60 + end.minute > _minute(hours['close_time']):
        return False
    if start < datetime.now():
        return False
    return True


def _overlap(db, start, end):
    return db.execute('''
        SELECT 1 FROM bookings WHERE status='confirmed' AND start_at < ? AND end_at > ? LIMIT 1
    ''', (end.isoformat(timespec='minutes'), start.isoformat(timespec='minutes'))).fetchone() is not None


def list_services(db_path):
    with connect(db_path) as db:
        return [dict(x) for x in db.execute('SELECT id,name,duration_minutes FROM services WHERE active=1 ORDER BY id')]


def availability(db_path, service_id: int, day: str):
    d = parse_day(day)
    with connect(db_path) as db:
        service = _service(db, service_id)
        result = []
        unavailable = []
        today_date = datetime.now().date()
        is_blocked = db.execute('SELECT 1 FROM blocked_days WHERE day=?', (day,)).fetchone() is not None
        hours = _hours(db, d.weekday())
        if d < today_date:
            return {'service_id':service_id,'date':day,'timezone':'business local time', 'available_times':[], 'unavailable_times':[], 'day_status':'past'}
        if is_blocked:
            return {'service_id':service_id,'date':day,'timezone':'business local time', 'available_times':[], 'unavailable_times':[], 'day_status':'blocked'}
        if not hours or not hours['is_open']:
            return {'service_id':service_id,'date':day,'timezone':'business local time', 'available_times':[], 'unavailable_times':[], 'day_status':'closed'}
        open_min = _minute(hours['open_time'])
        close_min = _minute(hours['close_time'])
        duration = service['duration_minutes']
        for minute in range(open_min, close_min, SLOT_MINUTES):
            start = datetime.combine(d, datetime.min.time()) + timedelta(minutes=minute)
            end = start + timedelta(minutes=duration)
            if end.date() != start.date() or (end.hour * 60 + end.minute) > close_min:
                continue
            slot_label = start.strftime('%H:%M')
            if _valid_slot(db, start, duration) and not _overlap(db, start, end):
                result.append(slot_label)
            else:
                unavailable.append(slot_label)
        status = 'available' if result else 'unavailable'
        return {'service_id':service_id,'date':day,'timezone':'local business time (configure before production)', 'available_times':result, 'unavailable_times':unavailable, 'day_status':status}


def month_availability(db_path, service_id: int, month: str):
    try:
        if not isinstance(month, str) or len(month) != 7 or month[4] != '-':
            raise ValueError
        year, mon = int(month[:4]), int(month[5:7])
        if not (1 <= mon <= 12):
            raise ValueError
    except (ValueError, TypeError):
        raise BookingError('Month must be YYYY-MM')
    _, num_days = calendar.monthrange(year, mon)
    days_out = {}
    with connect(db_path) as db:
        service = _service(db, service_id)
        duration = service['duration_minutes']
        hours_map = {row['weekday']: row for row in db.execute('SELECT * FROM weekly_hours')}
        first_iso = f'{year:04d}-{mon:02d}-01'
        last_iso = f'{year:04d}-{mon:02d}-{num_days:02d}'
        blocked_set = {
            row['day'] for row in db.execute(
                'SELECT day FROM blocked_days WHERE day >= ? AND day <= ?',
                (first_iso, last_iso)
            )
        }
        now = datetime.now()
        today_date = now.date()
        for day_num in range(1, num_days + 1):
            d = date(year, mon, day_num)
            day_iso = d.isoformat()
            if d < today_date:
                days_out[day_iso] = {'status': 'past', 'available_count': 0}
                continue
            if day_iso in blocked_set:
                days_out[day_iso] = {'status': 'blocked', 'available_count': 0}
                continue
            hours = hours_map.get(d.weekday())
            if not hours or not hours['is_open']:
                days_out[day_iso] = {'status': 'closed', 'available_count': 0}
                continue
            open_min = _minute(hours['open_time'])
            close_min = _minute(hours['close_time'])
            count = 0
            for minute in range(open_min, close_min, SLOT_MINUTES):
                start = datetime.combine(d, datetime.min.time()) + timedelta(minutes=minute)
                end = start + timedelta(minutes=duration)
                if end.date() != start.date() or (end.hour * 60 + end.minute) > close_min:
                    continue
                if start < now:
                    continue
                if not _overlap(db, start, end):
                    count += 1
            days_out[day_iso] = {
                'status': 'available' if count > 0 else 'unavailable',
                'available_count': count
            }
    return {'service_id': service_id, 'month': month, 'days': days_out}


def create_booking(db_path, service_id, customer_name, customer_email, start_at):
    if not isinstance(customer_name, str) or not (1 <= len(customer_name.strip()) <= 100):
        raise BookingError('Name must be between 1 and 100 characters')
    if not isinstance(customer_email, str) or len(customer_email) > 254 or '@' not in customer_email or customer_email.startswith('@'):
        raise BookingError('Valid email is required')
    start = parse_start(start_at)
    with connect(db_path) as db:
        db.execute('BEGIN IMMEDIATE')  # serializes competing SQLite writes
        try:
            service = _service(db, service_id)
            duration = service['duration_minutes']
            end = start + timedelta(minutes=duration)
            if not _valid_slot(db, start, duration):
                raise BookingError('Time is outside availability')
            if _overlap(db, start, end):
                raise BookingError('Time is already booked')
            cursor = db.execute('''INSERT INTO bookings (service_id, customer_name, customer_email, start_at, end_at)
               VALUES (?,?,?,?,?)''', (service_id,customer_name.strip(),customer_email.strip(),start.isoformat(timespec='minutes'),end.isoformat(timespec='minutes')))
            db.execute('COMMIT')
            return {'booking_id':cursor.lastrowid,'status':'confirmed','start_at':start_at,'end_at':end.isoformat(timespec='minutes')}
        except Exception:
            db.execute('ROLLBACK')
            raise


def list_bookings(db_path):
    with connect(db_path) as db:
        return [dict(x) for x in db.execute('SELECT * FROM bookings ORDER BY start_at DESC')]


def cancel_booking(db_path, booking_id):
    with connect(db_path) as db:
        cursor = db.execute("UPDATE bookings SET status='cancelled' WHERE id=? AND status='confirmed'", (booking_id,))
        if cursor.rowcount == 0:
            raise BookingError('Confirmed booking not found')
        return {'booking_id':booking_id,'status':'cancelled'}


def block_day(db_path, day, reason=''):
    parse_day(day)
    with connect(db_path) as db:
        # Do not silently invalidate existing confirmed bookings.
        if db.execute("SELECT 1 FROM bookings WHERE status='confirmed' AND substr(start_at,1,10)=? LIMIT 1", (day,)).fetchone():
            raise BookingError('Cancel existing reservations before blocking this day')
        db.execute('INSERT OR REPLACE INTO blocked_days (day,reason) VALUES (?,?)', (day,reason))
    return {'date':day,'blocked':True}


def create_service(db_path, name, duration_minutes):
    if not isinstance(name,str) or not (1 <= len(name.strip()) <= 100):
        raise BookingError('Invalid service name')
    if type(duration_minutes) is not int or duration_minutes not in (30,60,90,120):
        raise BookingError('Duration must be 30, 60, 90, or 120 minutes')
    with connect(db_path) as db:
        cursor = db.execute('INSERT INTO services(name,duration_minutes) VALUES (?,?)',(name.strip(),duration_minutes))
        return {'id':cursor.lastrowid,'name':name.strip(),'duration_minutes':duration_minutes}
