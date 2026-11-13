import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from booking.core import initialize, get_schedule, set_schedule, availability, create_booking, BookingError, list_blocked_days, block_day, unblock_day

class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.temp.name)/'test.db')
        initialize(self.db)
    def tearDown(self): self.temp.cleanup()

    def test_weekend_can_be_opened(self):
        schedule = get_schedule(self.db)
        schedule[5]['is_open'] = 1
        set_schedule(self.db, schedule)
        day=datetime.now().date()+timedelta(days=1)
        while day.weekday()!=5: day += timedelta(days=1)
        self.assertIn('09:00', availability(self.db,1,day.isoformat())['available_times'])

    def test_schedule_conflict_protection(self):
        day=datetime.now().date()+timedelta(days=1)
        while day.weekday()>=5: day+=timedelta(days=1)
        create_booking(self.db,1,'Test','test@example.com',day.isoformat()+'T10:00')
        schedule=get_schedule(self.db)
        schedule[day.weekday()]['is_open']=0
        with self.assertRaises(BookingError): set_schedule(self.db,schedule)

    def test_block_and_unblock(self):
        day=(datetime.now().date()+timedelta(days=9)).isoformat()
        block_day(self.db,day,'Private')
        self.assertTrue(any(row['day']==day for row in list_blocked_days(self.db)))
        unblock_day(self.db,day)
        self.assertFalse(any(row['day']==day for row in list_blocked_days(self.db)))

if __name__=='__main__': unittest.main()
