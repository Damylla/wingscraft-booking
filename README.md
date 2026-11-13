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


# Wingscraft Booking System

**独立型予約管理システム | Python + SQLite + HTML/CSS/JavaScript**

Wingscraft Bookingは、お客様がサービス・日付・時間を選択して予約できるWebアプリケーションです。

管理者は予約の確認・キャンセル、営業時間の設定、休業日の管理などを行うことができます。

このシステムはWingscraftのポートフォリオサイトとは独立して動作します。

> **開発状況：** ローカル環境での開発・デモ向けMVP（最小実用製品）です。現時点では、本番環境で一般のお客様に公開することを想定していません。

---

## 1. 必要な環境

- Windows 10 / 11
- Python 3.10以上
- Webブラウザ（Chrome、Edgeなど）
- インターネット接続（ダウンロード時）

Pythonのダウンロード：

https://www.python.org/downloads/

Pythonのインストール時には、**Add Python to PATH** にチェックを入れてください。

インストール後、PowerShellで以下のコマンドを実行します。

```powershell
python --version
```

Pythonのバージョンが表示されれば準備完了です。

このプロジェクトでは、基本的に追加の `npm install` や `pip install` は必要ありません。

---

## 2. プロジェクトのダウンロード

1. GitHubのリポジトリを開きます。

   https://github.com/Damylla/wingscraft-booking

2. **Code → Download ZIP** を選択します。
3. ダウンロードしたZIPファイルを解凍します。
4. 解凍したフォルダを開きます。

以下のファイルが存在するフォルダまで移動してください。

```text
wingscraft-booking/
├── booking/
├── web/
├── tests/
├── run.py
├── START-WINDOWS.bat
├── .env.example
└── README.md
```

フォルダが二重になっている場合は、`run.py` がある階層を使用してください。

---

## 3. アプリケーションの起動

### 方法A：最も簡単な起動方法

`START-WINDOWS.bat` をダブルクリックしてください。

初回起動時に管理者キーの設定が求められる場合があります。

管理者キーは16文字以上の安全な文字列を設定してください。

入力中に文字が画面に表示されない場合がありますが、正常な動作です。

設定したキーは管理画面へのログインに使用するため、安全な場所に保管してください。

### 方法B：PowerShellから起動

`run.py` があるフォルダでPowerShellを開き、以下を実行します。

```powershell
python run.py
```

動作しない場合は、こちらを試してください。

```powershell
py -3 run.py
```

正常に起動すると、サーバーが次のアドレスで待機します。

```text
http://127.0.0.1:8080
```

アプリケーションの使用中はPowerShellを閉じないでください。

---

## 4. Webブラウザで開く

### お客様用予約ページ

http://127.0.0.1:8080/

### 管理者ダッシュボード

http://127.0.0.1:8080/admin

管理画面では、設定した管理者キーを入力してください。

これらはローカルアドレスです。アプリケーションを起動しているパソコンからアクセスできます。

サーバーを終了する場合は、PowerShellで **Ctrl + C** を押してください。

---

## 5. 主な機能

### お客様向け機能

- サービスの選択
- カレンダーから日付を選択
- 予約可能な時間帯の確認
- 予約時間の選択
- お客様情報の入力
- 予約の作成
- 予約確認画面の表示

### 管理者向け機能

- 予約一覧の確認
- 予約のフィルタリング
- 予約のキャンセル
- サービスの管理
- 営業時間の設定
- 休業日の設定
- 予約状況の確認

予約データはローカルのSQLiteデータベースに保存されます。

同じ時間帯に予約が重複しないよう、サーバー側でチェックを行います。

---

## 6. Gmail通知の設定（任意）

このシステムには、Gmail SMTPを使用した予約通知機能が含まれています。

ただし、セキュリティ上の理由により、Gmailのパスワードや認証情報はGitHubには保存されていません。

メール通知を使用しない場合、この設定は省略できます。

### Step 1：Googleアプリパスワードの作成

Googleアカウントで2段階認証を有効にしてください。

利用可能なアカウントの場合、以下からアプリパスワードを作成できます。

https://myaccount.google.com/apppasswords

通常のGoogleログインパスワードは使用しないでください。

### Step 2：環境設定ファイルを作成

プロジェクトフォルダでPowerShellを開き、以下を実行します。

```powershell
Copy-Item .env.example .env
notepad .env
```

### Step 3：メール設定を入力

`.env` ファイルに、自分が利用権限を持つメールアカウントの情報を設定します。

```dotenv
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_ENCRYPTION=SSL
SMTP_USER=YOUR_GMAIL_ADDRESS
SMTP_PASSWORD=YOUR_GOOGLE_APP_PASSWORD
BOOKING_NOTIFY_EMAIL=YOUR_NOTIFICATION_EMAIL
```

`BOOKING_ADMIN_TOKEN` には16文字以上の安全で固有の管理者キーを設定してください。

設定後、ファイルを保存してサーバーを再起動してください。

実際にテスト予約を作成し、通知メールが届くか確認します。

**セキュリティ上の注意事項**

- `.env` ファイルをGitHubにアップロードしないでください。
- Googleアプリパスワードを公開しないでください。
- 管理者キーを第三者と共有しないでください。
- 実際のお客様の個人情報を公開リポジトリに保存しないでください。

---

## 7. 自動テスト

プロジェクトフォルダで以下を実行します。

```powershell
python -m unittest discover -s tests -v
```

このコマンドで予約ロジックやAPIなどの自動テストを実行できます。

ただし、テストが成功しても、実際のメール配信や本番環境の安全性が保証されるわけではありません。

---

## 8. よくあるエラーと解決方法

### `ModuleNotFoundError: No module named 'booking'`

正しいプロジェクトフォルダでコマンドを実行しているか確認してください。

`run.py` と `booking/` が同じ階層にある必要があります。

```powershell
python run.py
```

### `python is not recognized`

Pythonがインストールされているか確認してください。

または次のコマンドを試してください。

```powershell
py -3 run.py
```

### `Address already in use`

ポート8080が別のプロセスで使用されています。

既存のサーバーを **Ctrl + C** で停止してください。

### トップページが404になる

`python run.py` でサーバーを起動しているか確認してください。

正しいURL：

http://127.0.0.1:8080/

### 管理者ログインができない

設定した `BOOKING_ADMIN_TOKEN` が正しいか確認してください。

### Gmail通知が届かない

以下を確認してください。

- `.env` の設定
- Gmailアプリパスワード
- SMTP接続情報
- インターネット接続
- サーバーのエラーログ

メール設定が完了していない場合、通知は送信されません。

---

## 9. プロジェクト構成

```text
wingscraft-booking/
├── booking/
│   ├── __init__.py
│   ├── core.py
│   ├── notifications.py
│   └── server.py
│
├── web/
│   ├── index.html
│   ├── app.js
│   ├── admin.html
│   ├── admin.js
│   └── styles.css
│
├── tests/
│   ├── test_booking.py
│   ├── test_notifications_and_api.py
│   └── test_schedule.py
│
├── run.py
├── START-WINDOWS.bat
├── .env.example
└── README.md
```

### データベースについて

アプリケーションの実行時に、以下のようなデータベースファイルが作成される場合があります。

```text
data/bookings.sqlite3
```

データベースをバックアップする場合は、先にサーバーを停止し、安全な場所にファイルをコピーしてください。

---

## 10. セキュリティと公開について

このプロジェクトは、ローカルでの開発・動作確認を目的としたMVPです。

現時点では、Pythonサーバーをそのままインターネット上に公開しないでください。

本番環境で運用する場合、以下の対策が必要です。

- HTTPSの設定
- 安全な管理者認証
- アクセス制限とレート制限
- 安全なサーバーホスティング
- データベースのバックアップ
- 個人情報の適切な保護
- プライバシーとセキュリティ対策

GitHubへのアップロードはソースコードの共有であり、バックエンドの公開ではありません。

GitHub PagesのみではPython APIやSQLiteサーバーを実行できません。

---

## 11. 開発情報

**Project:** Wingscraft Booking System

**Technology:** Python / SQLite / HTML / CSS / JavaScript

**Repository:** https://github.com/Damylla/wingscraft-booking

**Status:** Local Development / MVP

**Purpose:** Reusable Booking System Codebase
