import tempfile
import threading
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from booking.core import (initialize, availability, create_booking, cancel_booking, list_bookings,
                          block_day, create_service, BookingError)

class BookingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=str(Path(self.tmp.name)/'test.sqlite3')
        initialize(self.db)
        d=datetime.now().date()+timedelta(days=1)
        while d.weekday()>=5:
            d+=timedelta(days=1)
        self.day=d.isoformat()
        self.start=self.day+'T10:00'

    def tearDown(self): self.tmp.cleanup()

    def test_booking_and_availability(self):
        self.assertIn('10:00',availability(self.db,1,self.day)['available_times'])
        book=create_booking(self.db,1,'A','a@example.com',self.start)
        self.assertNotIn('10:00',availability(self.db,1,self.day)['available_times'])
        with self.assertRaises(BookingError):
            create_booking(self.db,1,'B','b@example.com',self.start)
        cancel_booking(self.db,book['booking_id'])
        self.assertIn('10:00',availability(self.db,1,self.day)['available_times'])

    def test_overlapping_durations(self):
        long_service=create_service(self.db,'Long',60)
        create_booking(self.db,long_service['id'],'A','a@example.com',self.start)
        with self.assertRaises(BookingError):
            create_booking(self.db,1,'B','b@example.com',self.day+'T10:30')

    def test_blocking_day(self):
        block_day(self.db,self.day,'Holiday')
        self.assertEqual([], availability(self.db,1,self.day)['available_times'])

    def test_block_rejects_existing_booking(self):
        create_booking(self.db,1,'A','a@example.com',self.start)
        with self.assertRaises(BookingError): block_day(self.db,self.day)

    def test_concurrent_double_booking(self):
        results=[]
        lock=threading.Lock()
        def worker():
            try:
                create_booking(self.db,1,'A','a@example.com',self.start)
                val='ok'
            except BookingError:
                val='blocked'
            with lock: results.append(val)
        threads=[threading.Thread(target=worker) for _ in range(6)]
        for t in threads:t.start()
        for t in threads:t.join()
        self.assertEqual(results.count('ok'),1)
        self.assertEqual(results.count('blocked'),5)

if __name__=='__main__': unittest.main()
