"""Start the local booking web application with an admin secret."""
import getpass
import os
from booking.notifications import load_dotenv

if __name__ == '__main__':
    load_dotenv()
    if not os.getenv('BOOKING_ADMIN_TOKEN') or os.getenv('BOOKING_ADMIN_TOKEN') == 'REPLACE_WITH_LONG_RANDOM_SECRET':
        print('Wingscraft Booking — local application')
        print('Enter an admin key with at least 16 characters. The key will not display.')
        os.environ['BOOKING_ADMIN_TOKEN'] = getpass.getpass('Admin key: ')
    from booking.server import main
    main()
