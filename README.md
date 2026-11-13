# Wingscraft Booking — Standalone booking website + admin

A complete **local-development booking MVP**, with a customer-facing booking page, admin dashboard, persistent SQLite database and API. This project is separate from the Wingscraft portfolio. It requires **Python 3.10+ only**, with **no `pip` or `npm` installation**.

## Windows: start in two steps

1. Unzip the archive, then open the inner `wingscraft-booking-codebase` folder containing `run.py`.
2. Double-click **`START-WINDOWS.bat`**, or open PowerShell in that folder and run:

   ```powershell
   python run.py
   ```

   On first launch, choose an **admin key of at least 16 characters**. Input is hidden. **Use the same key on later launches** so you can log into the dashboard. If you already set `BOOKING_ADMIN_TOKEN`, it is used automatically.

3. In a browser open:
   - **Customer booking:** http://127.0.0.1:8080/
   - **Admin dashboard:** http://127.0.0.1:8080/admin

The server must remain running in PowerShell; stop it using **Ctrl+C**. Admin dashboard asks for the key, which is stored only in the current browser tab session. Data persists in `data/bookings.sqlite3`.

## What works

- Four-step customer booking: select service, choose date & time on the interactive calendar, enter contact details, review & confirm.
- Real availability from weekly business hours, service duration, existing bookings and blocked dates.
- SQLite transactions prevent concurrent double bookings. One shared resource/calendar is used.
- Admin can view, search, filter, and cancel bookings, add services, set weekly opening hours and block/unblock dates.
- Server-side Gmail SMTP notification integration (`wingscraft.studio@gmail.com`) with Wingscraft-styled HTML emails, automatic `.env` loading, duplicate-send prevention, and fault-tolerant delivery logging.
- Customer-facing feedback for booking errors, unavailable dates and confirmations.
- Responsive dark premium interface using Wingscraft-style charcoal, cream, bronze and brown.
- API for future connection to other frontends.
- Dependency-free Python backend and JavaScript/CSS frontend.

## Windows Setup: Gmail Notification Configuration (`wingscraft.studio@gmail.com`)

1. **Generate a Google App Password**:
   - Sign in to `wingscraft.studio@gmail.com` at https://myaccount.google.com/security
   - Ensure **2-Step Verification** is turned on.
   - Open **App passwords** (https://myaccount.google.com/apppasswords), create an app password named `Wingscraft Booking`, and copy the 16-character password.
2. **Create your `.env` file on Windows**:
   - Open PowerShell inside `wingscraft-booking-codebase`:
     ```powershell
     Copy-Item .env.example .env
     notepad .env
     ```
   - Fill in `BOOKING_ADMIN_TOKEN` (at least 16 characters) and set `SMTP_PASSWORD` to your 16-character Gmail App Password:
     ```ini
     SMTP_HOST=smtp.gmail.com
     SMTP_PORT=465
     SMTP_ENCRYPTION=SSL
     BOOKING_NOTIFY_EMAIL=wingscraft.studio@gmail.com
     SMTP_USER=wingscraft.studio@gmail.com
     SMTP_PASSWORD=your_16_char_app_password
     ```
   - Save `.env` (`.gitignore` already excludes `.env` so credentials are never committed to GitHub).
3. **Start the server**:
   ```powershell
   python run.py
   ```

## Test

```powershell
python -m unittest discover -s tests -v
```

## Data and backups

SQLite database is saved at `data/bookings.sqlite3` beside `run.py`. **To back up, stop the server and copy this file** to a safe location. Do not upload the database, admin key or customer emails to public GitHub. `.gitignore` excludes `data/`.

## Technical details

- `booking/core.py`: SQLite business logic, availability, validation and transaction locking
- `booking/server.py`: local HTTP server, admin-protected endpoints and static website
- `web/index.html`, `web/app.js`: customer booking UI
- `web/admin.html`, `web/admin.js`: admin dashboard
- `web/styles.css`: visual design
- `tests/`: booking behavior and API tests

### API

Public: `GET /health`, `GET /api/services`, `GET /api/availability?service_id=1&date=YYYY-MM-DD`, `POST /api/bookings`.

Admin (requires `Authorization: Bearer <admin-key>`): `GET /api/admin/bookings`, `POST /api/admin/bookings/{id}/cancel`, `GET/POST /api/admin/blocked-days`, `DELETE /api/admin/blocked-days/{date}`, `POST /api/admin/services`, `GET/PUT /api/admin/schedule`.

Sample booking JSON: `{"service_id":1,"customer_name":"Example","customer_email":"example@example.com","start_at":"2027-01-04T10:00"}`.

## IMPORTANT: before using with real customers

**This is a working local MVP, not a production-hardened public SaaS.** Do **not** expose `run.py` to the public internet or deploy this server to GitHub Pages. It currently uses local business time (system timezone, not explicit IANA zones), one shared booking resource, a single static admin secret, and no email notification system. For public operation, add HTTPS, proper user authentication and sessions, per-IP rate limits, CSRF defense where applicable, business timezone / DST handling, secure hosting, backups, privacy/data-retention policies, and customer notification/cancellation workflows. Booking confirmations are shown in the browser only; no email is sent. The admin panel can **cancel** existing reservations but does not edit or reschedule them. Existing reservation data is stored in plain SQLite on the device.
