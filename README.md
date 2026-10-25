# AttendEase — Student Attendance Tracker

A beginner-friendly Flask + SQLite web app for teacher login, student records, daily attendance, attendance percentages, low-attendance alerts, and monthly reports.

## Requirements
- Python 3.10 or newer
- pip

## Run on Windows
1. Extract this folder.
2. Open Command Prompt or PowerShell inside `student-attendance-tracker`.
3. Create a virtual environment:
   ```powershell
   py -m venv .venv
   .venv\Scripts\activate
   ```
4. Install Flask:
   ```powershell
   pip install -r requirements.txt
   ```
5. Start the app:
   ```powershell
   python app.py
   ```
6. Open `http://127.0.0.1:5000` in your browser.
7. Demo login: username `teacher`, password `ChangeMe123!`.
8. Immediately use **Password** in the navigation to change the demo password.

## Run on macOS / Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```
Then visit `http://127.0.0.1:5000`.

## How to use
1. Sign in as the teacher and change the default password.
2. Open **Students** and add a unique roll number, name, and class.
3. Open **Daily attendance**, choose the date, mark Present / Absent / Leave, then save.
4. The dashboard calculates overall attendance using Present / (Present + Absent). Leave is excluded from the denominator.
5. Students below 75% are highlighted. The threshold can be changed with the `ATTENDANCE_THRESHOLD` environment variable.
6. Open **Monthly reports**, select a month, then use **Print / Save PDF** to print or save a PDF from your browser.

## Configuration
For a local demo, the app creates `attendance.db` beside `app.py` on first run. Set these environment variables before running for a safer setup:
- `SECRET_KEY`: long, random secret used to sign sessions.
- `TEACHER_PASSWORD`: initial teacher password, used only when the database is first created.
- `ATTENDANCE_THRESHOLD`: alert threshold percentage (default `75`).
- `ATTENDANCE_DB`: optional absolute path for the SQLite database.

Example PowerShell (run before first launch):
```powershell
$env:SECRET_KEY = "replace-with-a-long-random-secret"
$env:TEACHER_PASSWORD = "replace-with-a-strong-initial-password"
$env:ATTENDANCE_THRESHOLD = "75"
python app.py
```

## Important security notes
- This is a local learning / college project, not a production-ready hosted system.
- The Flask development server is for local testing only. Do not expose it to the public internet.
- Use a strong `SECRET_KEY`, change the demo password, back up the database, and use HTTPS plus a production WSGI server before hosting.
- Student information is personal data. Store only what you need and restrict access.
- Attendance data is stored on the computer running the app; there is no cloud sync or email alert in this version.
