from flask import Flask, request, redirect, session, render_template_string, url_for, flash, send_file, jsonify
from database import (db, DB_FILE, init_database, auto_migrate, wipe_all_employee_data,
                       Employee, Attendance, PunchLog, LeaveRequest, Holiday,
                       STANDARD_WORK_HOURS)
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date, datetime, timedelta
import calendar
import sqlite3
import os
import io
import csv
from collections import defaultdict

# Absolute path to payroll.db, always sitting next to this app.py file.
# This avoids Flask-SQLAlchemy's default behavior of creating the database
# inside a separate "instance/" subfolder, which was causing a mismatch
# between the database the app reads from and the one being patched.
app = Flask(__name__)
init_database(app)
# Render/Gunicorn does not execute the __main__ block. Initialize and migrate
# the SQLite database at import time so the deployed app has the latest schema.
auto_migrate()
with app.app_context():
    db.create_all()
    # Seed the demo database on a fresh deployment. Existing data is preserved.
    if Employee.query.count() == 0:
        from seed_data import seed_demo_data
        seed_demo_data()
app.secret_key = os.environ.get("SECRET_KEY", "payrollpro-demo-secret")

ADMIN_USER = "admin"
ADMIN_PASS_HASH = generate_password_hash("admin123")  # change the source string, not this hash, to set a new admin password

STANDARD_WORK_HOURS = 8  # a "full day" for overtime + auto-attendance purposes

# ---------------- MODERN UI SYSTEM ----------------
# The app stays self-contained: templates, styling and small interactions
# live here so the project can run with only app.py + payroll.db.
BASE = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>PayrollPro — {{ page_title|default('Payroll Management') }}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/core@latest/dist/css/tabler.min.css">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@latest/dist/tabler-icons.min.css">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
<style>
:root{
  --pp-primary:#7c3aed; --pp-primary-2:#a78bfa; --pp-bg:#f7f8fc;
  --pp-card:#ffffff; --pp-text:#18202f; --pp-muted:#718096;
  --pp-border:#e7eaf0; --pp-sidebar:#241044; --pp-sidebar-2:#4c1d95;
  --pp-success:#16a34a; --pp-warning:#f59e0b; --pp-danger:#dc2626;
  --pp-blue:#2563eb; --pp-purple:#7c3aed;
}
[data-bs-theme="dark"]{
  --pp-bg:#0f1117; --pp-card:#171a22; --pp-text:#f5f7fb; --pp-muted:#9aa4b2;
  --pp-border:#282d38; --pp-sidebar:#170b2f; --pp-sidebar-2:#3b1a72;
}
html,body{background:var(--pp-bg);color:var(--pp-text);}
body{font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;}
.page{min-height:100vh;}
.pp-sidebar{
  position:fixed;left:0;top:0;bottom:0;width:246px;z-index:1030;
  background:linear-gradient(180deg,var(--pp-sidebar-2),var(--pp-sidebar));
  color:#fff;padding:22px 14px;display:flex;flex-direction:column;
  box-shadow:10px 0 35px rgba(20,24,40,.10);
}
.pp-brand{display:flex;align-items:center;gap:11px;color:#fff;text-decoration:none;padding:5px 10px 26px;}
.pp-brand-mark{width:38px;height:38px;border-radius:12px;background:#fff;color:var(--pp-primary);
display:grid;place-items:center;font-size:20px;box-shadow:0 7px 20px rgba(0,0,0,.14);}
.pp-brand-name{font-size:20px;font-weight:800;letter-spacing:-.5px;}
.pp-brand-name span{font-weight:500;opacity:.85;}
.pp-nav-label{text-transform:uppercase;font-size:10px;font-weight:800;letter-spacing:1.1px;opacity:.6;padding:0 12px;margin:7px 0 8px;}
.pp-nav{display:flex;flex-direction:column;gap:4px;}
.pp-nav a{
  color:rgba(255,255,255,.82);text-decoration:none;border-radius:10px;padding:10px 12px;
  display:flex;align-items:center;gap:11px;font-size:13px;font-weight:600;transition:.18s ease;
}
.pp-nav a i{font-size:18px;opacity:.9;}
.pp-nav a:hover{background:rgba(255,255,255,.12);color:#fff;transform:translateX(2px);}
.pp-nav a.active{background:#fff;color:var(--pp-primary);box-shadow:0 7px 18px rgba(0,0,0,.12);}
.pp-sidebar-bottom{margin-top:auto;}
.pp-logout{border-top:1px solid rgba(255,255,255,.14);padding-top:14px;margin-top:14px;}
.pp-main{margin-left:246px;min-height:100vh;}
.pp-topbar{
  height:76px;background:rgba(255,255,255,.82);backdrop-filter:blur(14px);
  border-bottom:1px solid var(--pp-border);display:flex;align-items:center;
  justify-content:space-between;padding:0 30px;position:sticky;top:0;z-index:20;
}
[data-bs-theme="dark"] .pp-topbar{background:rgba(23,26,34,.86);}
.pp-search{width:290px;position:relative;}
.pp-search i{position:absolute;left:13px;top:10px;color:var(--pp-muted);}
.pp-search input{padding-left:38px;border-radius:10px;background:var(--pp-bg);border-color:var(--pp-border);}
.pp-top-actions{display:flex;align-items:center;gap:16px;}
.pp-icon-btn{border:0;background:transparent;color:var(--pp-muted);font-size:20px;position:relative;}
.pp-dot{position:absolute;right:-2px;top:-1px;width:7px;height:7px;border-radius:50%;background:#ef3340;border:2px solid var(--pp-card);}
.pp-user{display:flex;align-items:center;gap:10px;padding-left:8px;}
.pp-avatar{width:38px;height:38px;border-radius:50%;background:linear-gradient(135deg,#7c3aed,#a78bfa);
color:#fff;display:grid;place-items:center;font-weight:800;}
.pp-content{padding:28px 30px 42px;max-width:1700px;margin:auto;}
.pp-page-heading{display:flex;justify-content:space-between;align-items:flex-start;gap:20px;margin-bottom:22px;}
.pp-eyebrow{font-size:12px;color:var(--pp-muted);margin-bottom:5px;}
.pp-title{font-size:28px;line-height:1.15;font-weight:800;letter-spacing:-.8px;margin:0;}
.pp-subtitle{color:var(--pp-muted);font-size:13px;margin-top:7px;}
.pp-card{background:var(--pp-card);border:1px solid var(--pp-border);border-radius:16px;box-shadow:0 5px 22px rgba(25,35,55,.045);}
[data-bs-theme="dark"] .pp-card{box-shadow:none;}
.pp-card-pad{padding:20px;}
.pp-stat{padding:18px;position:relative;overflow:hidden;min-height:126px;}
.pp-stat:after{content:"";position:absolute;width:80px;height:80px;border-radius:50%;right:-28px;top:-28px;background:var(--stat-bg);opacity:.42;}
.pp-stat-icon{width:42px;height:42px;border-radius:12px;display:grid;place-items:center;font-size:21px;background:var(--stat-bg);color:var(--stat-color);margin-bottom:13px;}
.pp-stat-label{font-size:12px;color:var(--pp-muted);font-weight:600;}
.pp-stat-value{font-size:25px;font-weight:800;letter-spacing:-.5px;margin-top:2px;}
.pp-stat-change{font-size:11px;font-weight:700;margin-top:4px;}
.pp-section-title{font-size:14px;font-weight:800;margin:0;}
.pp-section-muted{font-size:11px;color:var(--pp-muted);}
.pp-btn-primary{background:var(--pp-primary);border-color:var(--pp-primary);color:#fff;border-radius:10px;font-weight:700;}
.pp-btn-primary:hover{background:#6d28d9;border-color:#6d28d9;color:#fff;}
.pp-btn-soft{background:rgba(124,58,237,.08);color:var(--pp-primary);border:1px solid rgba(124,58,237,.12);border-radius:9px;font-weight:700;}
.pp-table{margin:0;}
.pp-table th{font-size:10px;text-transform:uppercase;letter-spacing:.55px;color:var(--pp-muted);font-weight:800;border-bottom:1px solid var(--pp-border);padding:13px 16px;}
.pp-table td{font-size:12px;border-bottom:1px solid var(--pp-border);padding:13px 16px;vertical-align:middle;}
.pp-table tr:last-child td{border-bottom:0;}
.pp-person{display:flex;align-items:center;gap:10px;}
.pp-person-avatar{width:34px;height:34px;border-radius:10px;background:linear-gradient(135deg,#eef2ff,#fee2e2);color:#334155;display:grid;place-items:center;font-weight:800;font-size:12px;}
.pp-badge{padding:5px 9px;border-radius:999px;font-size:10px;font-weight:800;}
.pp-badge-success{background:#dcfce7;color:#15803d}.pp-badge-warning{background:#fef3c7;color:#b45309}
.pp-badge-danger{background:#fee2e2;color:#b91c1c}.pp-badge-blue{background:#dbeafe;color:#1d4ed8}
.pp-badge-purple{background:#ede9fe;color:#6d28d9}.pp-badge-gray{background:#eef2f7;color:#64748b}
.pp-list-item{display:flex;align-items:center;gap:12px;padding:12px 0;border-bottom:1px solid var(--pp-border);}
.pp-list-item:last-child{border-bottom:0;padding-bottom:0;}
.pp-list-icon{width:34px;height:34px;border-radius:10px;display:grid;place-items:center;font-size:16px;flex:none;}
.pp-chart-wrap{height:275px;}
.pp-mini-chart{height:205px;}
.pp-quick{display:flex;align-items:center;gap:10px;padding:13px;border:1px solid var(--pp-border);border-radius:12px;text-decoration:none;color:var(--pp-text);transition:.18s;}
.pp-quick:hover{border-color:#f2a0a8;transform:translateY(-2px);box-shadow:0 7px 18px rgba(25,35,55,.07);color:var(--pp-text);}
.pp-quick i{font-size:19px;color:var(--pp-primary);}
.pp-alert{padding:11px 12px;border-radius:11px;background:var(--pp-bg);display:flex;gap:10px;align-items:flex-start;}
.pp-empty{padding:35px;text-align:center;color:var(--pp-muted);}
.form-control,.form-select{border-radius:10px;border-color:var(--pp-border);background:var(--pp-card);color:var(--pp-text);}
.form-control:focus,.form-select:focus{border-color:#a78bfa;box-shadow:0 0 0 3px rgba(124,58,237,.10);}
.card{border-color:var(--pp-border);border-radius:16px;box-shadow:0 5px 22px rgba(25,35,55,.045);}
.alert{border-radius:12px;}
@keyframes ppUp{from{opacity:0;transform:translateY(9px)}to{opacity:1;transform:none}}
.pp-animate{animation:ppUp .4s ease both;}
.pp-delay-1{animation-delay:.04s}.pp-delay-2{animation-delay:.08s}.pp-delay-3{animation-delay:.12s}.pp-delay-4{animation-delay:.16s}
.pp-login{
  min-height:100vh;display:grid;place-items:center;padding:30px;position:relative;overflow:hidden;
  background:
    radial-gradient(circle at 12% 18%,rgba(124,58,237,.23),transparent 28%),
    radial-gradient(circle at 88% 80%,rgba(99,102,241,.16),transparent 30%),
    linear-gradient(135deg,#fff6f7 0%,#f6f8ff 100%);
}
.pp-login:before,.pp-login:after{content:"";position:absolute;border-radius:50%;filter:blur(2px);opacity:.75;}
.pp-login:before{width:440px;height:440px;left:-190px;bottom:-180px;background:linear-gradient(135deg,#7c3aed,#c4b5fd);}
.pp-login:after{width:520px;height:520px;right:-250px;top:-220px;background:linear-gradient(135deg,#4c1d95,#a78bfa);}
.pp-login-shell{width:min(1020px,100%);min-height:610px;display:grid;grid-template-columns:1fr 1fr;
background:rgba(255,255,255,.72);backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,.8);
border-radius:28px;box-shadow:0 30px 80px rgba(31,41,55,.16);overflow:hidden;position:relative;z-index:2;}
.pp-login-visual{padding:50px;display:flex;flex-direction:column;justify-content:space-between;position:relative;overflow:hidden;}
.pp-login-visual.admin{background:linear-gradient(145deg,#2e1065,#7c3aed);}
.pp-login-visual.employee{background:linear-gradient(145deg,#241044,#7c3aed);}
.pp-login-visual:after{content:"";position:absolute;width:330px;height:330px;border-radius:50%;right:-130px;bottom:-160px;background:rgba(255,255,255,.13);}
.pp-login-office{position:absolute;right:45px;bottom:42px;width:300px;height:190px;border-radius:18px;
background:linear-gradient(160deg,rgba(255,255,255,.24),rgba(255,255,255,.06));border:1px solid rgba(255,255,255,.25);
box-shadow:0 25px 50px rgba(0,0,0,.13);transform:perspective(600px) rotateY(-7deg);}
.pp-login-office:before{content:"";position:absolute;left:30px;right:30px;top:28px;height:4px;background:rgba(255,255,255,.6);box-shadow:0 35px 0 rgba(255,255,255,.32),0 70px 0 rgba(255,255,255,.2);}
.pp-login-copy{position:relative;z-index:2;color:#fff;max-width:360px;}
.pp-login-copy h2{font-size:34px;line-height:1.08;font-weight:850;letter-spacing:-1px;margin:22px 0 12px;}
.pp-login-copy p{font-size:14px;line-height:1.7;color:rgba(255,255,255,.84);}
.pp-login-feature{position:relative;z-index:2;color:rgba(255,255,255,.88);font-size:12px;display:flex;gap:18px;flex-wrap:wrap;}
.pp-login-form{padding:50px;display:flex;align-items:center;background:var(--pp-card);}
.pp-login-form-inner{width:100%;max-width:390px;margin:auto;}
.pp-login-logo{display:flex;align-items:center;gap:10px;font-size:20px;font-weight:850;margin-bottom:36px;}
.pp-login-logo-mark{width:40px;height:40px;border-radius:12px;background:#fee2e2;color:var(--pp-primary);display:grid;place-items:center;font-size:21px;}
.pp-login-form h1{font-size:28px;font-weight:850;letter-spacing:-.7px;margin-bottom:7px;}
.pp-login-form .lead{font-size:13px;color:var(--pp-muted);margin-bottom:26px;}
.pp-login-label{font-size:11px;font-weight:800;color:var(--pp-text);margin-bottom:7px;}
.pp-login-field{margin-bottom:15px;}
.pp-login-submit{height:46px;width:100%;border-radius:10px;border:0;color:#fff;font-weight:800;background:linear-gradient(135deg,var(--pp-primary),var(--pp-primary-2));box-shadow:0 9px 22px rgba(124,58,237,.22);}
.pp-login-switch{display:flex;justify-content:center;gap:5px;margin-top:22px;font-size:12px;color:var(--pp-muted);}
.pp-login-switch a{font-weight:800;color:var(--pp-primary);text-decoration:none;}
.pp-secure{display:flex;justify-content:center;gap:12px;color:var(--pp-muted);font-size:10px;margin-top:24px;}
.pp-calendar-day{min-height:92px;border:1px solid var(--pp-border);padding:8px;border-radius:10px;background:var(--pp-card);}
.pp-calendar-day.today{border-color:#ef9aa2;box-shadow:inset 0 0 0 1px #ef9aa2;}
.pp-calendar-day .num{font-size:11px;font-weight:800;color:var(--pp-muted);}
.pp-holiday-chip{margin-top:8px;padding:5px 6px;border-radius:7px;background:#fff1f2;color:#be123c;font-size:9px;font-weight:800;}
@media(max-width:1100px){
  .pp-sidebar{width:210px}.pp-main{margin-left:210px}.pp-topbar{padding:0 20px}.pp-content{padding:22px 20px;}
}
@media(max-width:900px){
  .pp-sidebar{position:relative;width:100%;height:auto;min-height:0;padding:12px;display:block;}
  .pp-brand{padding-bottom:12px}.pp-nav{display:grid;grid-template-columns:repeat(3,1fr);}
  .pp-nav-label,.pp-sidebar-bottom{display:none}.pp-main{margin-left:0}.pp-topbar{position:relative;}
  .pp-login-shell{grid-template-columns:1fr}.pp-login-visual{min-height:260px;padding:35px}.pp-login-office{display:none;}
}
@media(max-width:600px){
  .pp-nav{grid-template-columns:repeat(2,1fr)}.pp-topbar{height:auto;padding:13px 16px;gap:10px}.pp-search{width:180px}
  .pp-content{padding:18px 14px}.pp-title{font-size:23px}.pp-login{padding:12px}.pp-login-form,.pp-login-visual{padding:30px 24px;}
}
</style>
<script>
(function(){
  const saved=localStorage.getItem("payrollpro-theme")||"light";
  document.documentElement.setAttribute("data-bs-theme",saved);
})();
</script>

<style id="payrollpro-final-theme">
:root {
  --pp-primary: #7c3aed;
  --pp-primary-2: #a78bfa;
  --pp-primary-soft: #f3e8ff;
}
.btn-primary, .bg-primary, .text-primary { background-color: var(--pp-primary) !important; border-color: var(--pp-primary) !important; color: #fff !important; }
.btn-primary:hover { filter: brightness(0.96); transform: translateY(-1px); }
.nav-link.active, .sidebar a.active { color: var(--pp-primary) !important; }
a:not(.btn) { color: var(--pp-primary); }
.form-control:focus, .form-select:focus { border-color: var(--pp-primary-2) !important; box-shadow: 0 0 0 .2rem rgba(124,58,237,.15) !important; }
.progress-bar { background-color: var(--pp-primary) !important; }
.badge-primary { background-color: var(--pp-primary) !important; }
.pp-animated { transition: transform .18s ease, box-shadow .18s ease, background-color .18s ease; }
.pp-animated:hover { transform: translateY(-2px); box-shadow: 0 8px 22px rgba(76,29,149,.12); }
</style>


<style id="payrollpro-final-purple-theme">
:root{--pp-primary:#7c3aed;--pp-primary-dark:#6d28d9;--pp-primary-soft:#f3e8ff}
.btn-primary,.bg-primary{background-color:var(--pp-primary)!important;border-color:var(--pp-primary)!important}
.btn-primary:hover{background-color:var(--pp-primary-dark)!important;border-color:var(--pp-primary-dark)!important;transform:translateY(-2px)}
.nav-link.active,.sidebar a.active{color:var(--pp-primary)!important}
.progress-bar{background-color:var(--pp-primary)!important}
.form-control:focus,.form-select:focus{border-color:#a78bfa!important;box-shadow:0 0 0 .2rem rgba(124,58,237,.15)!important}
</style>

</head>
<body>
{% if session.get('user') %}
<aside class="pp-sidebar">
  <a class="pp-brand" href="/dashboard">
    <span class="pp-brand-mark"><i class="ti ti-users"></i></span>
    <span class="pp-brand-name">Payroll <span>Pro</span></span>
  </a>
  <div class="pp-nav-label">Workspace</div>
  <nav class="pp-nav">
    <a class="{{ 'active' if request.path=='/dashboard' else '' }}" href="/dashboard"><i class="ti ti-layout-dashboard"></i>Dashboard</a>
    <a class="{{ 'active' if request.path.startswith('/employees') else '' }}" href="/employees"><i class="ti ti-users"></i>Employees</a>
    <a class="{{ 'active' if request.path.startswith('/payroll') else '' }}" href="/payroll"><i class="ti ti-report-money"></i>Payroll</a>
    <a class="{{ 'active' if request.path.startswith('/attendance') or request.path=='/punch' else '' }}" href="/attendance"><i class="ti ti-clock"></i>Attendance</a>
    <a class="{{ 'active' if request.path.startswith('/leave') else '' }}" href="/leave"><i class="ti ti-calendar-off"></i>Leave</a>
    <a class="{{ 'active' if request.path.startswith('/holidays') else '' }}" href="/holidays"><i class="ti ti-calendar-star"></i>Holidays</a>
    <a class="{{ 'active' if request.path.startswith('/appraisals') else '' }}" href="/appraisals"><i class="ti ti-trending-up"></i>Appraisals</a>
  </nav>
  <div class="pp-nav-label" style="margin-top:22px;">Insights</div>
  <nav class="pp-nav">
    <a class="{{ 'active' if request.path.startswith('/reports') else '' }}" href="/reports"><i class="ti ti-chart-bar"></i>Reports</a>
    <a class="{{ 'active' if request.path.startswith('/notifications') else '' }}" href="/notifications"><i class="ti ti-bell"></i>Notifications</a>
    <a class="{{ 'active' if request.path.startswith('/settings') else '' }}" href="/settings"><i class="ti ti-settings"></i>Settings</a>
  </nav>
  <div class="pp-sidebar-bottom">
    <div class="pp-logout"><a class="pp-nav" href="/logout" style="color:#fff;text-decoration:none;padding:10px 12px;"><i class="ti ti-logout"></i>Logout</a></div>
  </div>
</aside>
<div class="pp-main">
  <header class="pp-topbar">
    <div class="pp-search">
      <i class="ti ti-search"></i>
      <input class="form-control form-control-sm" placeholder="Search anything..." onkeydown="if(event.key==='Enter'){location.href='/employees?q='+encodeURIComponent(this.value)}">
    </div>
    <div class="pp-top-actions">
      <button class="pp-icon-btn" onclick="togglePayrollTheme()" title="Toggle theme"><i class="ti ti-moon-stars" id="themeIcon"></i></button>
      <a class="pp-icon-btn text-decoration-none" href="/notifications" title="Notifications"><i class="ti ti-bell"></i>{% if notification_count|default(0)>0 %}<span class="pp-dot"></span>{% endif %}</a>
      <div class="pp-user">
        <div class="pp-avatar">A</div>
        <div class="d-none d-sm-block"><div style="font-size:12px;font-weight:800;">Admin</div><div style="font-size:10px;color:var(--pp-muted);">Super Admin</div></div>
      </div>
    </div>
  </header>
{% endif %}

{% if session.get('employee_id') %}
<aside class="pp-sidebar">
  <a class="pp-brand" href="/employee/dashboard">
    <span class="pp-brand-mark" style="color:#7c3aed;"><i class="ti ti-id-badge-2"></i></span>
    <span class="pp-brand-name">Payroll <span>Pro</span></span>
  </a>
  <div class="pp-nav-label">My Workspace</div>
  <nav class="pp-nav">
    <a class="{{ 'active' if request.path=='/employee/dashboard' else '' }}" href="/employee/dashboard"><i class="ti ti-layout-dashboard"></i>Dashboard</a>
    <a class="{{ 'active' if request.path=='/employee/profile' else '' }}" href="/employee/profile"><i class="ti ti-user-circle"></i>My Profile</a>
    <a class="{{ 'active' if request.path=='/employee/attendance' else '' }}" href="/employee/attendance"><i class="ti ti-clock"></i>Attendance & Punch</a>
    <a class="{{ 'active' if request.path=='/employee/leave' else '' }}" href="/employee/leave"><i class="ti ti-calendar-off"></i>My Leave</a>
    <a class="{{ 'active' if request.path=='/employee/payslip_page' else '' }}" href="/employee/payslip_page"><i class="ti ti-receipt"></i>Payslips</a>
    <a class="{{ 'active' if request.path=='/employee/appraisal' else '' }}" href="/employee/appraisal"><i class="ti ti-trending-up"></i>My Appraisal</a>
    <a class="{{ 'active' if request.path.startswith('/holidays') else '' }}" href="/holidays"><i class="ti ti-calendar-star"></i>Holidays</a>
    <a class="{{ 'active' if request.path=='/employee/notifications' else '' }}" href="/employee/notifications"><i class="ti ti-bell"></i>Notifications</a>
    <a class="{{ 'active' if request.path=='/employee/settings' else '' }}" href="/employee/settings"><i class="ti ti-settings"></i>Settings</a>
  </nav>
  <div class="pp-sidebar-bottom"><div class="pp-logout"><a class="pp-nav" href="/employee/logout" style="color:#fff;text-decoration:none;padding:10px 12px;"><i class="ti ti-logout"></i>Logout</a></div></div>
</aside>
<div class="pp-main">
  <header class="pp-topbar">
    <div class="pp-search"><span style="font-size:12px;color:var(--pp-muted);font-weight:700;">Employee self-service</span></div>
    <div class="pp-top-actions"><button class="pp-icon-btn" onclick="togglePayrollTheme()"><i class="ti ti-moon-stars" id="themeIcon"></i></button><div class="pp-user"><div class="pp-avatar" style="background:linear-gradient(135deg,#7c3aed,#a78bfa);">E</div></div></div>
  </header>
{% endif %}

<div class="pp-content">
{% with messages = get_flashed_messages() %}
  {% for m in messages %}<div class="alert alert-info pp-animate">{{m}}</div>{% endfor %}
{% endwith %}
{{ body|safe }}
</div>
{% if session.get('user') or session.get('employee_id') %}</div>{% endif %}
<script>
function setThemeIcon(){const dark=document.documentElement.getAttribute("data-bs-theme")==="dark";const i=document.getElementById("themeIcon");if(i)i.className=dark?"ti ti-sun":"ti ti-moon-stars";}
function togglePayrollTheme(){const h=document.documentElement;const n=h.getAttribute("data-bs-theme")==="dark"?"light":"dark";h.setAttribute("data-bs-theme",n);localStorage.setItem("payrollpro-theme",n);setThemeIcon();}
setThemeIcon();
document.querySelectorAll(".stat-value").forEach(el=>{const raw=el.textContent.trim();const m=raw.match(/^([^\\d]*)([\\d,]+)(.*)$/);if(!m)return;const p=m[1],t=parseInt(m[2].replace(/,/g,""),10),s=m[3];if(isNaN(t))return;let st=performance.now();function tick(now){let q=Math.min((now-st)/700,1),e=1-Math.pow(1-q,3);el.textContent=p+Math.floor(e*t).toLocaleString("en-IN")+s;if(q<1)requestAnimationFrame(tick);else el.textContent=p+t.toLocaleString("en-IN")+s;}requestAnimationFrame(tick);});
</script>
</body></html>
"""

def render(body, **kw):
    return render_template_string(BASE, body=render_template_string(body, **kw), **kw)

EMP_BASE = BASE

def render_emp(body, **kw):
    return render_template_string(EMP_BASE, body=render_template_string(body, **kw), **kw)

def employee_login_required(f):
    from functools import wraps
    @wraps(f)
    def wrap(*a, **kw):
        if not session.get("employee_id"):
            return redirect("/employee/login")
        return f(*a, **kw)
    return wrap

def login_required(f):
    from functools import wraps
    @wraps(f)
    def wrap(*a, **kw):
        if not session.get("user"):
            return redirect("/login")
        return f(*a, **kw)
    return wrap


# ---------------- AUTH ----------------
@app.route("/", methods=["GET"])
def home():
    if session.get("user"):
        return redirect("/dashboard")
    if session.get("employee_id"):
        return redirect("/employee/dashboard")
    return redirect("/login")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("username","").strip() == ADMIN_USER and check_password_hash(ADMIN_PASS_HASH, request.form.get("password","")):
            session.clear()
            session["user"] = ADMIN_USER
            return redirect("/dashboard")
        flash("Invalid admin credentials.")
    return render_template_string(r"""
    <!doctype html><html lang="en"><head>
    <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Admin Login — PayrollPro</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/core@latest/dist/css/tabler.min.css">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@latest/dist/tabler-icons.min.css">
    <style>
    body{margin:0;font-family:Inter,system-ui,sans-serif}.pp-login{min-height:100vh;display:grid;place-items:center;padding:30px;position:relative;overflow:hidden;background:radial-gradient(circle at 12% 18%,rgba(124,58,237,.23),transparent 28%),radial-gradient(circle at 88% 80%,rgba(99,102,241,.16),transparent 30%),linear-gradient(135deg,#f8f5ff,#f6f8ff)}.pp-login:before,.pp-login:after{content:"";position:absolute;border-radius:50%}.pp-login:before{width:440px;height:440px;left:-190px;bottom:-180px;background:linear-gradient(135deg,#7c3aed,#c4b5fd)}.pp-login:after{width:520px;height:520px;right:-250px;top:-220px;background:linear-gradient(135deg,#4c1d95,#a78bfa)}.shell{width:min(1020px,100%);min-height:610px;display:grid;grid-template-columns:1fr 1fr;background:rgba(255,255,255,.78);backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,.9);border-radius:28px;box-shadow:0 30px 80px rgba(31,41,55,.16);overflow:hidden;position:relative;z-index:2}.visual{padding:50px;display:flex;flex-direction:column;justify-content:space-between;color:#fff;position:relative;overflow:hidden}.visual:after{content:"";position:absolute;width:330px;height:330px;border-radius:50%;right:-130px;bottom:-160px;background:rgba(255,255,255,.13)}.admin{background:linear-gradient(145deg,#b90f1d,#f33b4a)}.copy{max-width:370px;position:relative;z-index:2}.copy h2{font-size:35px;line-height:1.05;margin:22px 0 12px;font-weight:850;letter-spacing:-1px}.copy p{font-size:14px;line-height:1.7;color:rgba(255,255,255,.84)}.office{position:absolute;right:45px;bottom:45px;width:300px;height:190px;border-radius:18px;background:linear-gradient(160deg,rgba(255,255,255,.24),rgba(255,255,255,.05));border:1px solid rgba(255,255,255,.3);box-shadow:0 25px 50px rgba(0,0,0,.14)}.office:before{content:"";position:absolute;left:30px;right:30px;top:30px;height:4px;background:rgba(255,255,255,.6);box-shadow:0 35px 0 rgba(255,255,255,.32),0 70px 0 rgba(255,255,255,.2)}.form{padding:50px;display:flex;align-items:center;background:#fff}.inner{width:100%;max-width:390px;margin:auto}.logo{display:flex;align-items:center;gap:10px;font-size:20px;font-weight:850;margin-bottom:36px}.mark{width:40px;height:40px;border-radius:12px;background:#ede9fe;color:#7c3aed;display:grid;place-items:center;font-size:21px}.inner h1{font-size:29px;font-weight:850;letter-spacing:-.7px;margin-bottom:7px}.lead{font-size:13px;color:#718096;margin-bottom:26px}.label{font-size:11px;font-weight:800;margin-bottom:7px;display:block}.field{margin-bottom:15px}.form-control{height:44px;border-radius:10px}.submit{height:46px;width:100%;border:0;border-radius:10px;color:#fff;font-weight:800;background:linear-gradient(135deg,#7c3aed,#a78bfa);box-shadow:0 9px 22px rgba(124,58,237,.22)}.switch{display:flex;justify-content:center;gap:5px;margin-top:22px;font-size:12px;color:#718096}.switch a{color:#7c3aed;font-weight:800;text-decoration:none}.secure{text-align:center;color:#718096;font-size:10px;margin-top:24px}@media(max-width:850px){.shell{grid-template-columns:1fr}.visual{min-height:270px}.office{display:none}}@media(max-width:550px){.pp-login{padding:12px}.form,.visual{padding:30px 24px}}
    </style></head><body>
    <div class="pp-login"><div class="shell">
      <section class="visual admin"><div class="copy">
        <div style="font-weight:850;font-size:20px;">PAYROLL <span style="font-weight:500;">PRO</span></div>
        <h2>Welcome back!</h2>
        <p>Manage your organization, employees and payroll — all in one place.</p>
      </div><div class="office"></div><div style="font-size:11px;opacity:.85;position:relative;z-index:2;">Secure • Reliable • Confidential</div></section>
      <section class="form"><div class="inner">
        <div class="logo"><span class="mark"><i class="ti ti-users"></i></span>PayrollPro</div>
        <h1>Admin Login</h1><div class="lead">Secure access to your payroll dashboard.</div>
        {% with messages=get_flashed_messages() %}{% for m in messages %}<div class="alert alert-danger py-2">{{m}}</div>{% endfor %}{% endwith %}
        <form method="post">
          <div class="field"><label class="label">Username</label><input class="form-control" name="username" placeholder="Enter admin username" required></div>
          <div class="field"><label class="label">Password</label><input class="form-control" type="password" name="password" placeholder="Enter password" required></div>
          <div class="d-flex justify-content-between align-items-center mb-4" style="font-size:11px;color:#718096;"><label><input type="checkbox" class="form-check-input me-1"> Remember me</label><a href="/forgot-password" style="color:#7c3aed;font-weight:700;text-decoration:none;">Forgot password?</a></div>
          <button class="submit">Login <i class="ti ti-arrow-right ms-1"></i></button>
        </form>
        <div class="switch">Are you an employee? <a href="/employee/login">Employee Login</a></div>
        <div class="secure"><i class="ti ti-shield-check"></i> Secure &nbsp;•&nbsp; Reliable &nbsp;•&nbsp; Confidential</div>
      </div></section>
    </div></div></body></html>
    """)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
@login_required
def dashboard():
    total = Employee.query.count()
    active_count = Employee.query.filter_by(status="Active").count()
    inactive_count = Employee.query.filter_by(status="Inactive").count()
    today = str(date.today())
    present = Attendance.query.filter_by(date=today, status="Present").count()
    absent = Attendance.query.filter_by(date=today, status="Absent").count()
    onleave = Attendance.query.filter_by(date=today, status="Leave").count()
    pending = LeaveRequest.query.filter_by(status="Pending").count()
    payroll_total = sum(e.net for e in Employee.query.all())

    trend_labels, trend_present, trend_absent = [], [], []
    for i in range(6, -1, -1):
        d = str(date.today() - timedelta(days=i))
        trend_labels.append(d[5:])
        trend_present.append(Attendance.query.filter_by(date=d, status="Present").count())
        trend_absent.append(Attendance.query.filter_by(date=d, status="Absent").count())

    dept_totals = {}
    for e in Employee.query.all():
        dept = e.department or "Unassigned"
        dept_totals[dept] = dept_totals.get(dept, 0) + e.net

    recent = Employee.query.order_by(Employee.id.desc()).limit(5).all()
    upcoming = Holiday.query.filter(Holiday.date >= today).order_by(Holiday.date).limit(4).all()
    pending_leaves = LeaveRequest.query.filter_by(status="Pending").order_by(LeaveRequest.id.desc()).limit(4).all()
    emp_map = {e.id:e for e in Employee.query.all()}
    appraisal_due = [e for e in Employee.query.filter_by(status="Active").all() if e.appraisal_due][:4]

    notification_count = pending + len(appraisal_due)

    return render(r"""
    <div class="pp-page-heading pp-animate">
      <div><div class="pp-eyebrow">Overview</div><h1 class="pp-title">Good morning, Admin 👋</h1><div class="pp-subtitle">Here's what's happening across your organization today.</div></div>
      <div class="d-flex gap-2">
        <a href="/employees" class="btn pp-btn-soft"><i class="ti ti-user-plus me-1"></i>Add Employee</a>
        <a href="/payroll" class="btn pp-btn-primary"><i class="ti ti-report-money me-1"></i>Process Payroll</a>
      </div>
    </div>

    <div class="row g-3 mb-4">
      <div class="col-6 col-xl pp-animate pp-delay-1"><div class="pp-card pp-stat" style="--stat-bg:#fee2e2;--stat-color:#dc2626"><div class="pp-stat-icon"><i class="ti ti-users"></i></div><div class="pp-stat-label">Total Employees</div><div class="pp-stat-value stat-value">{{t}}</div><div class="pp-stat-change" style="color:#16a34a;">Active workforce</div></div></div>
      <div class="col-6 col-xl pp-animate pp-delay-1"><div class="pp-card pp-stat" style="--stat-bg:#dcfce7;--stat-color:#16a34a"><div class="pp-stat-icon"><i class="ti ti-user-check"></i></div><div class="pp-stat-label">Present Today</div><div class="pp-stat-value stat-value">{{p}}</div><div class="pp-stat-change" style="color:#16a34a;">{{present_pct}}% of workforce</div></div></div>
      <div class="col-6 col-xl pp-animate pp-delay-2"><div class="pp-card pp-stat" style="--stat-bg:#fef3c7;--stat-color:#d97706"><div class="pp-stat-icon"><i class="ti ti-calendar-off"></i></div><div class="pp-stat-label">On Leave</div><div class="pp-stat-value stat-value">{{l}}</div><div class="pp-stat-change" style="color:#d97706;">Today</div></div></div>
      <div class="col-6 col-xl pp-animate pp-delay-2"><div class="pp-card pp-stat" style="--stat-bg:#fee2e2;--stat-color:#dc2626"><div class="pp-stat-icon"><i class="ti ti-user-x"></i></div><div class="pp-stat-label">Absent Today</div><div class="pp-stat-value stat-value">{{ab}}</div><div class="pp-stat-change" style="color:#dc2626;">Needs attention</div></div></div>
      <div class="col-12 col-xl pp-animate pp-delay-3"><div class="pp-card pp-stat" style="--stat-bg:#ede9fe;--stat-color:#7c3aed"><div class="pp-stat-icon"><i class="ti ti-currency-rupee"></i></div><div class="pp-stat-label">Current Month Payroll</div><div class="pp-stat-value stat-value">₹{{ '%.0f'|format(pt) }}</div><div class="pp-stat-change" style="color:#7c3aed;">Estimated net payroll</div></div></div>
    </div>

    <div class="row g-3 mb-3">
      <div class="col-xl-8">
        <div class="pp-card pp-card-pad pp-animate pp-delay-2">
          <div class="d-flex justify-content-between align-items-center mb-3"><div><h3 class="pp-section-title">Payroll Overview</h3><div class="pp-section-muted">Attendance and workforce trend — last 7 days</div></div><a href="/reports" class="btn btn-sm btn-outline-secondary">View reports</a></div>
          <div class="pp-chart-wrap"><canvas id="trendChart"></canvas></div>
        </div>
      </div>
      <div class="col-xl-4">
        <div class="pp-card pp-card-pad h-100 pp-animate pp-delay-3">
          <div class="d-flex justify-content-between align-items-center mb-2"><div><h3 class="pp-section-title">Employees by Department</h3><div class="pp-section-muted">Current workforce</div></div></div>
          <div class="pp-mini-chart"><canvas id="deptChart"></canvas></div>
        </div>
      </div>
    </div>

    <div class="row g-3 mb-3">
      <div class="col-lg-4">
        <div class="pp-card pp-card-pad h-100"><div class="d-flex justify-content-between align-items-center mb-2"><h3 class="pp-section-title">Pending Approvals</h3><a href="/leave" class="pp-section-muted text-decoration-none">View all</a></div>
        {% for lq in pending_leaves %}
          <div class="pp-list-item"><div class="pp-list-icon" style="background:#fee2e2;color:#dc2626;"><i class="ti ti-calendar-event"></i></div><div class="flex-fill"><div style="font-size:12px;font-weight:800;">{{emp_map[lq.emp_id].name if lq.emp_id in emp_map else 'Employee'}}</div><div class="pp-section-muted">{{lq.leave_type}} · {{lq.start_date}}</div></div><span class="pp-badge pp-badge-warning">Pending</span></div>
        {% else %}<div class="pp-empty">No pending approvals 🎉</div>{% endfor %}
        </div>
      </div>
      <div class="col-lg-4">
        <div class="pp-card pp-card-pad h-100"><div class="d-flex justify-content-between align-items-center mb-2"><h3 class="pp-section-title">Upcoming Holidays</h3><a href="/holidays" class="pp-section-muted text-decoration-none">Calendar</a></div>
        {% for h in upcoming %}
          <div class="pp-list-item"><div class="pp-list-icon" style="background:#fff1f2;color:#e11d2e;"><i class="ti ti-calendar-star"></i></div><div class="flex-fill"><div style="font-size:12px;font-weight:800;">{{h.name}}</div><div class="pp-section-muted">{{h.date}}</div></div></div>
        {% else %}<div class="pp-empty">No upcoming holidays added.</div>{% endfor %}
        </div>
      </div>
      <div class="col-lg-4">
        <div class="pp-card pp-card-pad h-100"><div class="d-flex justify-content-between align-items-center mb-2"><h3 class="pp-section-title">Important Alerts</h3><a href="/notifications" class="pp-section-muted text-decoration-none">See all</a></div>
          <div class="pp-alert mb-2"><div class="pp-list-icon" style="background:#fee2e2;color:#dc2626;"><i class="ti ti-bell"></i></div><div><div style="font-size:11px;font-weight:800;">{{pending}} leave request(s) pending</div><div class="pp-section-muted">Review before payroll processing.</div></div></div>
          <div class="pp-alert mb-2"><div class="pp-list-icon" style="background:#fef3c7;color:#d97706;"><i class="ti ti-star"></i></div><div><div style="font-size:11px;font-weight:800;">{{appraisal_due|length}} appraisal(s) due</div><div class="pp-section-muted">Review employee appraisal dates.</div></div></div>
          <div class="pp-alert"><div class="pp-list-icon" style="background:#dcfce7;color:#15803d;"><i class="ti ti-shield-check"></i></div><div><div style="font-size:11px;font-weight:800;">System is ready</div><div class="pp-section-muted">All core payroll modules are online.</div></div></div>
        </div>
      </div>
    </div>

    <div class="pp-card pp-card-pad">
      <div class="d-flex justify-content-between align-items-center mb-2"><h3 class="pp-section-title">Recent Employees</h3><a href="/employees" class="pp-section-muted text-decoration-none">View all employees →</a></div>
      <div class="table-responsive"><table class="table pp-table"><thead><tr><th>Employee</th><th>Department</th><th>Designation</th><th>Joining Date</th><th>Salary</th><th>Status</th></tr></thead><tbody>
      {% for e in recent %}<tr><td><div class="pp-person"><div class="pp-person-avatar">{{e.name[:1]|upper}}</div><div><div style="font-weight:800;">{{e.name}}</div><div class="pp-section-muted">{{e.email}}</div></div></div></td><td>{{e.department}}</td><td>{{e.designation}}</td><td>{{e.date_joined}}</td><td style="font-weight:800;">₹{{'%.0f'|format(e.net)}}</td><td><span class="pp-badge {{'pp-badge-success' if e.status=='Active' else 'pp-badge-gray'}}">{{e.status}}</span></td></tr>{% else %}<tr><td colspan="6" class="pp-empty">No employees yet.</td></tr>{% endfor %}
      </tbody></table></div>
    </div>

    <script>
    const ppText=getComputedStyle(document.documentElement).getPropertyValue('--pp-muted')||'#718096';
    const ppBorder=getComputedStyle(document.documentElement).getPropertyValue('--pp-border')||'#e7eaf0';
    new Chart(document.getElementById('trendChart'),{type:'line',data:{labels:{{trend_labels|tojson}},datasets:[
      {label:'Present',data:{{trend_present|tojson}},borderColor:'#16a34a',backgroundColor:'rgba(22,163,74,.08)',tension:.38,fill:true,borderWidth:2,pointRadius:3},
      {label:'Absent',data:{{trend_absent|tojson}},borderColor:'#e11d2e',backgroundColor:'rgba(225,29,46,.04)',tension:.38,fill:true,borderWidth:2,pointRadius:3}
    ]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:'bottom',labels:{boxWidth:8,usePointStyle:true,color:ppText,font:{size:10,weight:'600'}}}},scales:{x:{grid:{display:false},ticks:{color:ppText,font:{size:10}}},y:{beginAtZero:true,grid:{color:ppBorder},ticks:{precision:0,color:ppText,font:{size:10}}}}}});
    new Chart(document.getElementById('deptChart'),{type:'doughnut',data:{labels:{{dept_labels|tojson}},datasets:[{data:{{dept_values|tojson}},backgroundColor:['#e11d2e','#2563eb','#16a34a','#f59e0b','#7c3aed','#0891b2'],borderWidth:0}]},options:{cutout:'68%',plugins:{legend:{position:'bottom',labels:{boxWidth:9,usePointStyle:true,color:ppText,font:{size:9,weight:'600'}}}}}});
    </script>
    """, t=total, p=present, ab=absent, l=onleave, pd=pending, pt=payroll_total,
         present_pct=round((present/total*100),1) if total else 0,
         trend_labels=trend_labels, trend_present=trend_present, trend_absent=trend_absent,
         dept_labels=list(dept_totals.keys()), dept_values=[round(v,2) for v in dept_totals.values()],
         recent=recent, upcoming=upcoming, pending_leaves=pending_leaves, emp_map=emp_map,
         appraisal_due=appraisal_due, notification_count=notification_count)


# ---------------- REPORTS / NOTIFICATIONS / SETTINGS ----------------
@app.route("/reports")
@login_required
def reports():
    total=Employee.query.count(); active=Employee.query.filter_by(status="Active").count()
    payroll=sum(e.net for e in Employee.query.all()); pending=LeaveRequest.query.filter_by(status="Pending").count()
    return render(r"""
    <div class="pp-page-heading"><div><div class="pp-eyebrow">Insights</div><h1 class="pp-title">Reports & Analytics</h1><div class="pp-subtitle">Generate, preview, print and download complete workforce reports.</div></div><button class="btn pp-btn-primary" onclick="window.print()"><i class="ti ti-printer me-1"></i>Export / Print</button></div>
    <div class="row g-3 mb-3">
      <div class="col-md-3"><div class="pp-card pp-card-pad"><div class="pp-section-muted">Employees</div><div class="fs-2 fw-bold">{{total}}</div></div></div>
      <div class="col-md-3"><div class="pp-card pp-card-pad"><div class="pp-section-muted">Active</div><div class="fs-2 fw-bold">{{active}}</div></div></div>
      <div class="col-md-3"><div class="pp-card pp-card-pad"><div class="pp-section-muted">Net Payroll</div><div class="fs-2 fw-bold">₹{{'%.0f'|format(payroll)}}</div></div></div>
      <div class="col-md-3"><div class="pp-card pp-card-pad"><div class="pp-section-muted">Pending Leaves</div><div class="fs-2 fw-bold">{{pending}}</div></div></div>
    </div>
    <div class="pp-card pp-card-pad mb-3">
      <h3 class="pp-section-title mb-3">Download Reports</h3>
      <form class="row g-2 align-items-end" onsubmit="return false;">
        <div class="col-md-4"><label class="form-label small">Report</label><select id="reportType" class="form-select"><option value="employees">Employee Report</option><option value="payroll">Payroll Report</option><option value="attendance">Attendance Report</option><option value="leave">Leave Report</option><option value="appraisal">Appraisal Report</option><option value="holidays">Holiday Report</option></select></div>
        <div class="col-md-3"><label class="form-label small">Month (for payroll/attendance)</label><input id="reportMonth" class="form-control" type="month" value="{{month}}"></div>
        <div class="col-md-2"><label class="form-label small">Format</label><select id="reportFmt" class="form-select"><option value="xlsx">Excel</option><option value="csv">CSV</option><option value="pdf">PDF</option></select></div>
        <div class="col-md-3"><button class="btn pp-btn-primary w-100" onclick="downloadReport()"><i class="ti ti-download me-1"></i>Generate & Download</button></div>
      </form>
      <div class="small text-muted mt-2">Employee report includes contact, DOB/age, work, tenure and salary fields. Payroll, attendance, leave, appraisal and holiday reports are generated from the live database.</div>
    </div>
    <div class="pp-card pp-card-pad"><h3 class="pp-section-title mb-3">Available Reports</h3><div class="row g-3">
      {% for icon,name,desc,typ in [('ti-users','Employee Report','Complete employee master data','employees'),('ti-report-money','Payroll Report','Salary, deductions, overtime and net payroll','payroll'),('ti-clock','Attendance Report','Daily attendance and punch insights','attendance'),('ti-calendar-off','Leave Report','Leave usage and requests','leave'),('ti-trending-up','Appraisal Report','Ratings, hikes and review dates','appraisal'),('ti-calendar-star','Holiday Report','2026 public holiday calendar','holidays')] %}
      <div class="col-md-6 col-xl-4"><button type="button" class="pp-quick w-100 text-start" onclick="document.getElementById('reportType').value='{{typ}}';document.getElementById('reportFmt').value='xlsx';downloadReport()"><i class="ti {{icon}}"></i><div><div style="font-size:12px;font-weight:800;">{{name}}</div><div class="pp-section-muted">{{desc}}</div><div class="small mt-1" style="color:var(--pp-primary);font-weight:700;">Download →</div></div></button></div>
      {% endfor %}
    </div></div>
    <script>function downloadReport(){const t=document.getElementById('reportType').value,f=document.getElementById('reportFmt').value,m=document.getElementById('reportMonth').value;let u='/reports/download/'+t+'/'+f;if(m)u+='?month='+encodeURIComponent(m);window.location.href=u;}</script>
    """, total=total, active=active, payroll=payroll, pending=pending, month=str(date.today())[:7])

def _report_rows(report_type, month):
    if report_type == 'employees':
        headers=['Employee ID','Name','Email','Phone','DOB','Age','Gender','Department','Designation','Joining Date','Tenure','Employment Type','Manager','Location','Shift','Working Hours','Status','Basic','HRA','Bonus','Allowance','PF','Tax','Other Deduction','Net Salary','Qualification','College','Skills','Certifications','Previous Company','Experience Years']
        rows=[]
        for e in Employee.query.order_by(Employee.id).all(): rows.append([e.id,e.name,e.email,e.phone,e.dob or '',e.age or '',e.gender or '',e.department,e.designation,e.date_joined or '',e.tenure_label,e.employment_type or '',e.reporting_manager or '',e.work_location or '',e.shift or '',e.working_hours or 8,e.status,e.basic or 0,e.hra or 0,e.bonus or 0,e.allowance or 0,e.pf or 0,e.tax or 0,e.other_ded or 0,round(e.net,2),e.qualification or '',e.college or '',e.skills or '',e.certifications or '',e.previous_company or '',e.experience_years or 0])
        return headers,rows
    if report_type == 'payroll':
        headers=['Employee ID','Name','Department','Basic','HRA','Bonus','Allowance','Gross','PF','Tax','Other Deduction','Net Salary','Overtime Hours','Overtime Pay']
        rows=[]
        for e in Employee.query.order_by(Employee.id).all():
            logs=PunchLog.query.filter(PunchLog.emp_id==e.id,PunchLog.date.like(f'{month}%'),PunchLog.time_out.isnot(None)).all(); ot=round(sum(x.overtime_hours for x in logs),2); otp=round(ot*e.per_hour_rate*1.5,2); gross=sum([e.basic or 0,e.hra or 0,e.bonus or 0,e.allowance or 0])
            rows.append([e.id,e.name,e.department,e.basic or 0,e.hra or 0,e.bonus or 0,e.allowance or 0,round(gross,2),e.pf or 0,e.tax or 0,e.other_ded or 0,round(e.net+otp,2),ot,otp])
        return headers,rows
    if report_type == 'attendance':
        headers=['Date','Employee ID','Employee','Department','Status','Punch In','Punch Out','Hours','Overtime Hours','Source']; rows=[]
        emps={e.id:e for e in Employee.query.all()}
        for a in Attendance.query.filter(Attendance.date.like(f'{month}%')).order_by(Attendance.date,Attendance.emp_id).all():
            e=emps.get(a.emp_id); p=PunchLog.query.filter_by(emp_id=a.emp_id,date=a.date).first(); rows.append([a.date,a.emp_id,e.name if e else '',e.department if e else '',a.status,p.time_in if p else '',p.time_out if p else '',p.hours if p else 0,p.overtime_hours if p else 0,a.source])
        return headers,rows
    if report_type == 'leave':
        headers=['Leave ID','Employee ID','Employee','Department','Type','From','To','Reason','Status']; rows=[]; emps={e.id:e for e in Employee.query.all()}
        for l in LeaveRequest.query.order_by(LeaveRequest.id.desc()).all():
            e=emps.get(l.emp_id); rows.append([l.id,l.emp_id,e.name if e else '',e.department if e else '',l.leave_type,l.start_date,l.end_date,l.reason,l.status])
        return headers,rows
    if report_type == 'appraisal':
        headers=['Employee ID','Name','Department','Designation','Last Appraisal','Next Appraisal','Status','Rating','Hike %','Current Basic','Comments']; rows=[]
        for e in Employee.query.order_by(Employee.id).all(): rows.append([e.id,e.name,e.department,e.designation,e.last_appraisal_date or '',e.next_appraisal_date or '', 'Due' if e.appraisal_due else 'Upcoming',e.appraisal_rating or 0,e.hike_pct or 0,e.basic or 0,e.appraisal_comments or ''])
        return headers,rows
    if report_type == 'holidays':
        headers=['Date','Holiday','Day']; rows=[]
        for h in Holiday.query.order_by(Holiday.date).all():
            try: day=datetime.strptime(h.date,'%Y-%m-%d').strftime('%A')
            except ValueError: day=''
            rows.append([h.date,h.name,day])
        return headers,rows
    raise ValueError('Unknown report type')

@app.route('/reports/download/<report_type>/<fmt>')
@login_required
def report_download(report_type,fmt):
    if report_type not in {'employees','payroll','attendance','leave','appraisal','holidays'} or fmt not in {'csv','xlsx','pdf'}: return 'Invalid report request',400
    headers,rows=_report_rows(report_type,request.args.get('month',str(date.today())[:7]))
    filename=f'payrollpro_{report_type}_{date.today().isoformat()}'
    if fmt=='csv':
        buf=io.StringIO(); w=csv.writer(buf); w.writerow(headers); w.writerows(rows); return send_file(io.BytesIO(buf.getvalue().encode('utf-8-sig')),mimetype='text/csv',as_attachment=True,download_name=filename+'.csv')
    if fmt=='xlsx':
        try: from openpyxl import Workbook
        except ImportError: return 'Excel export requires openpyxl. Run: python -m pip install openpyxl',500
        wb=Workbook(); ws=wb.active; ws.title=report_type.title(); ws.append(headers)
        for r in rows: ws.append(r)
        ws.freeze_panes='A2'; ws.auto_filter.ref=ws.dimensions
        for col in ws.columns:
            width=min(max(len(str(c.value or '')) for c in col)+2,40); ws.column_dimensions[col[0].column_letter].width=width
        out=io.BytesIO(); wb.save(out); out.seek(0); return send_file(out,mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',as_attachment=True,download_name=filename+'.xlsx')
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet
    except ImportError: return 'PDF export requires reportlab. Run: python -m pip install reportlab',500
    out=io.BytesIO(); doc=SimpleDocTemplate(out,pagesize=landscape(A4),leftMargin=20,rightMargin=20,topMargin=20,bottomMargin=20); styles=getSampleStyleSheet()
    safe=[[str(x)[:40] for x in headers]]+[[str(x)[:40] for x in r] for r in rows]
    if len(safe[0])>10: safe=[safe[0]]+[r for r in safe[1:]]
    t=Table(safe,repeatRows=1); t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#7c3aed')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTSIZE',(0,0),(-1,-1),6),('GRID',(0,0),(-1,-1),.25,colors.HexColor('#d8dce6')),('VALIGN',(0,0),(-1,-1),'TOP')]))
    doc.build([Paragraph(f'PayrollPro — {report_type.title()} Report',styles['Title']),t]); out.seek(0); return send_file(out,mimetype='application/pdf',as_attachment=True,download_name=filename+'.pdf')

@app.route("/notifications")
@login_required
def notifications():
    pending=LeaveRequest.query.filter_by(status="Pending").order_by(LeaveRequest.id.desc()).all()
    due=[e for e in Employee.query.filter_by(status="Active").all() if e.appraisal_due]
    return render(r"""
    <div class="pp-page-heading"><div><div class="pp-eyebrow">Workspace</div><h1 class="pp-title">Notifications</h1><div class="pp-subtitle">Stay on top of approvals, payroll and employee actions.</div></div><button class="btn btn-outline-secondary" onclick="document.querySelectorAll('.pp-notif').forEach(x=>x.style.opacity='.55')">Mark all as read</button></div>
    <div class="pp-card pp-card-pad">
      {% for lq in pending %}<div class="pp-list-item pp-notif"><div class="pp-list-icon" style="background:#fee2e2;color:#dc2626;"><i class="ti ti-calendar-event"></i></div><div class="flex-fill"><div style="font-size:12px;font-weight:800;">Leave request pending</div><div class="pp-section-muted">Employee ID {{lq.emp_id}} requested {{lq.leave_type}} from {{lq.start_date}} to {{lq.end_date}}.</div></div><a href="/leave" class="btn btn-sm pp-btn-soft">Review</a></div>{% endfor %}
      {% for e in due %}<div class="pp-list-item pp-notif"><div class="pp-list-icon" style="background:#fef3c7;color:#d97706;"><i class="ti ti-star"></i></div><div class="flex-fill"><div style="font-size:12px;font-weight:800;">Appraisal due</div><div class="pp-section-muted">{{e.name}} has an appraisal due.</div></div><a href="/appraisals" class="btn btn-sm btn-outline-secondary">Open</a></div>{% endfor %}
      <div class="pp-list-item pp-notif"><div class="pp-list-icon" style="background:#dcfce7;color:#15803d;"><i class="ti ti-shield-check"></i></div><div class="flex-fill"><div style="font-size:12px;font-weight:800;">PayrollPro system ready</div><div class="pp-section-muted">Core employee, attendance, leave and payroll modules are available.</div></div><span class="pp-badge pp-badge-success">System</span></div>
      {% if not pending and not due %}<div class="pp-empty">You're all caught up 🎉</div>{% endif %}
    </div>
    """, pending=pending, due=due)

@app.route("/settings", methods=["GET","POST"])
@login_required
def settings():
    if request.method=="POST":
        flash("Settings saved for this session. Company configuration can be connected to the database next.")
        return redirect("/settings")
    return render(r"""
    <div class="pp-page-heading"><div><div class="pp-eyebrow">System</div><h1 class="pp-title">Settings</h1><div class="pp-subtitle">Configure your company, payroll rules and interface.</div></div></div>
    <form method="post">
      <div class="row g-3">
        <div class="col-lg-6"><div class="pp-card pp-card-pad"><h3 class="pp-section-title mb-3"><i class="ti ti-building me-1"></i> Company</h3><div class="row g-3"><div class="col-12"><label class="form-label">Company name</label><input class="form-control" value="PayrollPro Company"></div><div class="col-md-6"><label class="form-label">Email</label><input class="form-control" placeholder="hr@company.com"></div><div class="col-md-6"><label class="form-label">Phone</label><input class="form-control" placeholder="+91"></div><div class="col-12"><label class="form-label">Address</label><textarea class="form-control" rows="3" placeholder="Company address"></textarea></div></div></div></div>
        <div class="col-lg-6"><div class="pp-card pp-card-pad"><h3 class="pp-section-title mb-3"><i class="ti ti-report-money me-1"></i> Payroll</h3><div class="row g-3"><div class="col-md-6"><label class="form-label">Pay cycle</label><select class="form-select"><option>Monthly</option><option>Bi-weekly</option></select></div><div class="col-md-6"><label class="form-label">Standard work hours</label><input class="form-control" value="8"></div><div class="col-md-6"><label class="form-label">PF rate (%)</label><input class="form-control" value="12"></div><div class="col-md-6"><label class="form-label">Default leave days</label><input class="form-control" value="12"></div></div></div></div>
        <div class="col-12"><div class="pp-card pp-card-pad"><h3 class="pp-section-title mb-3"><i class="ti ti-palette me-1"></i> Appearance & Security</h3><div class="d-flex flex-wrap gap-2"><button type="button" class="btn btn-outline-secondary" onclick="togglePayrollTheme()">Toggle Light / Dark Mode</button><a href="/admin/reset_data" class="btn btn-outline-danger">Reset demo data</a></div></div></div>
      </div><button class="btn pp-btn-primary mt-3">Save Settings</button>
    </form>
    """)

# ---------------- EMPLOYEES ----------------
# Salary components are offered as ready-made presets (computed as a % of
# Basic, or a flat slab) since most companies follow one of a handful of
# standard structures — pick the closest one, or choose "Custom" to type
# an exact figure. This also keeps the numbers consistent employee-to-employee.
@app.route("/employees", methods=["GET", "POST"])
@login_required
def employees():
    if request.method == "POST":
        f = request.form
        try:
            new_emp = Employee(
                name=f["name"].strip(), department=f["department"].strip(), designation=f["designation"].strip(),
                email=f["email"].strip(), phone=f["phone"].strip(), date_joined=f.get("date_joined") or str(date.today()),
                basic=float(f["basic"] or 0), hra=float(f["hra_amount"] or 0), bonus=float(f["bonus_amount"] or 0),
                allowance=float(f["allowance_amount"] or 0), pf=float(f["pf_amount"] or 0),
                tax=float(f["tax_amount"] or 0), other_ded=float(f.get("other_ded") or 0),
            )
        except (KeyError, ValueError):
            flash("Please fill in all required fields with valid numbers.")
            return redirect("/employees")
        new_emp.set_password("employee123")  # default — the employee should change this after first login
        db.session.add(new_emp)
        db.session.commit()
        flash("Employee added. Default login password: employee123")
        return redirect("/employees")

    search = request.args.get("q", "").strip()
    query = Employee.query
    if search:
        like = f"%{search}%"
        query = query.filter(db.or_(Employee.name.ilike(like), Employee.department.ilike(like),
                                     Employee.designation.ilike(like), Employee.email.ilike(like)))
    emps = query.order_by(Employee.name).all()

    return render("""
    <h4>Add Employee</h4>
    <form method="post" class="row g-2 mb-4" id="empForm">
      <div class="col-md-3"><input class="form-control" name="name" placeholder="Name" required></div>
      <div class="col-md-3"><input class="form-control" name="department" placeholder="Department" required></div>
      <div class="col-md-3"><input class="form-control" name="designation" placeholder="Designation" required></div>
      <div class="col-md-3"><input class="form-control" type="date" name="date_joined" value="{{today}}" title="Date Joined"></div>
      <div class="col-md-4"><input class="form-control" name="email" placeholder="Email" required></div>
      <div class="col-md-4"><input class="form-control" name="phone" placeholder="Phone" required></div>
      <div class="col-md-4"><input class="form-control" id="basic" name="basic" placeholder="Basic Salary (₹/month)" type="number" step="0.01" required></div>

      <div class="col-md-3">
        <label class="form-label small text-muted mb-0">HRA</label>
        <select class="form-select preset" id="hra_preset" data-pct-of="basic" data-target="hra_amount">
          <option value="0">None</option>
          <option value="20" selected>20% of Basic</option>
          <option value="40">40% of Basic (metro)</option>
          <option value="50">50% of Basic</option>
          <option value="custom">Custom amount</option>
        </select>
        <input class="form-control form-control-sm mt-1" id="hra_amount" name="hra_amount" type="number" step="0.01" readonly>
      </div>
      <div class="col-md-3">
        <label class="form-label small text-muted mb-0">Bonus</label>
        <select class="form-select preset" id="bonus_preset" data-pct-of="basic" data-target="bonus_amount">
          <option value="0" selected>None</option>
          <option value="8.33">8.33% of Basic (statutory min.)</option>
          <option value="10">10% of Basic</option>
          <option value="custom">Custom amount</option>
        </select>
        <input class="form-control form-control-sm mt-1" id="bonus_amount" name="bonus_amount" type="number" step="0.01" readonly>
      </div>
      <div class="col-md-3">
        <label class="form-label small text-muted mb-0">Allowance</label>
        <select class="form-select preset" id="allowance_preset" data-flat="1" data-target="allowance_amount">
          <option value="0">None</option>
          <option value="2000" selected>₹2,000 (conveyance+misc)</option>
          <option value="5000">₹5,000</option>
          <option value="10000">₹10,000 (special allowance)</option>
          <option value="custom">Custom amount</option>
        </select>
        <input class="form-control form-control-sm mt-1" id="allowance_amount" name="allowance_amount" type="number" step="0.01" readonly>
      </div>
      <div class="col-md-3">
        <label class="form-label small text-muted mb-0">PF (deduction)</label>
        <select class="form-select preset" id="pf_preset" data-pct-of="basic" data-target="pf_amount">
          <option value="0">Not applicable</option>
          <option value="12" selected>12% of Basic (EPF standard)</option>
          <option value="custom">Custom amount</option>
        </select>
        <input class="form-control form-control-sm mt-1" id="pf_amount" name="pf_amount" type="number" step="0.01" readonly>
      </div>
      <div class="col-md-3">
        <label class="form-label small text-muted mb-0">Tax / TDS (deduction)</label>
        <select class="form-select preset" id="tax_preset" data-pct-of="basic" data-target="tax_amount">
          <option value="0" selected>None (below taxable slab)</option>
          <option value="5">5% of Basic</option>
          <option value="10">10% of Basic</option>
          <option value="20">20% of Basic</option>
          <option value="custom">Custom amount</option>
        </select>
        <input class="form-control form-control-sm mt-1" id="tax_amount" name="tax_amount" type="number" step="0.01" readonly>
      </div>
      <div class="col-md-3">
        <label class="form-label small text-muted mb-0">Other Deductions</label>
        <input class="form-control" name="other_ded" placeholder="₹0.00" type="number" step="0.01" value="0">
      </div>

      <div class="col-12"><button class="btn btn-primary">Add Employee</button></div>
    </form>

    <script>
    function recalcPresets() {
      const basic = parseFloat(document.getElementById('basic').value) || 0;
      document.querySelectorAll('.preset').forEach(sel => {
        const target = document.getElementById(sel.dataset.target);
        if (sel.value === 'custom') { target.readOnly = false; target.focus(); return; }
        target.readOnly = true;
        if (sel.dataset.pctOf) target.value = (basic * parseFloat(sel.value) / 100).toFixed(2);
        else if (sel.dataset.flat) target.value = parseFloat(sel.value).toFixed(2);
      });
    }
    document.getElementById('basic').addEventListener('input', recalcPresets);
    document.querySelectorAll('.preset').forEach(sel => sel.addEventListener('change', recalcPresets));
    recalcPresets();
    </script>

    <div class="d-flex justify-content-between align-items-center mb-2 flex-wrap gap-2">
      <h4 class="mb-0">All Employees ({{emps|length}})</h4>
      <div class="d-flex gap-2">
        <form method="get" class="d-flex gap-1">
          <input class="form-control form-control-sm" name="q" value="{{search}}" placeholder="Search name/dept/designation...">
          <button class="btn btn-sm btn-outline-primary"><i class="ti ti-search"></i></button>
        </form>
        <a href="/employees/export" class="btn btn-sm btn-outline-success"><i class="ti ti-file-spreadsheet"></i> Export CSV</a>
      </div>
    </div>
    <div class="card">
    <div class="table-responsive">
    <table class="table table-bordered align-middle card-table">
    <tr><th>Name</th><th>Dept</th><th>Designation</th><th>Email</th><th>Joined</th><th>Tenure</th><th>Net Salary</th><th>Status</th><th>Action</th></tr>
    {% for e in emps %}
    <tr><td>{{e.name}}</td><td>{{e.department}}</td><td>{{e.designation}}</td><td>{{e.email}}</td>
    <td>{{e.date_joined or '—'}}</td><td>{{e.tenure_label}}</td>
    <td>₹{{ '%.2f'|format(e.net) }}</td>
    <td><span class="badge {{ 'bg-success' if e.status=='Active' else 'bg-secondary' }}">{{e.status}}</span></td>
    <td class="text-nowrap">
      <a class="btn btn-sm btn-outline-primary" href="/employees/{{e.id}}" title="View complete employee profile"><i class="ti ti-user-circle"></i></a>
      <a class="btn btn-sm btn-outline-secondary" href="/employees/toggle_status/{{e.id}}" title="Suspend/Activate">
        <i class="ti {{ 'ti-user-minus' if e.status=='Active' else 'ti-user-check' }}"></i>
      </a>
      <a class="btn btn-sm btn-outline-primary" href="/payslip/{{e.id}}" title="Download Payslip"><i class="ti ti-download"></i></a>
      <a class="btn btn-sm btn-danger" href="/employees/delete/{{e.id}}" title="Delete" onclick="return confirm('Delete this employee?');"><i class="ti ti-trash"></i></a>
    </td></tr>
    {% else %}
    <tr><td colspan="9" class="text-center text-muted py-3">No employees yet — add your first one above.</td></tr>
    {% endfor %}
    </table>
    </div>
    </div>""", emps=emps, search=search, today=str(date.today()))

@app.route("/employees/<int:eid>")
@login_required
def employee_profile(eid):
    e=Employee.query.get_or_404(eid)
    attendance=Attendance.query.filter_by(emp_id=e.id).order_by(Attendance.date.desc()).limit(20).all()
    punches=PunchLog.query.filter_by(emp_id=e.id).order_by(PunchLog.date.desc()).limit(20).all()
    leaves=LeaveRequest.query.filter_by(emp_id=e.id).order_by(LeaveRequest.id.desc()).limit(10).all()
    return render(r"""
    <div class="pp-page-heading"><div><div class="pp-eyebrow">Employee 360°</div><h1 class="pp-title">{{e.name}}</h1><div class="pp-subtitle">{{e.designation}} · {{e.department}} · {{e.email}}</div></div><div class="d-flex gap-2"><a class="btn btn-outline-secondary" href="/employees">Back</a><a class="btn pp-btn-primary" href="/payslip/{{e.id}}"><i class="ti ti-download"></i> Payslip</a></div></div>
    <div class="row g-3">
      <div class="col-xl-4"><div class="pp-card pp-card-pad h-100"><div class="d-flex align-items-center gap-3 mb-3"><div class="pp-avatar">{{e.name[:1]}}</div><div><h3 class="mb-0">{{e.name}}</h3><div class="text-muted small">EMP{{'%03d'|format(e.id)}} · {{e.status}}</div></div></div><div class="row g-2 small"><div class="col-6"><b>Email</b><br>{{e.email}}</div><div class="col-6"><b>Phone</b><br>{{e.phone}}</div><div class="col-6"><b>DOB</b><br>{{e.dob or '—'}} ({{e.age or '—'}})</div><div class="col-6"><b>Gender</b><br>{{e.gender or '—'}}</div><div class="col-6"><b>Joined</b><br>{{e.date_joined or '—'}}</div><div class="col-6"><b>Tenure</b><br>{{e.tenure_label}}</div><div class="col-12"><b>Address</b><br>{{e.address or '—'}}, {{e.city or ''}}, {{e.state or ''}}</div><div class="col-6"><b>Emergency</b><br>{{e.emergency_contact_name or '—'}}</div><div class="col-6"><b>Emergency Phone</b><br>{{e.emergency_contact_phone or '—'}}</div></div></div></div>
      <div class="col-xl-8"><div class="pp-card pp-card-pad h-100"><h3 class="pp-section-title mb-3">Employment & Work</h3><div class="row g-3 small"><div class="col-md-4"><b>Employment Type</b><br>{{e.employment_type}}</div><div class="col-md-4"><b>Manager</b><br>{{e.reporting_manager}}</div><div class="col-md-4"><b>Location</b><br>{{e.work_location}}</div><div class="col-md-4"><b>Shift</b><br>{{e.shift}}</div><div class="col-md-4"><b>Working Hours</b><br>{{e.working_hours}} hrs/day</div><div class="col-md-4"><b>Probation</b><br>{{e.probation_status}}</div><div class="col-md-4"><b>Qualification</b><br>{{e.qualification}}</div><div class="col-md-4"><b>College</b><br>{{e.college}}</div><div class="col-md-4"><b>Experience</b><br>{{e.experience_years}} years</div><div class="col-12"><b>Skills</b><br>{{e.skills}}</div><div class="col-12"><b>Certifications</b><br>{{e.certifications}}</div></div></div></div>
      <div class="col-lg-6"><div class="pp-card pp-card-pad"><h3 class="pp-section-title mb-3">Payroll</h3><div class="row g-2 small"><div class="col-6">Basic <b class="float-end">₹{{'%.2f'|format(e.basic)}}</b></div><div class="col-6">HRA <b class="float-end">₹{{'%.2f'|format(e.hra)}}</b></div><div class="col-6">Allowance <b class="float-end">₹{{'%.2f'|format(e.allowance)}}</b></div><div class="col-6">Bonus <b class="float-end">₹{{'%.2f'|format(e.bonus)}}</b></div><div class="col-6">PF <b class="float-end">₹{{'%.2f'|format(e.pf)}}</b></div><div class="col-6">Tax <b class="float-end">₹{{'%.2f'|format(e.tax)}}</b></div><div class="col-12 border-top pt-2">Net Salary <b class="float-end">₹{{'%.2f'|format(e.net)}}</b></div></div></div></div>
      <div class="col-lg-6"><div class="pp-card pp-card-pad"><h3 class="pp-section-title mb-3">Appraisal</h3><div class="small">Last: {{e.last_appraisal_date or '—'}} · Next: {{e.next_appraisal_date or '—'}}<br>Rating: <b>{{e.appraisal_rating or '—'}}</b> · Hike: <b>{{e.hike_pct or 0}}%</b><br>{{e.appraisal_comments or 'No comments'}}</div></div></div>
      <div class="col-12"><div class="pp-card pp-card-pad"><h3 class="pp-section-title mb-3">Recent Punch & Attendance</h3><div class="table-responsive"><table class="table pp-table"><tr><th>Date</th><th>Status</th><th>Punch In</th><th>Punch Out</th><th>Hours</th><th>OT</th></tr>{% for a in attendance %}{% set p=punches|selectattr('date','equalto',a.date)|first %}<tr><td>{{a.date}}</td><td>{{a.status}}</td><td>{{p.time_in if p else '—'}}</td><td>{{p.time_out if p else '—'}}</td><td>{{p.hours if p else 0}}</td><td>{{p.overtime_hours if p else 0}}</td></tr>{% else %}<tr><td colspan="6" class="pp-empty">No records</td></tr>{% endfor %}</table></div></div></div>
      <div class="col-12"><div class="pp-card pp-card-pad"><h3 class="pp-section-title mb-3">Recent Leave</h3><div class="table-responsive"><table class="table pp-table"><tr><th>Type</th><th>From</th><th>To</th><th>Status</th><th>Reason</th></tr>{% for l in leaves %}<tr><td>{{l.leave_type}}</td><td>{{l.start_date}}</td><td>{{l.end_date}}</td><td>{{l.status}}</td><td>{{l.reason}}</td></tr>{% else %}<tr><td colspan="5" class="pp-empty">No leave records</td></tr>{% endfor %}</table></div></div></div>
    </div>
    """, e=e,attendance=attendance,punches=punches,leaves=leaves)

@app.route("/employees/toggle_status/<int:eid>")
@login_required
def toggle_employee_status(eid):
    e = Employee.query.get_or_404(eid)
    e.status = "Inactive" if e.status == "Active" else "Active"
    db.session.commit()
    flash(f"{e.name} is now {e.status}.")
    return redirect("/employees")

@app.route("/employees/export")
@login_required
def export_employees_csv():
    import csv
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Name", "Department", "Designation", "Email", "Phone", "Date Joined", "Basic", "Net Salary", "Status"])
    for e in Employee.query.order_by(Employee.name).all():
        writer.writerow([e.name, e.department, e.designation, e.email, e.phone, e.date_joined, e.basic, e.net, e.status])
    mem = io.BytesIO(buf.getvalue().encode("utf-8"))
    return send_file(mem, mimetype="text/csv", as_attachment=True, download_name="employees.csv")

@app.route("/employees/delete/<int:eid>")
@login_required
def delete_employee(eid):
    db.session.delete(Employee.query.get_or_404(eid))
    db.session.commit()
    return redirect("/employees")

@app.route("/admin/reset_data", methods=["GET", "POST"])
@login_required
def reset_data():
    if request.method == "POST" and request.form.get("confirm") == "RESET":
        wipe_all_employee_data()
        flash("All employee, attendance, leave and punch data has been wiped clean.")
        return redirect("/dashboard")
    return render("""
    <div class="col-md-5 mx-auto card p-4 mt-5">
      <h4 class="text-danger"><i class="ti ti-alert-triangle"></i> Reset All Data</h4>
      <p class="text-muted">This permanently deletes every employee, attendance record, leave request and punch
      log — useful for clearing out demo/seed data before going live. This cannot be undone.</p>
      <form method="post">
        <input class="form-control mb-2" name="confirm" placeholder="Type RESET to confirm">
        <button class="btn btn-danger w-100">Wipe All Employee Data</button>
      </form>
    </div>""")


# ---------------- ATTENDANCE (auto-generated from punch logs) ----------------
def auto_mark_attendance_for_date(target_date):
    """Core automation: for every active employee, look at their punch log
    for target_date and decide Present / Half Day / Absent. Anyone with an
    Approved leave covering that date is marked Leave. Only overwrites rows
    that were themselves auto-generated (source='auto') or don't exist yet —
    a manual admin override is never silently overwritten."""
    marked = 0
    for e in Employee.query.filter_by(status="Active").all():
        existing = Attendance.query.filter_by(emp_id=e.id, date=target_date).first()
        if existing and existing.source == "manual":
            continue  # respect a manual override

        on_leave = LeaveRequest.query.filter(
            LeaveRequest.emp_id == e.id, LeaveRequest.status == "Approved",
            LeaveRequest.start_date <= target_date, LeaveRequest.end_date >= target_date,
        ).first()

        if on_leave:
            status = "Leave"
        else:
            logs = PunchLog.query.filter_by(emp_id=e.id, date=target_date).filter(PunchLog.time_out.isnot(None)).all()
            total_hours = sum(l.hours or 0 for l in logs)
            if total_hours >= STANDARD_WORK_HOURS - 1:
                status = "Present"
            elif total_hours > 0:
                status = "Half Day"
            else:
                status = "Absent"

        if existing:
            existing.status = status
            existing.source = "auto"
        else:
            db.session.add(Attendance(emp_id=e.id, date=target_date, status=status, source="auto"))
        marked += 1
    db.session.commit()
    return marked

@app.route("/attendance", methods=["GET", "POST"])
@login_required
def attendance():
    today = str(date.today())
    view_date = request.args.get("date", today)

    if request.method == "POST":
        if request.form.get("action") == "auto_generate":
            n = auto_mark_attendance_for_date(view_date)
            flash(f"Auto-generated attendance for {n} active employee(s) on {view_date}, from punch logs & approved leave.")
        else:
            # manual override for edge cases (e.g. field staff, forgot to punch)
            for e in Employee.query.all():
                status = request.form.get(f"status_{e.id}")
                if status:
                    rec = Attendance.query.filter_by(emp_id=e.id, date=view_date).first()
                    if rec:
                        rec.status, rec.source = status, "manual"
                    else:
                        db.session.add(Attendance(emp_id=e.id, date=view_date, status=status, source="manual"))
            db.session.commit()
            flash("Manual attendance saved for " + view_date)
        return redirect(f"/attendance?date={view_date}")

    emps = Employee.query.all()
    marked = {a.emp_id: a for a in Attendance.query.filter_by(date=view_date).all()}
    return render("""
    <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-2">
      <h4 class="mb-0">Attendance — {{view_date}}</h4>
      <form method="get" class="d-flex gap-2">
        <input class="form-control form-control-sm" type="date" name="date" value="{{view_date}}">
        <button class="btn btn-sm btn-outline-primary">View</button>
      </form>
    </div>

    <div class="card p-3 mb-3">
      <div class="d-flex align-items-center justify-content-between flex-wrap gap-2">
        <div>
          <i class="ti ti-wand text-primary"></i> <b>Auto-mark from Punch + Leave</b>
          <p class="text-muted small mb-0">Present / Half Day / Absent is inferred automatically from punch hours
          ({{std_hours}}+ hrs = Present, some hours = Half Day, none = Absent); anyone on approved leave is marked
          Leave. Any manual edit you make below is remembered and won't be overwritten by auto-generation.</p>
        </div>
        <form method="post"><input type="hidden" name="action" value="auto_generate"><input type="hidden" name="date_hidden">
          <button class="btn btn-primary" formaction="/attendance?date={{view_date}}"><i class="ti ti-wand"></i> Auto-Generate Now</button>
        </form>
      </div>
    </div>

    <details class="mb-3">
      <summary class="text-muted">Manual override (edge cases only)</summary>
      <form method="post" class="mt-2">
      <table class="table table-bordered">
      <tr><th>Name</th><th>Present</th><th>Absent</th><th>Half Day</th><th>Leave</th><th>Source</th></tr>
      {% for e in emps %}
      <tr><td>{{e.name}}</td>
      {% for opt in ['Present','Absent','Half Day','Leave'] %}
      <td><input type="radio" name="status_{{e.id}}" value="{{opt}}" {% if marked.get(e.id) and marked[e.id].status==opt %}checked{% endif %}></td>
      {% endfor %}
      <td><span class="badge {{ 'bg-primary' if marked.get(e.id) and marked[e.id].source=='auto' else 'bg-secondary' }}">{{ marked[e.id].source if marked.get(e.id) else '—' }}</span></td>
      </tr>
      {% endfor %}
      </table>
      <button class="btn btn-outline-primary">Save Manual Override</button>
      </form>
    </details>
    """, emps=emps, view_date=view_date, marked=marked, std_hours=STANDARD_WORK_HOURS)

# ---------------- PUNCH IN / PUNCH OUT ----------------
@app.route("/punch", methods=["GET", "POST"])
@login_required
def punch():
    today = str(date.today())

    if request.method == "POST":
        emp_id = int(request.form["emp_id"])
        action = request.form["action"]  # "in" or "out"
        now_str = datetime.now().strftime("%H:%M:%S")

        open_log = PunchLog.query.filter_by(emp_id=emp_id, date=today, time_out=None).first()

        if action == "in":
            if open_log:
                flash("Already punched in — punch out first.")
            else:
                db.session.add(PunchLog(emp_id=emp_id, date=today, time_in=now_str))
                db.session.commit()
                flash("Punched in at " + now_str)

        elif action == "out":
            if not open_log:
                flash("No active punch-in found for today.")
            else:
                t_in = datetime.strptime(open_log.time_in, "%H:%M:%S")
                t_out = datetime.strptime(now_str, "%H:%M:%S")
                worked_hours = round((t_out - t_in).seconds / 3600, 2)
                open_log.time_out = now_str
                open_log.hours = worked_hours
                db.session.commit()
                overtime = round(max(0, worked_hours - STANDARD_WORK_HOURS), 2)
                msg = f"Punched out at {now_str} — worked {worked_hours} hrs"
                if overtime > 0:
                    msg += f" (includes {overtime} hrs overtime)"
                is_holiday = Holiday.query.filter_by(date=today).first()
                if is_holiday:
                    msg += f" — worked on holiday ({is_holiday.name})"
                flash(msg)

        return redirect("/punch")

    emps = Employee.query.filter_by(status="Active").order_by(Employee.name).all()
    open_logs = {l.emp_id: l for l in PunchLog.query.filter_by(date=today, time_out=None).all()}
    today_holiday = Holiday.query.filter_by(date=today).first()

    history = []
    logs = PunchLog.query.order_by(PunchLog.id.desc()).limit(100).all()
    for l in logs:
        emp = Employee.query.get(l.emp_id)
        history.append({"log": l, "emp": emp, "holiday": Holiday.query.filter_by(date=l.date).first()})

    return render("""
    <h4><i class="ti ti-clock"></i> Punch In / Punch Out</h4>
    {% if today_holiday %}
    <div class="alert alert-warning"><i class="ti ti-star-filled"></i> Today is a company holiday ({{today_holiday.name}}) — any punches will be flagged as holiday work.</div>
    {% endif %}
    <p class="text-muted">Punches now feed straight into <a href="/attendance">Attendance</a> (auto Present/Half Day/Absent)
    and into overtime tracking on <a href="/payroll">Payroll</a> — they no longer set pay directly.</p>
    <div class="alert alert-light border small">
      <i class="ti ti-bulb text-warning"></i> <b>Automation ideas for real deployments:</b> connect a
      biometric/RFID device or mobile geofenced check-in instead of this manual button, auto-punch-out at shift end
      if someone forgets, and send a Slack/SMS nudge to anyone who hasn't punched in by their shift start time.
    </div>

    <div class="card mb-4">
    <table class="table table-bordered align-middle card-table">
    <tr><th>Employee</th><th>Status Today</th><th>Action</th></tr>
    {% for e in emps %}
    <tr>
      <td>{{e.name}}</td>
      <td>
        {% if e.id in open_logs %}
          <span class="badge bg-success">Punched In at {{ open_logs[e.id].time_in }}</span>
        {% else %}
          <span class="badge bg-secondary">Not punched in</span>
        {% endif %}
      </td>
      <td>
        <form method="post" class="d-inline">
          <input type="hidden" name="emp_id" value="{{e.id}}">
          {% if e.id in open_logs %}
            <button class="btn btn-sm btn-warning" name="action" value="out">Punch Out</button>
          {% else %}
            <button class="btn btn-sm btn-success" name="action" value="in">Punch In</button>
          {% endif %}
        </form>
      </td>
    </tr>
    {% endfor %}
    </table>
    </div>

    <h5>Recent Punch History</h5>
    <div class="card">
    <div class="table-responsive">
    <table class="table table-bordered card-table">
    <tr><th>Date</th><th>Employee</th><th>Time In</th><th>Time Out</th><th>Hours</th><th>Overtime</th><th></th></tr>
    {% for h in history %}
    <tr>
      <td>{{h.log.date}}</td>
      <td>{{h.emp.name if h.emp else '—'}}</td>
      <td>{{h.log.time_in}}</td>
      <td>{{h.log.time_out or '—'}}</td>
      <td>{{h.log.hours or 0}}</td>
      <td>{% if h.log.overtime_hours %}<span class="badge bg-info text-dark">{{h.log.overtime_hours}} hrs</span>{% else %}—{% endif %}</td>
      <td>{% if h.holiday %}<span class="badge bg-warning text-dark"><i class="ti ti-star-filled"></i> {{h.holiday.name}}</span>{% endif %}</td>
    </tr>
    {% else %}
    <tr><td colspan="7" class="text-center text-muted py-3">No punch records yet.</td></tr>
    {% endfor %}
    </table>
    </div>
    </div>
    """, emps=emps, open_logs=open_logs, history=history, today_holiday=today_holiday)

# ---------------- PAYROLL ----------------
@app.route("/payroll")
@login_required
def payroll():
    emps = Employee.query.all()
    current_month = str(date.today())[:7]  # "YYYY-MM"

    ot_totals = {}
    for e in emps:
        logs = PunchLog.query.filter(
            PunchLog.emp_id == e.id,
            PunchLog.date.like(f"{current_month}%"),
            PunchLog.time_out.isnot(None),
        ).all()
        total_hours = sum(l.hours or 0 for l in logs)
        overtime_hours = sum(l.overtime_hours for l in logs)
        overtime_pay = round(overtime_hours * e.per_hour_rate * 1.5, 2)  # 1.5x for overtime, a common norm
        ot_totals[e.id] = {"hours": round(total_hours, 2), "ot_hours": round(overtime_hours, 2), "ot_pay": overtime_pay}

    return render("""
    <div class="d-flex justify-content-between align-items-center flex-wrap gap-2"><h4 class="mb-0">Payroll / Salary Slips</h4><div class="d-flex gap-2"><a class="btn btn-sm btn-outline-success" href="/reports/download/payroll/xlsx"><i class="ti ti-file-spreadsheet"></i> Excel</a><a class="btn btn-sm btn-outline-danger" href="/reports/download/payroll/pdf"><i class="ti ti-file-type-pdf"></i> PDF</a><a class="btn btn-sm btn-outline-secondary" href="/reports/download/payroll/csv"><i class="ti ti-file-text"></i> CSV</a></div></div>
    <p class="text-muted small">Overtime pay is calculated at 1.5× the Basic-derived hourly rate, for hours worked
    beyond {{std}} hrs/day this month — it's shown separately and isn't yet folded into Net Salary below.</p>
    <div class="card">
    <div class="table-responsive">
    <table class="table table-bordered card-table">
    <tr><th>Name</th><th>Basic</th><th>HRA</th><th>Bonus</th><th>Allowance</th><th>PF</th><th>Tax</th><th>Other Ded.</th>
        <th>Net Salary</th><th>Hours (this month)</th><th>Overtime Hrs</th><th>Overtime Pay</th></tr>
    {% for e in emps %}
    <tr><td>{{e.name}}</td><td>{{e.basic}}</td><td>{{e.hra}}</td><td>{{e.bonus}}</td><td>{{e.allowance}}</td>
    <td>{{e.pf}}</td><td>{{e.tax}}</td><td>{{e.other_ded}}</td><td><b>₹{{ '%.2f'|format(e.net) }}</b></td>
    <td>{{ ot[e.id].hours }} hrs</td>
    <td>{{ ot[e.id].ot_hours }} hrs</td>
    <td><b class="text-success">₹{{ '%.2f'|format(ot[e.id].ot_pay) }}</b></td></tr>
    {% else %}
    <tr><td colspan="11" class="text-center text-muted py-3">No employees yet.</td></tr>
    {% endfor %}
    </table>
    </div>
    </div>""", emps=emps, ot=ot_totals, std=STANDARD_WORK_HOURS)

# ---------------- APPRAISALS ----------------
@app.route("/appraisals", methods=["GET", "POST"])
@login_required
def appraisals():
    if request.method == "POST":
        eid = int(request.form["emp_id"])
        e = Employee.query.get_or_404(eid)
        e.last_appraisal_date = str(date.today())
        hike = float(request.form.get("hike_pct") or 0)
        if hike:
            e.basic = round(e.basic * (1 + hike / 100), 2)
        db.session.commit()
        flash(f"Recorded appraisal for {e.name}" + (f" — Basic increased by {hike}%." if hike else "."))
        return redirect("/appraisals")

    emps = Employee.query.filter_by(status="Active").order_by(Employee.date_joined).all()
    return render("""
    <h4><i class="ti ti-trending-up"></i> Appraisals</h4>
    <p class="text-muted">Based on each employee's join date — a starting point for the review conversation,
    not a substitute for an actual performance evaluation.</p>
    <div class="card">
    <div class="table-responsive">
    <table class="table table-bordered align-middle card-table">
    <tr><th>Name</th><th>Joined</th><th>Tenure</th><th>Next Review Due</th><th>Status</th><th>Suggested Hike</th><th>Current Basic</th><th>Action</th></tr>
    {% for e in emps %}
    <tr>
      <td>{{e.name}}</td>
      <td>{{e.date_joined or '—'}}</td>
      <td>{{e.tenure_label}}</td>
      <td>{{e.next_appraisal_date or '—'}}</td>
      <td>{% if e.appraisal_due %}<span class="badge bg-pending">Due</span>{% else %}<span class="badge bg-secondary">Not yet</span>{% endif %}</td>
      <td>{{e.suggested_hike_pct}}%</td>
      <td>₹{{ '%.2f'|format(e.basic) }}</td>
      <td>
        <form method="post" class="d-flex gap-1">
          <input type="hidden" name="emp_id" value="{{e.id}}">
          <input class="form-control form-control-sm" style="width:80px" type="number" step="0.1" name="hike_pct" value="{{e.suggested_hike_pct}}">
          <button class="btn btn-sm btn-primary">Apply</button>
        </form>
      </td>
    </tr>
    {% else %}
    <tr><td colspan="8" class="text-center text-muted py-3">No active employees yet.</td></tr>
    {% endfor %}
    </table>
    </div>
    </div>""", emps=emps)

# ---------------- HOLIDAYS ----------------
@app.route("/holidays", methods=["GET", "POST"])
@login_required
def holidays():
    if request.method == "POST":
        db.session.add(Holiday(date=request.form["date"], name=request.form["name"]))
        db.session.commit()
        flash("Holiday added")
        return redirect("/holidays")
    hol = Holiday.query.order_by(Holiday.date).all()
    holiday_map = {h.date: h for h in hol}
    year = 2026
    months = []
    for month in range(1, 13):
        weeks = calendar.monthcalendar(year, month)
        months.append({"name": calendar.month_name[month], "number": month, "weeks": weeks})
    return render("""
    <div class="d-flex justify-content-between align-items-center mb-3">
      <div><h4 class="mb-1"><i class="ti ti-calendar-star"></i> Holiday Calendar</h4>
      <div class="text-muted small">Maharashtra public holidays — 2026</div></div>
      <span class="badge bg-red-lt text-red">{{ hol|length }} holiday dates</span>
    </div>
    <form method="post" class="row g-2 mb-4">
      <div class="col-md-3"><input class="form-control" type="date" name="date" required></div>
      <div class="col-md-4"><input class="form-control" name="name" placeholder="Holiday name" required></div>
      <div class="col-md-2"><button class="btn btn-primary">Add Holiday</button></div>
    </form>
    <style>
      .holiday-month{border:1px solid var(--pp-border);border-radius:14px;background:var(--pp-card);overflow:hidden;height:100%;}
      .holiday-month-head{padding:12px 14px;font-weight:800;border-bottom:1px solid var(--pp-border);}
      .holiday-week{display:grid;grid-template-columns:repeat(7,1fr);font-size:10px;color:var(--pp-muted);text-align:center;padding:7px 7px 2px;}
      .holiday-grid{display:grid;grid-template-columns:repeat(7,1fr);gap:5px;padding:7px;}
      .holiday-day{min-height:58px;border:1px solid var(--pp-border);border-radius:8px;padding:5px;font-size:10px;position:relative;}
      .holiday-day.empty{border-color:transparent;background:transparent;}
      .holiday-day.holiday{background:#fff1f2;border-color:#fecdd3;color:#9f1239;}
      .holiday-day .daynum{font-weight:800;}
      .holiday-name{margin-top:4px;font-size:8px;line-height:1.15;font-weight:700;}
    </style>
    <div class="row g-3 mb-4">
      {% for m in months %}
      <div class="col-12 col-md-6 col-xl-4">
        <div class="holiday-month">
          <div class="holiday-month-head">{{m.name}} {{year}}</div>
          <div class="holiday-week"><span>Mon</span><span>Tue</span><span>Wed</span><span>Thu</span><span>Fri</span><span>Sat</span><span>Sun</span></div>
          <div class="holiday-grid">
          {% for week in m.weeks %}{% for day in week %}
            {% if day == 0 %}<div class="holiday-day empty"></div>
            {% else %}
              {% set ds = '%04d-%02d-%02d'|format(year,m.number,day) %}
              {% set h = holiday_map.get(ds) %}
              <div class="holiday-day {{'holiday' if h else ''}}">
                <div class="daynum">{{day}}</div>
                {% if h %}<div class="holiday-name">★ {{h.name}}</div>{% endif %}
              </div>
            {% endif %}
          {% endfor %}{% endfor %}
          </div>
        </div>
      </div>
      {% endfor %}
    </div>
    <div class="card">
      <div class="card-header"><h3 class="card-title">Holiday List</h3></div>
      <div class="table-responsive"><table class="table table-vcenter card-table">
      <thead><tr><th>Date</th><th>Holiday</th><th></th></tr></thead><tbody>
      {% for h in hol %}<tr><td>{{h.date}}</td><td>{{h.name}}</td>
      <td class="text-end"><a class="btn btn-sm btn-danger" href="/holidays/delete/{{h.id}}"><i class="ti ti-trash"></i></a></td></tr>
      {% else %}<tr><td colspan="3" class="text-center text-muted py-3">No holidays added yet.</td></tr>{% endfor %}
      </tbody></table></div>
    </div>""", hol=hol, holiday_map=holiday_map, months=months, year=year)

@app.route("/holidays/delete/<int:hid>")
@login_required
def delete_holiday(hid):
    db.session.delete(Holiday.query.get_or_404(hid))
    db.session.commit()
    return redirect("/holidays")

# ---------------- LEAVE (admin side) ----------------
@app.route("/leave", methods=["GET", "POST"])
@login_required
def leave():
    if request.method == "POST":
        f = request.form
        db.session.add(LeaveRequest(emp_id=f["emp_id"], leave_type=f["leave_type"], start_date=f["start"],
                              end_date=f["end"], reason=f["reason"]))
        db.session.commit()
        flash("Leave applied")
        return redirect("/leave")
    emps = Employee.query.all()
    leaves = LeaveRequest.query.order_by(LeaveRequest.id.desc()).all()
    emp_map = {e.id: e for e in emps}  # lookup so we can show the employee's name, not just their ID
    return render("""
    <h4>Apply Leave (on behalf of an employee)</h4>
    <form method="post" class="row g-2 mb-4">
      <div class="col-md-3"><select class="form-select" name="emp_id" required>
        <option value="">Select Employee</option>
        {% for e in emps %}<option value="{{e.id}}">{{e.name}}</option>{% endfor %}
      </select></div>
      <div class="col-md-2"><select class="form-select" name="leave_type">
        <option>Sick</option><option>Casual</option><option>Paid</option></select></div>
      <div class="col-md-2"><input class="form-control" type="date" name="start" required></div>
      <div class="col-md-2"><input class="form-control" type="date" name="end" required></div>
      <div class="col-md-2"><input class="form-control" name="reason" placeholder="Reason"></div>
      <div class="col-md-1"><button class="btn btn-primary">Apply</button></div>
    </form>
    <div class="card">
    <div class="table-responsive">
    <table class="table table-bordered card-table">
    <tr><th>Emp ID</th><th>Employee Name</th><th>Department</th><th>Type</th><th>From</th><th>To</th><th>Status</th><th>Action</th></tr>
    {% for l in leaves %}
    {% set emp = emp_map.get(l.emp_id) %}
    <tr>
      <td>{{l.emp_id}}</td>
      <td>{{ emp.name if emp else 'Unknown Employee' }}</td>
      <td>{{ emp.department if emp else '—' }}</td>
      <td>{{l.leave_type}}</td>
      <td>{{l.start_date}}</td>
      <td>{{l.end_date}}</td>
      <td><span class="badge {{ 'bg-pending' if l.status=='Pending' else ('bg-success' if l.status=='Approved' else 'bg-danger') }}">{{l.status}}</span></td>
      <td>
      {% if l.status == 'Pending' %}
      <a class="btn btn-sm btn-success" href="/leave/approve/{{l.id}}">Approve</a>
      <a class="btn btn-sm btn-danger" href="/leave/reject/{{l.id}}">Reject</a>
      {% endif %}
      </td>
    </tr>
    {% else %}
    <tr><td colspan="8" class="text-center text-muted py-3">No leave requests yet.</td></tr>
    {% endfor %}
    </table>
    </div>
    </div>""", emps=emps, leaves=leaves, emp_map=emp_map)

@app.route("/leave/approve/<int:lid>")
@login_required
def approve_leave(lid):
    l = LeaveRequest.query.get_or_404(lid)
    l.status = "Approved"
    db.session.commit()
    return redirect("/leave")

@app.route("/leave/reject/<int:lid>")
@login_required
def reject_leave(lid):
    l = LeaveRequest.query.get_or_404(lid)
    l.status = "Rejected"
    db.session.commit()
    return redirect("/leave")



# ---------------- EMPLOYEE LOGIN ----------------
@app.route("/employee/login", methods=["GET", "POST"])
def employee_login():
    if request.method == "POST":
        emp_id = request.form.get("emp_id")
        pw = request.form.get("password", "")
        if not emp_id:
            flash("Please select your name.")
            return redirect("/employee/login")
        try:
            emp = Employee.query.get(int(emp_id))
        except (TypeError, ValueError):
            emp = None
        if not emp or emp.status != "Active":
            flash("This account is inactive. Contact HR/Admin.")
            return redirect("/employee/login")
        if not emp.check_password(pw):
            flash("Incorrect password.")
            return redirect("/employee/login")
        session.clear()
        session["employee_id"] = emp.id
        return redirect("/employee/dashboard")

    emps = Employee.query.filter_by(status="Active").order_by(Employee.name).all()
    return render_template_string(r"""
    <!doctype html><html lang="en"><head>
    <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Employee Login — PayrollPro</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/core@latest/dist/css/tabler.min.css">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@latest/dist/tabler-icons.min.css">
    <style>
    body{margin:0;font-family:Inter,system-ui,sans-serif}.pp-login{min-height:100vh;display:grid;place-items:center;padding:30px;position:relative;overflow:hidden;background:radial-gradient(circle at 12% 18%,rgba(99,102,241,.16),transparent 28%),radial-gradient(circle at 88% 80%,rgba(14,165,233,.16),transparent 30%),linear-gradient(135deg,#f4f8ff,#f8fbff)}.pp-login:before,.pp-login:after{content:"";position:absolute;border-radius:50%}.pp-login:before{width:440px;height:440px;left:-190px;bottom:-180px;background:linear-gradient(135deg,#7c3aed,#a78bfa)}.pp-login:after{width:520px;height:520px;right:-250px;top:-220px;background:linear-gradient(135deg,#8b5cf6,#ddd6fe)}.shell{width:min(1020px,100%);min-height:610px;display:grid;grid-template-columns:1fr 1fr;background:rgba(255,255,255,.8);backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,.9);border-radius:28px;box-shadow:0 30px 80px rgba(31,41,55,.16);overflow:hidden;position:relative;z-index:2}.visual{padding:50px;display:flex;flex-direction:column;justify-content:space-between;color:#fff;position:relative;overflow:hidden;background:linear-gradient(145deg,#164cc7,#4382ff)}.visual:after{content:"";position:absolute;width:330px;height:330px;border-radius:50%;right:-130px;bottom:-160px;background:rgba(255,255,255,.13)}.copy{max-width:370px;position:relative;z-index:2}.copy h2{font-size:35px;line-height:1.05;margin:22px 0 12px;font-weight:850;letter-spacing:-1px}.copy p{font-size:14px;line-height:1.7;color:rgba(255,255,255,.84)}.office{position:absolute;right:45px;bottom:45px;width:300px;height:190px;border-radius:18px;background:linear-gradient(160deg,rgba(255,255,255,.24),rgba(255,255,255,.05));border:1px solid rgba(255,255,255,.3);box-shadow:0 25px 50px rgba(0,0,0,.14)}.office:before{content:"";position:absolute;left:30px;right:30px;top:30px;height:4px;background:rgba(255,255,255,.6);box-shadow:0 35px 0 rgba(255,255,255,.32),0 70px 0 rgba(255,255,255,.2)}.form{padding:50px;display:flex;align-items:center;background:#fff}.inner{width:100%;max-width:390px;margin:auto}.logo{display:flex;align-items:center;gap:10px;font-size:20px;font-weight:850;margin-bottom:36px}.mark{width:40px;height:40px;border-radius:12px;background:#ede9fe;color:#7c3aed;display:grid;place-items:center;font-size:21px}.inner h1{font-size:29px;font-weight:850;letter-spacing:-.7px;margin-bottom:7px}.lead{font-size:13px;color:#718096;margin-bottom:26px}.label{font-size:11px;font-weight:800;margin-bottom:7px;display:block}.field{margin-bottom:15px}.form-control,.form-select{height:44px;border-radius:10px}.submit{height:46px;width:100%;border:0;border-radius:10px;color:#fff;font-weight:800;background:linear-gradient(135deg,#4c1d95,#7c3aed);box-shadow:0 9px 22px rgba(37,99,235,.22)}.switch{display:flex;justify-content:center;gap:5px;margin-top:22px;font-size:12px;color:#718096}.switch a{color:#7c3aed;font-weight:800;text-decoration:none}.secure{text-align:center;color:#718096;font-size:10px;margin-top:24px}@media(max-width:850px){.shell{grid-template-columns:1fr}.visual{min-height:270px}.office{display:none}}@media(max-width:550px){.pp-login{padding:12px}.form,.visual{padding:30px 24px}}
    </style></head><body>
    <div class="pp-login"><div class="shell">
      <section class="visual"><div class="copy">
        <div style="font-weight:850;font-size:20px;">PAYROLL <span style="font-weight:500;">PRO</span></div>
        <h2>Welcome!</h2><p>Track your attendance, leave, salary and payslips — all from one simple workspace.</p>
      </div><div class="office"></div><div style="font-size:11px;opacity:.85;position:relative;z-index:2;">Secure • Personal • Easy</div></section>
      <section class="form"><div class="inner">
        <div class="logo"><span class="mark"><i class="ti ti-id-badge-2"></i></span>PayrollPro</div>
        <h1>Employee Login</h1><div class="lead">Access your employee self-service account.</div>
        {% with messages=get_flashed_messages() %}{% for m in messages %}<div class="alert alert-danger py-2">{{m}}</div>{% endfor %}{% endwith %}
        <form method="post">
          <div class="field"><label class="label">Employee</label><select class="form-select" name="emp_id" required><option value="">Select your name</option>{% for e in emps %}<option value="{{e.id}}">{{e.name}} — {{e.department}}</option>{% endfor %}</select></div>
          <div class="field"><label class="label">Password</label><input class="form-control" type="password" name="password" placeholder="Enter password" required></div>
          <div class="d-flex justify-content-between align-items-center mb-4" style="font-size:11px;color:#718096;"><label><input type="checkbox" class="form-check-input me-1"> Remember me</label><a href="/forgot-password" style="color:#7c3aed;font-weight:700;text-decoration:none;">Forgot password?</a></div>
          <button class="submit">Login <i class="ti ti-arrow-right ms-1"></i></button>
        </form>
        <div class="switch">Are you an admin? <a href="/login">Admin Login</a></div>
        <div class="secure"><i class="ti ti-shield-check"></i> Secure &nbsp;•&nbsp; Personal &nbsp;•&nbsp; Confidential</div>
      </div></section>
    </div></div></body></html>
    """, emps=emps)

@app.route("/employee/logout")
def employee_logout():
    session.pop("employee_id", None)
    return redirect("/employee/login")

def _current_employee():
    return Employee.query.get_or_404(session["employee_id"])

def _employee_month_stats(emp):
    today = str(date.today())
    current_month = today[:7]
    month_records = Attendance.query.filter(Attendance.emp_id == emp.id, Attendance.date.like(f"{current_month}%")).all()
    present_days = sum(1 for a in month_records if a.status == "Present")
    absent_days = sum(1 for a in month_records if a.status == "Absent")
    halfday_days = sum(1 for a in month_records if a.status == "Half Day")
    logs = PunchLog.query.filter(PunchLog.emp_id == emp.id, PunchLog.date.like(f"{current_month}%"), PunchLog.time_out.isnot(None)).all()
    overtime_hours = round(sum(l.overtime_hours for l in logs), 2)
    holiday_dates = {h.date for h in Holiday.query.all()}
    worked_holidays = sorted({l.date for l in logs if l.date in holiday_dates})
    return dict(present_days=present_days, absent_days=absent_days, halfday_days=halfday_days,
                overtime_hours=overtime_hours, worked_holidays=worked_holidays)

# ---------------- EMPLOYEE: OVERVIEW ----------------
@app.route("/employee/dashboard")
@employee_login_required
def employee_dashboard():
    emp = _current_employee()
    stats = _employee_month_stats(emp)
    leave_history = LeaveRequest.query.filter_by(emp_id=emp.id).order_by(LeaveRequest.id.desc()).all()
    approved_days_used = sum(
        (datetime.strptime(l.end_date, "%Y-%m-%d") - datetime.strptime(l.start_date, "%Y-%m-%d")).days + 1
        for l in leave_history if l.status == "Approved"
    )
    leave_balance_left = max((emp.leave_balance or 12) - approved_days_used, 0)
    pending_count = sum(1 for l in leave_history if l.status == "Pending")
    open_log = PunchLog.query.filter_by(emp_id=emp.id, date=str(date.today()), time_out=None).first()

    return render_emp("""
    <div class="row g-3 mb-3">
      <div class="col-md-8">
        <div class="card p-3">
          <h4 class="mb-1"><i class="ti ti-user-circle"></i> {{e.name}}</h4>
          <p class="text-muted mb-0">{{e.designation}} — {{e.department}}</p>
          <p class="text-muted small mb-0">{{e.email}} | {{e.phone}}</p>
          <p class="text-muted small mb-0">Joined {{e.date_joined or '—'}} · Tenure {{e.tenure_label}}
            {% if e.appraisal_due %}<span class="badge bg-pending ms-1">Appraisal Due</span>{% endif %}</p>
        </div>
      </div>
      <div class="col-md-4">
        <div class="card stat-glow p-3 text-center h-100" style="--c1:#0d9488;--c2:#14b8a6;--shadow:rgba(13,148,136,.35);">
          <i class="ti ti-report-money"></i><h3 class="stat-value">₹{{ '%.0f'|format(e.net) }}</h3>My Net Salary
        </div>
      </div>
    </div>

    <div class="row g-2 mb-3">
      <div class="col-6 col-md-2"><div class="card p-2 text-center"><h3 class="mb-0 stat-value" style="font-size:1.4rem;">{{s.present_days}}</h3><small class="text-muted">Present (mo.)</small></div></div>
      <div class="col-6 col-md-2"><div class="card p-2 text-center"><h3 class="mb-0 stat-value" style="font-size:1.4rem;">{{s.absent_days}}</h3><small class="text-muted">Absent (mo.)</small></div></div>
      <div class="col-6 col-md-2"><div class="card p-2 text-center"><h3 class="mb-0 stat-value" style="font-size:1.4rem;">{{s.halfday_days}}</h3><small class="text-muted">Half Day (mo.)</small></div></div>
      <div class="col-6 col-md-2"><div class="card p-2 text-center"><h3 class="mb-0 stat-value" style="font-size:1.4rem;">{{s.overtime_hours}}</h3><small class="text-muted">Overtime hrs</small></div></div>
      <div class="col-6 col-md-2"><div class="card p-2 text-center"><h3 class="mb-0 stat-value" style="font-size:1.4rem;">{{leave_balance}}</h3><small class="text-muted">Leave Balance</small></div></div>
      <div class="col-6 col-md-2"><div class="card p-2 text-center"><h3 class="mb-0 stat-value" style="font-size:1.4rem;">{{pending}}</h3><small class="text-muted">Pending Leaves</small></div></div>
    </div>

    <div class="row g-3">
      <div class="col-md-4">
        <div class="card p-3 h-100">
          <h6><i class="ti ti-clock"></i> Punch Status</h6>
          {% if open_log %}
            <p class="mb-2"><span class="badge bg-success">Punched in at {{open_log.time_in}}</span></p>
          {% else %}
            <p class="mb-2"><span class="badge bg-secondary">Not punched in today</span></p>
          {% endif %}
          <a href="/employee/attendance" class="btn btn-sm btn-primary w-100">Go to Punch &amp; Attendance</a>
        </div>
      </div>
      <div class="col-md-4">
        <div class="card p-3 h-100">
          <h6><i class="ti ti-calendar-off"></i> Leave</h6>
          <p class="text-muted small mb-2">{{leave_balance}} day(s) remaining this year.</p>
          <a href="/employee/leave" class="btn btn-sm btn-primary w-100">Apply / Manage Leave</a>
        </div>
      </div>
      <div class="col-md-4">
        <div class="card p-3 h-100">
          <h6><i class="ti ti-receipt"></i> Payslip</h6>
          <p class="text-muted small mb-2">View your latest salary breakdown.</p>
          <a href="/employee/payslip_page" class="btn btn-sm btn-primary w-100">View Payslip</a>
        </div>
      </div>
      {% if s.worked_holidays %}
      <div class="col-12">
        <div class="card p-3">
          <h6><i class="ti ti-star-filled text-warning"></i> Worked on Holidays this month</h6>
          <p class="mb-0">{{ s.worked_holidays|join(', ') }} — flagged for HR review / comp-off.</p>
        </div>
      </div>
      {% endif %}
    </div>
    """, e=emp, s=stats, leave_balance=leave_balance_left, pending=pending_count, open_log=open_log)

# ---------------- EMPLOYEE: ATTENDANCE + PUNCH ----------------
@app.route("/employee/profile")
@employee_login_required
def employee_profile_self():
    e=_current_employee()
    return render_emp(r"""<div class="pp-page-heading"><div><div class="pp-eyebrow">My Workspace</div><h1 class="pp-title">My Profile</h1><div class="pp-subtitle">Your personal, employment and contact information.</div></div></div><div class="row g-3"><div class="col-lg-6"><div class="pp-card pp-card-pad"><h3 class="pp-section-title mb-3">Personal</h3><div class="row g-3 small"><div class="col-6"><b>Name</b><br>{{e.name}}</div><div class="col-6"><b>Employee ID</b><br>EMP{{'%03d'|format(e.id)}}</div><div class="col-6"><b>Email</b><br>{{e.email}}</div><div class="col-6"><b>Phone</b><br>{{e.phone}}</div><div class="col-6"><b>DOB / Age</b><br>{{e.dob or '—'}} / {{e.age or '—'}}</div><div class="col-6"><b>Gender</b><br>{{e.gender or '—'}}</div><div class="col-12"><b>Address</b><br>{{e.address or '—'}}, {{e.city or ''}}, {{e.state or ''}}</div></div></div></div><div class="col-lg-6"><div class="pp-card pp-card-pad"><h3 class="pp-section-title mb-3">Employment</h3><div class="row g-3 small"><div class="col-6"><b>Department</b><br>{{e.department}}</div><div class="col-6"><b>Designation</b><br>{{e.designation}}</div><div class="col-6"><b>Joined</b><br>{{e.date_joined}}</div><div class="col-6"><b>Tenure</b><br>{{e.tenure_label}}</div><div class="col-6"><b>Manager</b><br>{{e.reporting_manager}}</div><div class="col-6"><b>Location</b><br>{{e.work_location}}</div><div class="col-6"><b>Shift</b><br>{{e.shift}}</div><div class="col-6"><b>Working Hours</b><br>{{e.working_hours}} hrs/day</div></div></div></div><div class="col-12"><div class="pp-card pp-card-pad"><h3 class="pp-section-title mb-3">Skills & Qualification</h3><p class="mb-1"><b>{{e.qualification}}</b> · {{e.college}} · {{e.graduation_year}}</p><p class="mb-0">{{e.skills}}</p></div></div></div>""",e=e)

@app.route("/employee/appraisal")
@employee_login_required
def employee_appraisal():
    e=_current_employee(); return render_emp(r"""<div class="pp-page-heading"><div><div class="pp-eyebrow">Performance</div><h1 class="pp-title">My Appraisal</h1><div class="pp-subtitle">Your latest review and appraisal timeline.</div></div></div><div class="row g-3"><div class="col-md-4"><div class="pp-card pp-card-pad"><div class="pp-section-muted">Rating</div><div class="fs-1 fw-bold">{{e.appraisal_rating or '—'}} / 5</div></div></div><div class="col-md-4"><div class="pp-card pp-card-pad"><div class="pp-section-muted">Last Appraisal</div><div class="fs-4 fw-bold">{{e.last_appraisal_date or '—'}}</div></div></div><div class="col-md-4"><div class="pp-card pp-card-pad"><div class="pp-section-muted">Next Appraisal</div><div class="fs-4 fw-bold">{{e.next_appraisal_date or '—'}}</div></div></div><div class="col-12"><div class="pp-card pp-card-pad"><h3 class="pp-section-title">Manager Comments</h3><p class="mt-2 mb-0">{{e.appraisal_comments or 'No appraisal comments recorded.'}}</p></div></div></div>""",e=e)

@app.route("/employee/notifications")
@employee_login_required
def employee_notifications():
    e=_current_employee(); leaves=LeaveRequest.query.filter_by(emp_id=e.id).order_by(LeaveRequest.id.desc()).limit(8).all(); return render_emp(r"""<div class="pp-page-heading"><div><div class="pp-eyebrow">My Workspace</div><h1 class="pp-title">Notifications</h1><div class="pp-subtitle">Updates about your leave, appraisal and payroll.</div></div></div><div class="pp-card pp-card-pad"><div class="pp-list-item"><div class="pp-list-icon" style="background:#ede9fe;color:#7c3aed"><i class="ti ti-receipt"></i></div><div><b>Latest payslip available</b><div class="pp-section-muted">Your current salary breakdown is ready.</div></div><a class="btn btn-sm pp-btn-soft ms-auto" href="/employee/payslip_page">Open</a></div><div class="pp-list-item"><div class="pp-list-icon" style="background:#fef3c7;color:#b45309"><i class="ti ti-trending-up"></i></div><div><b>Appraisal schedule</b><div class="pp-section-muted">Next review: {{e.next_appraisal_date or 'Not scheduled'}}</div></div><a class="btn btn-sm btn-outline-secondary ms-auto" href="/employee/appraisal">Open</a></div>{% for l in leaves %}<div class="pp-list-item"><div class="pp-list-icon" style="background:#dcfce7;color:#15803d"><i class="ti ti-calendar-event"></i></div><div><b>Leave {{l.status}}</b><div class="pp-section-muted">{{l.leave_type}} · {{l.start_date}} to {{l.end_date}}</div></div></div>{% endfor %}</div>""",e=e,leaves=leaves)

@app.route("/employee/attendance", methods=["GET", "POST"])
@employee_login_required
def employee_attendance():
    emp = _current_employee()
    today = str(date.today())

    if request.method == "POST":
        action_type = request.form["punch_action"]
        now_str = datetime.now().strftime("%H:%M:%S")
        open_log = PunchLog.query.filter_by(emp_id=emp.id, date=today, time_out=None).first()
        if action_type == "in":
            if open_log:
                flash("Already punched in — punch out first.")
            else:
                db.session.add(PunchLog(emp_id=emp.id, date=today, time_in=now_str))
                db.session.commit()
                flash("Punched in at " + now_str)
        else:
            if not open_log:
                flash("No active punch-in found for today.")
            else:
                t_in = datetime.strptime(open_log.time_in, "%H:%M:%S")
                t_out = datetime.strptime(now_str, "%H:%M:%S")
                worked_hours = round((t_out - t_in).seconds / 3600, 2)
                open_log.time_out = now_str
                open_log.hours = worked_hours
                db.session.commit()
                overtime = round(max(0, worked_hours - STANDARD_WORK_HOURS), 2)
                msg = f"Punched out — worked {worked_hours} hrs"
                if overtime:
                    msg += f" ({overtime} hrs overtime)"
                flash(msg)
        return redirect("/employee/attendance")

    open_log = PunchLog.query.filter_by(emp_id=emp.id, date=today, time_out=None).first()
    punch_history = PunchLog.query.filter_by(emp_id=emp.id).order_by(PunchLog.id.desc()).limit(15).all()
    attendance_history = Attendance.query.filter_by(emp_id=emp.id).order_by(Attendance.date.desc()).limit(15).all()
    today_holiday = Holiday.query.filter_by(date=today).first()
    stats = _employee_month_stats(emp)

    return render_emp("""
    <h4><i class="ti ti-clock"></i> Attendance &amp; Punch</h4>
    {% if today_holiday %}<div class="alert alert-warning"><i class="ti ti-star-filled"></i> Today is a company holiday: {{today_holiday.name}}.</div>{% endif %}

    <div class="row g-3">
      <div class="col-md-5">
        <div class="card p-3">
          <h5>Punch In / Out</h5>
          {% if open_log %}<p><span class="badge bg-success">Punched in at {{open_log.time_in}}</span></p>
          {% else %}<p><span class="badge bg-secondary">Not punched in today</span></p>{% endif %}
          <form method="post">
            {% if open_log %}
              <button class="btn btn-warning w-100" name="punch_action" value="out">Punch Out</button>
            {% else %}
              <button class="btn btn-success w-100" name="punch_action" value="in">Punch In</button>
            {% endif %}
          </form>
          <hr>
          <p class="small text-muted mb-1">This month: {{stats.present_days}} present, {{stats.absent_days}} absent,
          {{stats.halfday_days}} half day, <b>{{stats.overtime_hours}} hrs overtime</b>.</p>
        </div>
      </div>
      <div class="col-md-7">
        <div class="card p-3 h-100">
          <p class="small text-muted mb-1">Recent punches:</p>
          <table class="table table-sm mb-0">
            <tr><th>Date</th><th>In</th><th>Out</th><th>Hrs</th><th>OT</th></tr>
            {% for p in punch_history %}
            <tr><td>{{p.date}}</td><td>{{p.time_in}}</td><td>{{p.time_out or '—'}}</td><td>{{p.hours or 0}}</td>
            <td>{% if p.overtime_hours %}<span class="badge bg-info text-dark">{{p.overtime_hours}}</span>{% else %}—{% endif %}</td></tr>
            {% else %}
            <tr><td colspan="5" class="text-muted text-center">No punches yet</td></tr>
            {% endfor %}
          </table>
        </div>
      </div>
      <div class="col-12">
        <div class="card p-3">
          <p class="small text-muted mb-1">My attendance history:</p>
          <table class="table table-sm mb-0">
            <tr><th>Date</th><th>Status</th><th>Source</th></tr>
            {% for a in attendance_history %}
            <tr><td>{{a.date}}</td><td>
              <span class="badge {{ 'bg-success' if a.status=='Present' else ('bg-danger' if a.status=='Absent' else ('bg-warning text-dark' if a.status=='Half Day' else 'bg-secondary')) }}">{{a.status}}</span>
            </td><td><small class="text-muted">{{a.source}}</small></td></tr>
            {% else %}
            <tr><td colspan="3" class="text-muted text-center">No attendance marked yet</td></tr>
            {% endfor %}
          </table>
        </div>
      </div>
    </div>
    """, open_log=open_log, punch_history=punch_history, attendance_history=attendance_history,
         today_holiday=today_holiday, stats=stats)

# ---------------- EMPLOYEE: LEAVE ----------------
@app.route("/employee/leave", methods=["GET", "POST"])
@employee_login_required
def employee_leave():
    emp = _current_employee()
    if request.method == "POST":
        action = request.form.get("form_type")
        if action == "apply_leave":
            db.session.add(LeaveRequest(
                emp_id=emp.id, leave_type=request.form["leave_type"],
                start_date=request.form["start"], end_date=request.form["end"],
                reason=request.form.get("reason", ""),
            ))
            db.session.commit()
            flash("Leave application submitted.")
        elif action == "cancel_leave":
            lid = int(request.form["leave_id"])
            leave_req = LeaveRequest.query.filter_by(id=lid, emp_id=emp.id).first()
            if leave_req and leave_req.status == "Pending":
                db.session.delete(leave_req)
                db.session.commit()
                flash("Leave request cancelled.")
            else:
                flash("Only pending requests can be cancelled.")
        return redirect("/employee/leave")

    leave_history = LeaveRequest.query.filter_by(emp_id=emp.id).order_by(LeaveRequest.id.desc()).all()
    approved_days_used = sum(
        (datetime.strptime(l.end_date, "%Y-%m-%d") - datetime.strptime(l.start_date, "%Y-%m-%d")).days + 1
        for l in leave_history if l.status == "Approved"
    )
    leave_balance_left = max((emp.leave_balance or 12) - approved_days_used, 0)
    by_type = {}
    for l in leave_history:
        if l.status == "Approved":
            days = (datetime.strptime(l.end_date, "%Y-%m-%d") - datetime.strptime(l.start_date, "%Y-%m-%d")).days + 1
            by_type[l.leave_type] = by_type.get(l.leave_type, 0) + days

    return render_emp("""
    <h4><i class="ti ti-calendar-off"></i> Leave Management</h4>
    <div class="row g-2 mb-3">
      <div class="col-6 col-md-3"><div class="card p-2 text-center"><h3 class="stat-value" style="font-size:1.4rem;">{{balance}}</h3><small class="text-muted">Days Remaining</small></div></div>
      {% for t, d in by_type.items() %}
      <div class="col-6 col-md-3"><div class="card p-2 text-center"><h3 class="mb-0" style="font-size:1.4rem;">{{d}}</h3><small class="text-muted">{{t}} used</small></div></div>
      {% endfor %}
    </div>

    <div class="card p-3 mb-3">
      <h5>Apply for Leave</h5>
      <form method="post" class="row g-2">
        <input type="hidden" name="form_type" value="apply_leave">
        <div class="col-md-3"><select class="form-select" name="leave_type">
          <option>Sick</option><option>Casual</option><option>Paid</option></select></div>
        <div class="col-md-3"><input class="form-control" type="date" name="start" required></div>
        <div class="col-md-3"><input class="form-control" type="date" name="end" required></div>
        <div class="col-md-3"><input class="form-control" name="reason" placeholder="Reason"></div>
        <div class="col-12"><button class="btn btn-primary">Submit Application</button></div>
      </form>
    </div>

    <div class="card p-3">
      <h5>My Leave History</h5>
      <table class="table table-sm mb-0">
        <tr><th>Type</th><th>From</th><th>To</th><th>Status</th><th></th></tr>
        {% for l in leave_history %}
        <tr><td>{{l.leave_type}}</td><td>{{l.start_date}}</td><td>{{l.end_date}}</td>
        <td><span class="badge {{ 'bg-pending' if l.status=='Pending' else ('bg-success' if l.status=='Approved' else 'bg-danger') }}">{{l.status}}</span></td>
        <td>
          {% if l.status == 'Pending' %}
          <form method="post" class="d-inline" onsubmit="return confirm('Cancel this leave request?');">
            <input type="hidden" name="form_type" value="cancel_leave">
            <input type="hidden" name="leave_id" value="{{l.id}}">
            <button class="btn btn-sm btn-outline-danger py-0 px-1"><i class="ti ti-x"></i></button>
          </form>
          {% endif %}
        </td></tr>
        {% else %}
        <tr><td colspan="5" class="text-muted text-center">No leave applied yet</td></tr>
        {% endfor %}
      </table>
    </div>
    """, leave_history=leave_history, balance=leave_balance_left, by_type=by_type)

# ---------------- EMPLOYEE: PAYSLIP ----------------
@app.route("/employee/payslip_page")
@employee_login_required
def employee_payslip_page():
    emp = _current_employee()
    return render_emp("""
    <h4><i class="ti ti-receipt"></i> My Salary Breakdown</h4>
    <div class="card p-3">
      <div class="d-flex justify-content-between align-items-center mb-2">
        <span class="text-muted">{{e.designation}} — {{e.department}}</span>
        <a href="/payslip/{{e.id}}" class="btn btn-sm btn-primary"><i class="ti ti-download"></i> Download Payslip (PDF)</a>
      </div>
      <table class="table table-sm mb-0">
        <tr><th>Basic</th><th>HRA</th><th>Bonus</th><th>Allowance</th><th>PF</th><th>Tax</th><th>Other Ded.</th><th>Net Salary</th></tr>
        <tr><td>₹{{e.basic}}</td><td>₹{{e.hra}}</td><td>₹{{e.bonus}}</td><td>₹{{e.allowance}}</td>
        <td>₹{{e.pf}}</td><td>₹{{e.tax}}</td><td>₹{{e.other_ded}}</td><td><b>₹{{ '%.2f'|format(e.net) }}</b></td></tr>
      </table>
    </div>""", e=emp)

# ---------------- EMPLOYEE: SETTINGS ----------------
@app.route("/employee/settings", methods=["GET", "POST"])
@employee_login_required
def employee_settings():
    emp = _current_employee()
    if request.method == "POST":
        old_pw = request.form.get("old_password", "")
        new_pw = request.form.get("new_password", "")
        if not emp.check_password(old_pw):
            flash("Current password is incorrect.")
        elif len(new_pw) < 4:
            flash("New password must be at least 4 characters.")
        else:
            emp.set_password(new_pw)
            db.session.commit()
            flash("Password updated successfully.")
        return redirect("/employee/settings")

    return render_emp("""
    <h4><i class="ti ti-settings"></i> Settings</h4>
    <div class="card p-3 col-md-5">
      <h5><i class="ti ti-shield-lock"></i> Change Password</h5>
      <form method="post">
        <input class="form-control mb-2" type="password" name="old_password" placeholder="Current password" required>
        <input class="form-control mb-2" type="password" name="new_password" placeholder="New password" required>
        <button class="btn btn-primary w-100">Update Password</button>
      </form>
      <small class="text-muted d-block mt-2">Forgot your password? Contact Admin/HR to reset it.</small>
    </div>""", e=emp)


# ---------------- PAYSLIP PDF DOWNLOAD (admin or the employee themselves) ----------------
@app.route("/payslip/<int:emp_id>")
def payslip_pdf(emp_id):
    # Allow access if admin is logged in, OR if the logged-in employee is downloading their own slip
    if not session.get("user") and session.get("employee_id") != emp_id:
        flash("Please log in to view this payslip.")
        return redirect("/login")

    emp = Employee.query.get_or_404(emp_id)

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    except ImportError:
        return "PDF generation requires the 'reportlab' package. Run: pip install reportlab", 500

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm, leftMargin=2*cm, rightMargin=2*cm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("T", parent=styles["Title"], textColor=colors.HexColor("#0d9488"))
    story = [
        Paragraph("PayrollPro", title_style),
        Paragraph(f"Salary Slip — {date.today().strftime('%B %Y')}", styles["Normal"]),
        Spacer(1, 14),
        Paragraph(f"<b>Employee:</b> {emp.name}", styles["Normal"]),
        Paragraph(f"<b>Department:</b> {emp.department} &nbsp;&nbsp; <b>Designation:</b> {emp.designation}", styles["Normal"]),
        Paragraph(f"<b>Email:</b> {emp.email} &nbsp;&nbsp; <b>Phone:</b> {emp.phone}", styles["Normal"]),
        Paragraph(f"<b>Date Joined:</b> {emp.date_joined or '—'}", styles["Normal"]),
        Spacer(1, 16),
    ]
    data = [
        ["Component", "Amount (₹)"],
        ["Basic Salary", f"{emp.basic:.2f}"],
        ["HRA", f"{emp.hra:.2f}"],
        ["Bonus", f"{emp.bonus:.2f}"],
        ["Allowance", f"{emp.allowance:.2f}"],
        ["PF Deduction", f"-{emp.pf:.2f}"],
        ["Tax Deduction", f"-{emp.tax:.2f}"],
        ["Other Deductions", f"-{emp.other_ded:.2f}"],
        ["Net Salary", f"{emp.net:.2f}"],
    ]
    t = Table(data, colWidths=[9*cm, 5*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#0d9488")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,-1), (-1,-1), "Helvetica-Bold"),
        ("LINEABOVE", (0,-1), (-1,-1), 1, colors.HexColor("#0d9488")),
        ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
        ("TOPPADDING", (0,0), (-1,-1), 6), ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 20))
    story.append(Paragraph("This is a system-generated salary slip.", styles["Normal"]))
    doc.build(story)
    buf.seek(0)

    return send_file(buf, mimetype="application/pdf", as_attachment=True,
                      download_name=f"payslip_{emp.name.replace(' ', '_')}.pdf")

# ---------------- JSON API ----------------
# A thin JSON layer over the same data the HTML pages use — same session
# cookie, same auto-migrated DB, same business logic (auto-attendance,
# overtime, appraisal math). Meant for the React UI concept, but usable by
# any client. GET requests are open to any logged-in admin/employee; state
# changes require the matching login.

def api_login_required(f):
    from functools import wraps
    @wraps(f)
    def wrap(*a, **kw):
        if not session.get("user"):
            return jsonify(error="Not authenticated. Log in at /login first."), 401
        return f(*a, **kw)
    return wrap

def api_employee_login_required(f):
    from functools import wraps
    @wraps(f)
    def wrap(*a, **kw):
        if not session.get("employee_id"):
            return jsonify(error="Not authenticated. Log in at /employee/login first."), 401
        return f(*a, **kw)
    return wrap

def employee_to_dict(e, include_sensitive=False):
    d = dict(
        id=e.id, name=e.name, department=e.department, designation=e.designation,
        email=e.email, phone=e.phone, status=e.status, date_joined=e.date_joined,
        tenure_label=e.tenure_label, basic=e.basic, hra=e.hra, bonus=e.bonus,
        allowance=e.allowance, pf=e.pf, tax=e.tax, other_ded=e.other_ded, net=e.net,
    )
    if include_sensitive:
        d.update(
            next_appraisal_date=str(e.next_appraisal_date) if e.next_appraisal_date else None,
            appraisal_due=e.appraisal_due, suggested_hike_pct=e.suggested_hike_pct,
            leave_balance=e.leave_balance,
        )
    return d

@app.route("/api/dashboard")
@api_login_required
def api_dashboard():
    today = str(date.today())
    trend = []
    for i in range(6, -1, -1):
        d = str(date.today() - timedelta(days=i))
        trend.append(dict(
            date=d, present=Attendance.query.filter_by(date=d, status="Present").count(),
            absent=Attendance.query.filter_by(date=d, status="Absent").count(),
        ))
    dept_totals = {}
    for e in Employee.query.all():
        dept_totals[e.department or "Unassigned"] = dept_totals.get(e.department or "Unassigned", 0) + e.net
    return jsonify(
        total_employees=Employee.query.count(),
        active=Employee.query.filter_by(status="Active").count(),
        inactive=Employee.query.filter_by(status="Inactive").count(),
        present_today=Attendance.query.filter_by(date=today, status="Present").count(),
        absent_today=Attendance.query.filter_by(date=today, status="Absent").count(),
        on_leave_today=Attendance.query.filter_by(date=today, status="Leave").count(),
        pending_leaves=LeaveRequest.query.filter_by(status="Pending").count(),
        monthly_payroll=round(sum(e.net for e in Employee.query.all()), 2),
        attendance_trend=trend,
        payroll_by_department=[dict(department=k, amount=round(v, 2)) for k, v in dept_totals.items()],
    )

@app.route("/api/employees", methods=["GET", "POST"])
@api_login_required
def api_employees():
    if request.method == "POST":
        f = request.get_json(force=True, silent=True) or {}
        required = ["name", "department", "designation", "email", "phone", "basic"]
        if any(not f.get(k) for k in required):
            return jsonify(error=f"Missing one of: {', '.join(required)}"), 400
        try:
            e = Employee(
                name=f["name"], department=f["department"], designation=f["designation"],
                email=f["email"], phone=f["phone"], date_joined=f.get("date_joined") or str(date.today()),
                basic=float(f["basic"]), hra=float(f.get("hra", 0)), bonus=float(f.get("bonus", 0)),
                allowance=float(f.get("allowance", 0)), pf=float(f.get("pf", 0)),
                tax=float(f.get("tax", 0)), other_ded=float(f.get("other_ded", 0)),
            )
        except (TypeError, ValueError):
            return jsonify(error="basic/hra/bonus/allowance/pf/tax/other_ded must be numbers"), 400
        e.set_password("employee123")
        db.session.add(e)
        db.session.commit()
        return jsonify(employee_to_dict(e, include_sensitive=True)), 201

    q = request.args.get("q", "").strip()
    query = Employee.query
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Employee.name.ilike(like), Employee.department.ilike(like),
                                     Employee.designation.ilike(like), Employee.email.ilike(like)))
    return jsonify([employee_to_dict(e) for e in query.order_by(Employee.name).all()])

@app.route("/api/employees/<int:eid>", methods=["GET", "DELETE"])
@api_login_required
def api_employee_detail(eid):
    e = Employee.query.get_or_404(eid)
    if request.method == "DELETE":
        db.session.delete(e)
        db.session.commit()
        return jsonify(deleted=eid)
    return jsonify(employee_to_dict(e, include_sensitive=True))

@app.route("/api/employees/<int:eid>/toggle_status", methods=["POST"])
@api_login_required
def api_toggle_status(eid):
    e = Employee.query.get_or_404(eid)
    e.status = "Inactive" if e.status == "Active" else "Active"
    db.session.commit()
    return jsonify(id=e.id, status=e.status)

@app.route("/api/attendance")
@api_login_required
def api_attendance():
    d = request.args.get("date", str(date.today()))
    rows = Attendance.query.filter_by(date=d).all()
    return jsonify([dict(emp_id=a.emp_id, date=a.date, status=a.status, source=a.source) for a in rows])

@app.route("/api/attendance/auto_generate", methods=["POST"])
@api_login_required
def api_auto_generate_attendance():
    d = (request.get_json(silent=True) or {}).get("date", str(date.today()))
    n = auto_mark_attendance_for_date(d)
    return jsonify(date=d, employees_marked=n)

@app.route("/api/payroll")
@api_login_required
def api_payroll():
    current_month = str(date.today())[:7]
    out = []
    for e in Employee.query.all():
        logs = PunchLog.query.filter(
            PunchLog.emp_id == e.id, PunchLog.date.like(f"{current_month}%"), PunchLog.time_out.isnot(None)
        ).all()
        overtime_hours = round(sum(l.overtime_hours for l in logs), 2)
        out.append(dict(
            **employee_to_dict(e), overtime_hours=overtime_hours,
            overtime_pay=round(overtime_hours * e.per_hour_rate * 1.5, 2),
        ))
    return jsonify(out)

@app.route("/api/leave", methods=["GET", "POST"])
@api_login_required
def api_leave():
    if request.method == "POST":
        f = request.get_json(force=True, silent=True) or {}
        required = ["emp_id", "leave_type", "start_date", "end_date"]
        if any(not f.get(k) for k in required):
            return jsonify(error=f"Missing one of: {', '.join(required)}"), 400
        l = LeaveRequest(emp_id=f["emp_id"], leave_type=f["leave_type"], start_date=f["start_date"],
                          end_date=f["end_date"], reason=f.get("reason", ""))
        db.session.add(l)
        db.session.commit()
        return jsonify(id=l.id, status=l.status), 201
    return jsonify([
        dict(id=l.id, emp_id=l.emp_id, leave_type=l.leave_type, start_date=l.start_date,
             end_date=l.end_date, reason=l.reason, status=l.status)
        for l in LeaveRequest.query.order_by(LeaveRequest.id.desc()).all()
    ])

@app.route("/api/leave/<int:lid>/<string:decision>", methods=["POST"])
@api_login_required
def api_leave_decision(lid, decision):
    if decision not in ("approve", "reject"):
        return jsonify(error="decision must be 'approve' or 'reject'"), 400
    l = LeaveRequest.query.get_or_404(lid)
    l.status = "Approved" if decision == "approve" else "Rejected"
    db.session.commit()
    return jsonify(id=l.id, status=l.status)

@app.route("/api/appraisals")
@api_login_required
def api_appraisals():
    return jsonify([employee_to_dict(e, include_sensitive=True) for e in Employee.query.filter_by(status="Active").order_by(Employee.date_joined).all()])

@app.route("/api/holidays", methods=["GET", "POST"])
@api_login_required
def api_holidays():
    if request.method == "POST":
        f = request.get_json(force=True, silent=True) or {}
        if not f.get("date") or not f.get("name"):
            return jsonify(error="date and name are required"), 400
        h = Holiday(date=f["date"], name=f["name"])
        db.session.add(h)
        db.session.commit()
        return jsonify(id=h.id, date=h.date, name=h.name), 201
    return jsonify([dict(id=h.id, date=h.date, name=h.name) for h in Holiday.query.order_by(Holiday.date).all()])

# --- Employee self-service API (separate session key, separate auth) ---
@app.route("/api/employee/me")
@api_employee_login_required
def api_employee_me():
    emp = Employee.query.get_or_404(session["employee_id"])
    return jsonify(dict(**employee_to_dict(emp, include_sensitive=True), **_employee_month_stats(emp)))

@app.route("/api/employee/punch", methods=["POST"])
@api_employee_login_required
def api_employee_punch():
    emp = Employee.query.get_or_404(session["employee_id"])
    action = (request.get_json(force=True, silent=True) or {}).get("action")
    if action not in ("in", "out"):
        return jsonify(error="action must be 'in' or 'out'"), 400
    today = str(date.today())
    now_str = datetime.now().strftime("%H:%M:%S")
    open_log = PunchLog.query.filter_by(emp_id=emp.id, date=today, time_out=None).first()
    if action == "in":
        if open_log:
            return jsonify(error="Already punched in"), 409
        db.session.add(PunchLog(emp_id=emp.id, date=today, time_in=now_str))
        db.session.commit()
        return jsonify(status="punched_in", time=now_str)
    if not open_log:
        return jsonify(error="No active punch-in found"), 409
    t_in = datetime.strptime(open_log.time_in, "%H:%M:%S")
    t_out = datetime.strptime(now_str, "%H:%M:%S")
    worked_hours = round((t_out - t_in).seconds / 3600, 2)
    open_log.time_out = now_str
    open_log.hours = worked_hours
    db.session.commit()
    return jsonify(status="punched_out", time=now_str, hours=worked_hours, overtime_hours=open_log.overtime_hours)

@app.route("/api/employee/leave", methods=["GET", "POST"])
@api_employee_login_required
def api_employee_leave():
    emp = Employee.query.get_or_404(session["employee_id"])
    if request.method == "POST":
        f = request.get_json(force=True, silent=True) or {}
        required = ["leave_type", "start_date", "end_date"]
        if any(not f.get(k) for k in required):
            return jsonify(error=f"Missing one of: {', '.join(required)}"), 400
        l = LeaveRequest(emp_id=emp.id, leave_type=f["leave_type"], start_date=f["start_date"],
                          end_date=f["end_date"], reason=f.get("reason", ""))
        db.session.add(l)
        db.session.commit()
        return jsonify(id=l.id, status=l.status), 201
    return jsonify([
        dict(id=l.id, leave_type=l.leave_type, start_date=l.start_date, end_date=l.end_date,
             reason=l.reason, status=l.status)
        for l in LeaveRequest.query.filter_by(emp_id=emp.id).order_by(LeaveRequest.id.desc()).all()
    ])




# ---------------- PASSWORD RESET ----------------
import secrets

PASSWORD_RESET_TTL_MINUTES = 15
password_reset_tokens = {}

def create_password_reset_token(email):
    token = secrets.token_urlsafe(24)
    password_reset_tokens[email.lower()] = {
        "token": token,
        "expires": datetime.now() + timedelta(minutes=PASSWORD_RESET_TTL_MINUTES),
    }
    return token

@app.route("/forgot-password", methods=["POST"])
def forgot_password():
    """Request a password reset token for an employee email.
    For this local/demo project, the token is returned in JSON instead of
    being emailed. In production, send the same token through an email service.
    """
    f = request.get_json(silent=True) or request.form
    email = (f.get("email") or "").strip().lower()
    if not email:
        return jsonify(error="Email is required"), 400

    emp = Employee.query.filter(db.func.lower(Employee.email) == email).first()
    # Avoid revealing whether an account exists in a production deployment.
    if not emp:
        return jsonify(message="If the account exists, a reset token has been generated."), 200

    token = create_password_reset_token(email)
    return jsonify(
        message="Password reset token generated.",
        reset_token=token,
        expires_in_minutes=PASSWORD_RESET_TTL_MINUTES
    ), 200

@app.route("/reset-password", methods=["POST"])
def reset_password():
    f = request.get_json(silent=True) or request.form
    email = (f.get("email") or "").strip().lower()
    token = (f.get("token") or "").strip()
    new_password = f.get("new_password") or ""

    if not email or not token or not new_password:
        return jsonify(error="Email, token and new_password are required"), 400
    if len(new_password) < 8:
        return jsonify(error="Password must be at least 8 characters"), 400

    saved = password_reset_tokens.get(email)
    if not saved:
        return jsonify(error="Invalid or expired reset token"), 400
    if datetime.now() > saved["expires"] or not secrets.compare_digest(saved["token"], token):
        password_reset_tokens.pop(email, None)
        return jsonify(error="Invalid or expired reset token"), 400

    emp = Employee.query.filter(db.func.lower(Employee.email) == email).first()
    if not emp:
        password_reset_tokens.pop(email, None)
        return jsonify(error="Invalid or expired reset token"), 400

    emp.set_password(new_password)
    db.session.commit()
    password_reset_tokens.pop(email, None)
    return jsonify(message="Password reset successfully. You can now log in."), 200


@app.route("/forgot-password", methods=["GET"])
def forgot_password_page():
    return """
    <!doctype html>
    <html><head><title>Forgot Password</title>
    <style>
      body{font-family:Inter,Arial,sans-serif;background:#f5f3ff;display:grid;place-items:center;min-height:100vh}
      .box{width:min(420px,90vw);background:white;padding:28px;border-radius:20px;box-shadow:0 15px 50px rgba(76,29,149,.12)}
      input,button{width:100%;box-sizing:border-box;padding:12px;margin:7px 0;border-radius:10px;border:1px solid #ddd}
      button{background:#7c3aed;color:white;border:0;font-weight:700;cursor:pointer}
      small{color:#666}
    </style></head>
    <body><div class="box">
      <h2>Reset your password</h2>
      <p>Enter your employee email to generate a reset token.</p>
      <form id="f">
        <input name="email" type="email" placeholder="Employee email" required>
        <button>Generate reset token</button>
      </form>
      <pre id="out"></pre>
      <small>For this college/local demo, the token is shown here. Production should deliver it by email.</small>
    </div>
    <script>
      document.getElementById('f').onsubmit = async (e) => {
        e.preventDefault();
        const email = e.target.email.value;
        const r = await fetch('/forgot-password', {
          method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({email})
        });
        document.getElementById('out').textContent = JSON.stringify(await r.json(), null, 2);
      };
    </script></body></html>
    """

# ---------------- RUN ----------------
if __name__ == "__main__":
    auto_migrate()  # patches an existing payroll.db with any new columns/tables
    with app.app_context():
        db.create_all()  # creates the database + tables from scratch if it doesn't exist yet
    app.run(debug=True)