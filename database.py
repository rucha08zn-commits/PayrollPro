from datetime import date, datetime
import os
import sqlite3

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "payroll.db")
STANDARD_WORK_HOURS = 8

db = SQLAlchemy()


class Employee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    department = db.Column(db.String(100))
    designation = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    phone = db.Column(db.String(20))
    basic = db.Column(db.Float, default=0)
    hra = db.Column(db.Float, default=0)
    bonus = db.Column(db.Float, default=0)
    allowance = db.Column(db.Float, default=0)
    pf = db.Column(db.Float, default=0)
    tax = db.Column(db.Float, default=0)
    other_ded = db.Column(db.Float, default=0)
    status = db.Column(db.String(20), default="Active")
    password = db.Column(db.String(255))
    leave_balance = db.Column(db.Integer, default=12)
    date_joined = db.Column(db.String(20))
    last_appraisal_date = db.Column(db.String(20))
    dob = db.Column(db.String(20))
    gender = db.Column(db.String(20))
    alternate_phone = db.Column(db.String(20))
    address = db.Column(db.String(255))
    city = db.Column(db.String(80))
    state = db.Column(db.String(80))
    emergency_contact_name = db.Column(db.String(100))
    emergency_contact_phone = db.Column(db.String(20))
    employment_type = db.Column(db.String(30), default="Full-time")
    reporting_manager = db.Column(db.String(100))
    work_location = db.Column(db.String(100))
    shift = db.Column(db.String(50), default="09:00–18:00")
    working_hours = db.Column(db.Float, default=8)
    probation_status = db.Column(db.String(30), default="Confirmed")
    confirmation_date = db.Column(db.String(20))
    resignation_date = db.Column(db.String(20))
    qualification = db.Column(db.String(150))
    college = db.Column(db.String(150))
    graduation_year = db.Column(db.Integer)
    skills = db.Column(db.String(500))
    certifications = db.Column(db.String(500))
    previous_company = db.Column(db.String(150))
    experience_years = db.Column(db.Float, default=0)
    appraisal_rating = db.Column(db.Float, default=0)
    appraisal_comments = db.Column(db.String(500))
    hike_pct = db.Column(db.Float, default=0)

    def set_password(self, raw_password):
        self.password = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        if not self.password:
            return False
        return check_password_hash(self.password, raw_password)

    @property
    def net(self):
        return ((self.basic or 0) + (self.hra or 0) + (self.bonus or 0) + (self.allowance or 0)
                - (self.pf or 0) - (self.tax or 0) - (self.other_ded or 0))

    @property
    def per_hour_rate(self):
        return round((self.basic or 0) / 26 / STANDARD_WORK_HOURS, 2) if self.basic else 0

    @property
    def age(self):
        if not self.dob:
            return None
        try:
            born = datetime.strptime(self.dob, "%Y-%m-%d").date()
            today = date.today()
            return today.year - born.year - ((today.month, today.day) < (born.month, born.day))
        except ValueError:
            return None

    @property
    def tenure_days(self):
        if not self.date_joined:
            return None
        try:
            return (date.today() - datetime.strptime(self.date_joined, "%Y-%m-%d").date()).days
        except ValueError:
            return None

    @property
    def tenure_label(self):
        d = self.tenure_days
        if d is None:
            return "—"
        years, rem = divmod(d, 365)
        months = rem // 30
        return f"{years}y {months}m" if years else f"{months}m"

    @property
    def next_appraisal_date(self):
        base = self.last_appraisal_date or self.date_joined
        if not base:
            return None
        try:
            base_d = datetime.strptime(base, "%Y-%m-%d").date()
        except ValueError:
            return None
        # Handles Feb 29 safely.
        try:
            return base_d.replace(year=base_d.year + 1)
        except ValueError:
            return base_d.replace(year=base_d.year + 1, day=28)

    @property
    def appraisal_due(self):
        nd = self.next_appraisal_date
        return bool(nd and nd <= date.today())

    @property
    def suggested_hike_pct(self):
        d = self.tenure_days or 0
        years = d // 365
        if years <= 0:
            return 0
        if years == 1:
            return 8
        if years <= 3:
            return 10
        return 12


class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    emp_id = db.Column(db.Integer, db.ForeignKey("employee.id"))
    date = db.Column(db.String(20))
    status = db.Column(db.String(20))
    source = db.Column(db.String(20), default="manual")


class LeaveRequest(db.Model):
    __tablename__ = "leave_request"
    id = db.Column(db.Integer, primary_key=True)
    emp_id = db.Column(db.Integer, db.ForeignKey("employee.id"))
    leave_type = db.Column(db.String(50))
    start_date = db.Column(db.String(20))
    end_date = db.Column(db.String(20))
    reason = db.Column(db.String(200))
    status = db.Column(db.String(20), default="Pending")


class PunchLog(db.Model):
    __tablename__ = "punch_log"
    id = db.Column(db.Integer, primary_key=True)
    emp_id = db.Column(db.Integer, db.ForeignKey("employee.id"))
    date = db.Column(db.String(20))
    time_in = db.Column(db.String(20))
    time_out = db.Column(db.String(20))
    hours = db.Column(db.Float, default=0)

    @property
    def overtime_hours(self):
        return round(max(0, (self.hours or 0) - STANDARD_WORK_HOURS), 2)


class Holiday(db.Model):
    __tablename__ = "holiday"
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(20), unique=True)
    name = db.Column(db.String(100))


def init_database(app):
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + DB_FILE
    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)
    db.init_app(app)


def auto_migrate():
    if not os.path.exists(DB_FILE):
        return

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Support both the current schema and the older demo schema.
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='employee'")
    if c.fetchone():
        c.execute("PRAGMA table_info(employee)")
        columns = {row[1] for row in c.fetchall()}
        new_columns = {
            "status": "VARCHAR(20) DEFAULT 'Active'",
            "password": "VARCHAR(255)",
            "leave_balance": "INTEGER DEFAULT 12",
            "date_joined": "VARCHAR(20)",
            "last_appraisal_date": "VARCHAR(20)",
            "dob": "VARCHAR(20)", "gender": "VARCHAR(20)",
            "alternate_phone": "VARCHAR(20)", "address": "VARCHAR(255)",
            "city": "VARCHAR(80)", "state": "VARCHAR(80)",
            "emergency_contact_name": "VARCHAR(100)", "emergency_contact_phone": "VARCHAR(20)",
            "employment_type": "VARCHAR(30) DEFAULT 'Full-time'",
            "reporting_manager": "VARCHAR(100)", "work_location": "VARCHAR(100)",
            "shift": "VARCHAR(50) DEFAULT '09:00–18:00'", "working_hours": "FLOAT DEFAULT 8",
            "probation_status": "VARCHAR(30) DEFAULT 'Confirmed'",
            "confirmation_date": "VARCHAR(20)", "resignation_date": "VARCHAR(20)",
            "qualification": "VARCHAR(150)", "college": "VARCHAR(150)",
            "graduation_year": "INTEGER", "skills": "VARCHAR(500)",
            "certifications": "VARCHAR(500)", "previous_company": "VARCHAR(150)",
            "experience_years": "FLOAT DEFAULT 0", "appraisal_rating": "FLOAT DEFAULT 0",
            "appraisal_comments": "VARCHAR(500)", "hike_pct": "FLOAT DEFAULT 0",
        }
        for col_name, col_def in new_columns.items():
            if col_name not in columns:
                c.execute(f"ALTER TABLE employee ADD COLUMN {col_name} {col_def}")
                print(f"[auto_migrate] Added '{col_name}' column to employee table.")

        # Convert old plaintext passwords to Werkzeug hashes.
        if "password" in columns or "password" in new_columns:
            c.execute("SELECT id, password FROM employee")
            for emp_id, pw in c.fetchall():
                if pw and not pw.startswith(("pbkdf2:", "scrypt:", "argon2:")):
                    c.execute(
                        "UPDATE employee SET password = ? WHERE id = ?",
                        (generate_password_hash(pw), emp_id)
                    )

    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='attendance'")
    if c.fetchone():
        c.execute("PRAGMA table_info(attendance)")
        att_columns = {row[1] for row in c.fetchall()}
        if "source" not in att_columns:
            c.execute("ALTER TABLE attendance ADD COLUMN source VARCHAR(20) DEFAULT 'manual'")
            print("[auto_migrate] Added 'source' column to attendance table.")

    conn.commit()
    conn.close()


def wipe_all_employee_data():
    PunchLog.query.delete()
    LeaveRequest.query.delete()
    Attendance.query.delete()
    Employee.query.delete()
    db.session.commit()
