import os, sqlite3, secrets, hmac, hashlib, calendar
from datetime import date, datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, g

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.environ.get('ATTENDANCE_DB', os.path.join(BASE_DIR, 'attendance.db'))
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-only-change-this-secret-key')
THRESHOLD = int(os.environ.get('ATTENDANCE_THRESHOLD', '75'))


def db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db

@app.teardown_appcontext
def close_db(_error=None):
    conn = g.pop('db', None)
    if conn is not None:
        conn.close()


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 260000).hex()
    return salt, digest


def verify_password(password, salt, expected):
    _, actual = hash_password(password, salt)
    return hmac.compare_digest(actual, expected)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA foreign_keys = ON')
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS teachers (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT UNIQUE NOT NULL,
      salt TEXT NOT NULL,
      password_hash TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS students (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      roll_no TEXT UNIQUE NOT NULL,
      name TEXT NOT NULL,
      class_name TEXT NOT NULL DEFAULT 'B.Tech'
    );
    CREATE TABLE IF NOT EXISTS attendance (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
      attendance_date TEXT NOT NULL,
      status TEXT NOT NULL CHECK(status IN ('Present','Absent','Leave')),
      UNIQUE(student_id, attendance_date)
    );
    ''')
    exists = conn.execute('SELECT id FROM teachers WHERE username = ?', ('teacher',)).fetchone()
    if not exists:
        salt, digest = hash_password(os.environ.get('TEACHER_PASSWORD', 'ChangeMe123!'))
        conn.execute('INSERT INTO teachers(username,salt,password_hash) VALUES(?,?,?)', ('teacher', salt, digest))
    conn.commit()
    conn.close()

init_db()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if 'teacher_id' not in session:
            return redirect(url_for('login', next=request.path))
        return view(*args, **kwargs)
    return wrapped


def csrf_token():
    if '_csrf' not in session:
        session['_csrf'] = secrets.token_urlsafe(24)
    return session['_csrf']
app.jinja_env.globals['csrf_token'] = csrf_token

@app.before_request
def check_csrf():
    if request.method == 'POST':
        sent = request.form.get('_csrf', '')
        saved = session.get('_csrf', '')
        if not saved or not hmac.compare_digest(sent, saved):
            abort(400, 'Invalid or expired form token. Refresh the page and try again.')

@app.template_filter('pretty_date')
def pretty_date(value):
    try:
        return datetime.strptime(value, '%Y-%m-%d').strftime('%d %b %Y')
    except (ValueError, TypeError):
        return value

@app.route('/')
def index():
    if 'teacher_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        teacher = db().execute('SELECT * FROM teachers WHERE username = ?', (username,)).fetchone()
        if teacher and verify_password(password, teacher['salt'], teacher['password_hash']):
            session.clear()
            session['teacher_id'] = teacher['id']
            session['username'] = teacher['username']
            session['_csrf'] = secrets.token_urlsafe(24)
            return redirect(url_for('dashboard'))
        flash('Incorrect username or password.', 'error')
    return render_template('login.html')

@app.route('/logout', methods=['POST'])
@login_required
def logout():
    session.clear()
    flash('You have logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    conn = db()
    today = date.today().isoformat()
    total = conn.execute('SELECT COUNT(*) n FROM students').fetchone()['n']
    marked = conn.execute('SELECT COUNT(*) n FROM attendance WHERE attendance_date = ?', (today,)).fetchone()['n']
    present = conn.execute("SELECT COUNT(*) n FROM attendance WHERE attendance_date = ? AND status = 'Present'", (today,)).fetchone()['n']
    students = conn.execute('''SELECT s.id,s.roll_no,s.name,s.class_name,
      SUM(CASE WHEN a.status IN ('Present','Absent') THEN 1 ELSE 0 END) AS total_days,
      SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) AS present_days
      FROM students s LEFT JOIN attendance a ON a.student_id=s.id GROUP BY s.id ORDER BY s.roll_no''').fetchall()
    rows=[]
    low=0
    for s in students:
        total_days=s['total_days'] or 0; present_days=s['present_days'] or 0
        pct=round(present_days*100/total_days, 1) if total_days else None
        if pct is not None and pct < THRESHOLD: low += 1
        rows.append(dict(id=s['id'], roll_no=s['roll_no'], name=s['name'], class_name=s['class_name'], total_days=total_days, present_days=present_days, pct=pct))
    return render_template('dashboard.html', students=rows, total=total, marked=marked, present=present, low=low, today=today, threshold=THRESHOLD)

@app.route('/students', methods=['GET','POST'])
@login_required
def students_page():
    conn=db()
    if request.method=='POST':
        roll=request.form.get('roll_no','').strip()
        name=request.form.get('name','').strip()
        class_name=request.form.get('class_name','B.Tech').strip() or 'B.Tech'
        if not roll or not name:
            flash('Roll number and student name are required.', 'error')
        else:
            try:
                conn.execute('INSERT INTO students(roll_no,name,class_name) VALUES(?,?,?)',(roll,name,class_name))
                conn.commit(); flash('Student added successfully.', 'success')
                return redirect(url_for('students_page'))
            except sqlite3.IntegrityError:
                flash('That roll number already exists. Use a unique roll number.', 'error')
    students=conn.execute('SELECT * FROM students ORDER BY roll_no').fetchall()
    return render_template('students.html', students=students)

@app.route('/students/<int:student_id>/delete', methods=['POST'])
@login_required
def delete_student(student_id):
    conn=db(); conn.execute('DELETE FROM students WHERE id=?',(student_id,)); conn.commit()
    flash('Student and their attendance records deleted.', 'success')
    return redirect(url_for('students_page'))

@app.route('/attendance', methods=['GET','POST'])
@login_required
def attendance_page():
    conn=db()
    selected=request.values.get('date', date.today().isoformat())
    try: datetime.strptime(selected,'%Y-%m-%d')
    except ValueError: selected=date.today().isoformat()
    students=conn.execute('SELECT * FROM students ORDER BY roll_no').fetchall()
    if request.method=='POST':
        for student in students:
            status=request.form.get(f"status_{student['id']}")
            if status in ('Present','Absent','Leave'):
                conn.execute('''INSERT INTO attendance(student_id,attendance_date,status) VALUES(?,?,?)
                  ON CONFLICT(student_id,attendance_date) DO UPDATE SET status=excluded.status''',(student['id'],selected,status))
        conn.commit(); flash(f'Attendance saved for {selected}.', 'success')
        return redirect(url_for('attendance_page', date=selected))
    existing={r['student_id']:r['status'] for r in conn.execute('SELECT student_id,status FROM attendance WHERE attendance_date=?',(selected,)).fetchall()}
    return render_template('attendance.html', students=students, selected=selected, existing=existing)

@app.route('/reports')
@login_required
def reports():
    month=request.args.get('month', date.today().strftime('%Y-%m'))
    try:
        year, mon=map(int, month.split('-'))
        if mon not in range(1,13) or year not in range(2000,2100): raise ValueError
    except (ValueError, TypeError):
        month=date.today().strftime('%Y-%m'); year,mon=map(int,month.split('-'))
    start=f'{year:04d}-{mon:02d}-01'; end=f'{year:04d}-{mon:02d}-{calendar.monthrange(year,mon)[1]:02d}'
    records=db().execute('''SELECT s.id,s.roll_no,s.name,s.class_name,
      SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END) AS present_days,
      SUM(CASE WHEN a.status='Absent' THEN 1 ELSE 0 END) AS absent_days,
      SUM(CASE WHEN a.status='Leave' THEN 1 ELSE 0 END) AS leave_days
      FROM students s LEFT JOIN attendance a ON a.student_id=s.id AND a.attendance_date BETWEEN ? AND ?
      GROUP BY s.id ORDER BY s.roll_no''',(start,end)).fetchall()
    rows=[]
    for r in records:
        p=r['present_days'] or 0; a=r['absent_days'] or 0; l=r['leave_days'] or 0; total=p+a
        pct=round(p*100/total,1) if total else None
        rows.append(dict(roll_no=r['roll_no'],name=r['name'],class_name=r['class_name'],present=p,absent=a,leave=l,total=total,pct=pct,low=(pct is not None and pct<THRESHOLD)))
    return render_template('reports.html', rows=rows, month=month, threshold=THRESHOLD, month_label=f'{calendar.month_name[mon]} {year}')

@app.route('/change-password', methods=['GET','POST'])
@login_required
def change_password():
    if request.method=='POST':
        old=request.form.get('old_password',''); new=request.form.get('new_password',''); confirm=request.form.get('confirm_password','')
        teacher=db().execute('SELECT * FROM teachers WHERE id=?',(session['teacher_id'],)).fetchone()
        if not verify_password(old,teacher['salt'],teacher['password_hash']): flash('Current password is incorrect.','error')
        elif len(new)<10: flash('New password must be at least 10 characters.','error')
        elif new!=confirm: flash('New passwords do not match.','error')
        else:
            salt,digest=hash_password(new)
            db().execute('UPDATE teachers SET salt=?,password_hash=? WHERE id=?',(salt,digest,session['teacher_id'])); db().commit()
            flash('Password changed. Please log in again.','success'); session.clear(); return redirect(url_for('login'))
    return render_template('change_password.html')

if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG')=='1', host='127.0.0.1', port=int(os.environ.get('PORT','5000')))
