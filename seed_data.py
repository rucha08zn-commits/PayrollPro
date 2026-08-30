from datetime import datetime, date, timedelta
from database import db, Employee, Attendance, PunchLog, LeaveRequest, Holiday, init_database
from flask import Flask

DEMO_PASSWORD = "employee123"
DEMO_EMPLOYEES = [('Aarav Sharma', 'Engineering', 'Software Engineer'), ('Ananya Patil', 'HR', 'HR Executive'), ('Rohan Deshmukh', 'Finance', 'Accountant'), ('Isha Kulkarni', 'Engineering', 'Frontend Developer'), ('Vedant Joshi', 'Engineering', 'Backend Developer'), ('Sneha Pawar', 'Sales', 'Sales Executive'), ('Aditya More', 'Marketing', 'Marketing Executive'), ('Priya Jadhav', 'HR', 'HR Manager'), ('Omkar Shinde', 'Engineering', 'QA Engineer'), ('Kavya Chavan', 'Finance', 'Finance Executive'), ('Siddharth Kale', 'Engineering', 'DevOps Engineer'), ('Neha Wagh', 'Sales', 'Sales Manager'), ('Atharva Bhosale', 'Engineering', 'Software Engineer'), ('Meera Gaikwad', 'Marketing', 'Content Specialist'), ('Tanmay Desai', 'Finance', 'Senior Accountant'), ('Riya Thakur', 'HR', 'Recruiter'), ('Yash Mahajan', 'Engineering', 'UI/UX Designer'), ('Sakshi Suryawanshi', 'Sales', 'Business Development Executive'), ('Harsh Vaidya', 'Engineering', 'Full Stack Developer'), ('Pooja Nair', 'Finance', 'Payroll Executive'), ('Akshay Dhumal', 'Engineering', 'Software Engineer'), ('Shreya Joshi', 'Marketing', 'Social Media Executive'), ('Kunal Patil', 'Sales', 'Sales Executive'), ('Aditi Borkar', 'HR', 'HR Executive'), ('Manish Rathod', 'Engineering', 'Data Analyst'), ('Simran Kaur', 'Finance', 'Finance Manager'), ('Nikhil Salve', 'Engineering', 'Mobile Developer'), ('Mitali Kshirsagar', 'Marketing', 'Graphic Designer'), ('Rahul Gawande', 'Sales', 'Account Executive'), ('Diya Shelar', 'HR', 'Training Coordinator'), ('Saurabh Ingale', 'Engineering', 'System Administrator'), ('Ayesha Khan', 'Finance', 'Accounts Executive'), ('Vivek Nikam', 'Engineering', 'Software Engineer'), ('Nandini Pawar', 'Marketing', 'Marketing Manager'), ('Tejas Bhandari', 'Sales', 'Sales Executive'), ('Mrunal Patil', 'HR', 'HR Executive'), ('Parth Pande', 'Engineering', 'Cloud Engineer'), ('Komal Shinde', 'Finance', 'Accounts Executive'), ('Raj Malhotra', 'Sales', 'Sales Manager'), ('Vaishnavi More', 'Marketing', 'Content Writer'), ('Abhishek Koli', 'Engineering', 'QA Engineer'), ('Tanisha Kale', 'HR', 'HR Executive'), ('Soham Jagtap', 'Finance', 'Financial Analyst'), ('Rutuja Patil', 'Engineering', 'Software Engineer'), ('Mohit Choudhary', 'Sales', 'Sales Executive'), ('Pallavi Deshmukh', 'Marketing', 'Brand Executive'), ('Akash Wagh', 'Engineering', 'Backend Developer'), ('Nisha Bansode', 'HR', 'HR Coordinator'), ('Vishal Pawar', 'Finance', 'Accountant'), ('Sonal Joshi', 'Engineering', 'Product Designer')]
DEMO_HOLIDAYS_2026 = [('2026-01-26', 'Republic Day'), ('2026-02-15', 'Mahashivratri'), ('2026-02-19', 'Chhatrapati Shivaji Maharaj Jayanti'), ('2026-03-03', 'Holi (Second Day)'), ('2026-03-19', 'Gudhi Padwa'), ('2026-03-21', 'Ramzan-Id (Id-Ul-Fitra) (Shawal-1)'), ('2026-03-26', 'Ram Navami'), ('2026-03-31', 'Mahavir Janmakalyanak'), ('2026-04-03', 'Good Friday'), ('2026-04-14', 'Dr. Babasaheb Ambedkar Jayanti'), ('2026-05-01', 'Maharashtra Din / Buddha Pournima'), ('2026-05-28', 'Bakri Id (Id-Uz-Zuha)'), ('2026-06-26', 'Moharum'), ('2026-08-15', 'Independence Day / Parsi New Year (Shahenshahi)'), ('2026-08-26', 'Id-E-Milad'), ('2026-09-14', 'Ganesh Chaturthi'), ('2026-10-02', 'Mahatma Gandhi Jayanti'), ('2026-10-20', 'Dasara'), ('2026-11-08', 'Diwali Amavasya (Laxmi Pujan)'), ('2026-11-10', 'Diwali (Bali Pratipada)'), ('2026-11-24', 'Guru Nanak Jayanti'), ('2026-12-25', 'Christmas')]

def seed_demo_data():
    managers = {"Engineering":"Priya Jadhav", "HR":"Priya Jadhav", "Finance":"Simran Kaur", "Sales":"Neha Wagh", "Marketing":"Nandini Pawar"}
    locations = ["Nagpur HQ", "Pune Office", "Mumbai Office"]
    colleges = ["Raisoni College of Engineering", "RTM Nagpur University", "Pune University", "Mumbai University"]
    for idx, (name, dept, designation) in enumerate(DEMO_EMPLOYEES, 1):
        email=f"employee{idx:02d}@payrollpro.local"
        e=Employee.query.filter_by(email=email).first()
        basic=28000+(idx%10)*2500
        joined=f"202{3+(idx%3)}-{1+(idx%9):02d}-15"
        dob=f"{1988+(idx%11):04d}-{1+(idx%12):02d}-{5+(idx%20):02d}"
        if not e:
            e=Employee(name=name,department=dept,designation=designation,email=email,phone=f"+91 9{idx:09d}",
                date_joined=joined,basic=basic,hra=round(basic*.40,2),bonus=1000 if idx%4==0 else 0,
                allowance=2500+(idx%5)*500,pf=round(basic*.12,2),tax=round((basic*1.4)*.02,2),other_ded=0,
                status="Active",leave_balance=20,last_appraisal_date=f"2025-{1+(idx%12):02d}-15",
                dob=dob,gender="Female" if idx%2==0 else "Male",alternate_phone=f"+91 8{idx:09d}",
                address=f"{100+idx}, Demo Residency",city="Nagpur",state="Maharashtra",
                emergency_contact_name=f"Emergency Contact {idx:02d}",emergency_contact_phone=f"+91 7{idx:09d}",
                employment_type="Full-time" if idx%7 else "Contract",reporting_manager=managers.get(dept,"Admin"),
                work_location=locations[idx%len(locations)],shift="09:00–18:00",working_hours=8,
                probation_status="Confirmed",confirmation_date=joined,qualification="B.E./B.Tech",
                college=colleges[idx%len(colleges)],graduation_year=2019+(idx%7),
                skills="Python, SQL, Communication" if dept=="Engineering" else "Excel, Communication, Teamwork",
                certifications="Professional Certificate",previous_company="Demo Technologies Pvt. Ltd.",
                experience_years=float(1+(idx%7)),appraisal_rating=3.5+(idx%3)*.5,
                appraisal_comments="Consistent performance and good teamwork.",hike_pct=8+(idx%4)*2)
            e.set_password(DEMO_PASSWORD); db.session.add(e)
        else:
            # Fill new fields without destroying existing edits.
            defaults=dict(name=name,department=dept,designation=designation,dob=dob,gender="Female" if idx%2==0 else "Male",
                alternate_phone=f"+91 8{idx:09d}",address=f"{100+idx}, Demo Residency",city="Nagpur",state="Maharashtra",
                emergency_contact_name=f"Emergency Contact {idx:02d}",emergency_contact_phone=f"+91 7{idx:09d}",
                employment_type="Full-time" if idx%7 else "Contract",reporting_manager=managers.get(dept,"Admin"),
                work_location=locations[idx%len(locations)],shift="09:00–18:00",working_hours=8,probation_status="Confirmed",
                confirmation_date=e.confirmation_date or joined,qualification="B.E./B.Tech",college=colleges[idx%len(colleges)],
                graduation_year=2019+(idx%7),skills="Python, SQL, Communication" if dept=="Engineering" else "Excel, Communication, Teamwork",
                certifications="Professional Certificate",previous_company="Demo Technologies Pvt. Ltd.",experience_years=float(1+(idx%7)),
                appraisal_rating=3.5+(idx%3)*.5,appraisal_comments="Consistent performance and good teamwork.",hike_pct=8+(idx%4)*2)
            for k,v in defaults.items():
                if getattr(e,k,None) in (None,""): setattr(e,k,v)
            if not e.password: e.set_password(DEMO_PASSWORD)
            e.leave_balance=e.leave_balance or 20
    db.session.commit()

    # Seed the complete Maharashtra 2026 public holiday notification.
    for hdate,hname in DEMO_HOLIDAYS_2026:
        h=Holiday.query.filter_by(date=hdate).first()
        if h: h.name=hname
        else: db.session.add(Holiday(date=hdate,name=hname))
    db.session.commit()

    employees=Employee.query.order_by(Employee.id).all()
    holiday_dates={h.date for h in Holiday.query.all()}
    # Refresh only the demo August slice so rerunning the seed produces a clean, complete month.
    for old_a in Attendance.query.filter(Attendance.date.like("2026-08-%"), Attendance.source.like("Demo%")).all():
        db.session.delete(old_a)
    for old_p in PunchLog.query.filter(PunchLog.date.like("2026-08-%")).all():
        db.session.delete(old_p)
    db.session.commit()
    # COMPLETE AUGUST 2026: every weekday for every employee, excluding public holidays.
    for e in employees:
        leave_days=set()
        if e.id<=12:
            start_day=3+(e.id%18)
            leave_days={f"2026-08-{d:02d}" for d in range(start_day,min(start_day+2,29))}
        for day in range(1,32):
            dt=date(2026,8,day); ds=dt.isoformat()
            if dt.weekday()>=5 or ds in holiday_dates: continue
            # Approved leave gets Leave; other days are realistic Present/Absent.
            if ds in leave_days: status="Leave"
            else: status="Absent" if (e.id*7+day)%29==0 else "Present"
            a=Attendance.query.filter_by(emp_id=e.id,date=ds).first()
            if not a: db.session.add(Attendance(emp_id=e.id,date=ds,status=status,source="Demo-August-2026"))
            else: a.status=status; a.source="Demo-August-2026"
            if status=="Present" and not PunchLog.query.filter_by(emp_id=e.id,date=ds).first():
                m=(e.id+day)%5; db.session.add(PunchLog(emp_id=e.id,date=ds,time_in=f"09:{m:02d}:00",time_out=f"18:{m:02d}:00",hours=9.0))
    # Leave requests correspond to the seeded Leave attendance.
    for e in employees[:12]:
        start_day=3+(e.id%18); start=f"2026-08-{start_day:02d}"; end=f"2026-08-{min(start_day+1,28):02d}"
        if not LeaveRequest.query.filter_by(emp_id=e.id,start_date=start).first():
            db.session.add(LeaveRequest(emp_id=e.id,leave_type="Casual" if e.id%2 else "Sick",start_date=start,end_date=end,reason="Demo August leave request",status="Approved" if e.id%3 else "Pending"))
    db.session.commit()

def main():
    app=Flask(__name__); init_database(app)
    with app.app_context():
        db.create_all(); seed_demo_data()
        print("\nPayrollPro database seeded successfully.")
        print("Employees:",Employee.query.count())
        print("August 2026 attendance:",Attendance.query.filter(Attendance.date.like("2026-08-%")).count())
        print("August 2026 punches:",PunchLog.query.filter(PunchLog.date.like("2026-08-%")).count())
        print("Leave requests:",LeaveRequest.query.count())
        print("Public holiday dates:",Holiday.query.count())
        print("Default employee password: employee123")

if __name__=="__main__": main()
