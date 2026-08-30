# PayrollPro — Final Demo Build

## Included
- Purple/navy Admin + Employee UI
- Complete Employee 360 profile with contact, DOB/age, work, tenure, salary, skills and appraisal
- Admin employee directory + profile access
- Admin punch in/out for all employees
- Complete August 2026 working-day attendance for 50 demo employees
- Maharashtra 2026 public holiday calendar
- Functional payroll/attendance/employee/leave/appraisal/holiday reports
- CSV, Excel and PDF report downloads
- Employee self-service profile, attendance/punch, leave, payslips, appraisal and notifications

## Run on Windows
```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe seed_data.py
.\.venv\Scripts\python.exe app.py
```
Open http://127.0.0.1:5000

Admin: `admin` / `admin123`
Employee password: `employee123`

The seed data is fictional/demo data.
