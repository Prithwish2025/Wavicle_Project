from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
import csv, os, datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
from flask import session

# Simple credentials (you can store in a config file later)
TEACHER_USERNAME = "teacher"
TEACHER_PASSWORD = "1234"  # Change this!
app.secret_key = "replace_with_a_random_secret"

DATA_DIR = "data"
UPLOAD_DIR = os.path.abspath("uploads")
ALLOWED_EXT = {"pdf","doc","docx","txt","png","jpg","jpeg"}

STUDENTS_FILE = os.path.join(DATA_DIR, "students.csv")
ATTENDANCE_FILE = os.path.join(DATA_DIR, "attendance_log.csv")
ASSIGNMENTS_FILE = os.path.join(DATA_DIR, "assignments.csv")
MARKS_FILE = os.path.join(DATA_DIR, "marks.csv")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.csv")
SUBMISSIONS_FILE = os.path.join(DATA_DIR, "submissions.csv")
MEETINGS_FILE = os.path.join(DATA_DIR, "meetings.csv")
MEETING_ATT_FILE = os.path.join(DATA_DIR, "meeting_attendance.csv")

def ensure_files():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    files_with_headers = {
        STUDENTS_FILE: ["roll","name"],
        ATTENDANCE_FILE: ["date","roll","status"],
        ASSIGNMENTS_FILE: ["assignment_id","title","max_marks","weight","due_date"],
        MARKS_FILE: ["assignment_id","roll","marks"],
        SETTINGS_FILE: None,
        SUBMISSIONS_FILE: ["assignment_id","roll","filename","submitted_on"],
        MEETINGS_FILE: ["meeting_id","title","date","time","link"],
        MEETING_ATT_FILE: ["meeting_id","roll","status"]
    }
    for path, headers in files_with_headers.items():
        if not os.path.exists(path):
            with open(path,"w",newline="") as f:
                writer = csv.writer(f)
                if headers:
                    writer.writerow(headers)
    # default settings if empty
    if os.path.getsize(SETTINGS_FILE) == 0:
        with open(SETTINGS_FILE,"w",newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["att_red","75"])
            writer.writerow(["att_yellow","85"])
            writer.writerow(["perf_red","50"])
            writer.writerow(["perf_yellow","70"])
            writer.writerow(["missing_policy","strict"])

ensure_files()

# CSV helpers
def read_csv(file):
    if not os.path.exists(file):
        return []
    with open(file,newline="") as f:
        return list(csv.DictReader(f))

def append_csv(file, row):
    with open(file,"a",newline="") as f:
        writer = csv.writer(f)
        writer.writerow(row)

def write_csv(file, rows, headers):
    with open(file,"w",newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for r in rows:
            writer.writerow([r[h] for h in headers])

# settings helpers
def load_settings():
    s={}
    with open(SETTINGS_FILE,newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row)>=2:
                s[row[0]] = row[1]
    return s

def save_settings(settings_dict):
    rows = [[k,v] for k,v in settings_dict.items()]
    with open(SETTINGS_FILE,"w",newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".",1)[1].lower() in ALLOWED_EXT

# Routes
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == TEACHER_USERNAME and password == TEACHER_PASSWORD:
            session["teacher_logged_in"] = True
            flash("Login successful","success")
            return redirect(url_for("teacher"))
        else:
            flash("Invalid credentials","error")
            return redirect(url_for("login"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("teacher_logged_in", None)
    flash("Logged out","success")
    return redirect(url_for("index"))

# Protect teacher routes
@app.before_request
def require_login():
    protected_routes = ["/teacher","/mark_attendance","/create_assignment",
                        "/enter_marks","/update_settings","/schedule_meeting",
                        "/view_submissions"]
    if any(request.path.startswith(r) for r in protected_routes):
        if not session.get("teacher_logged_in"):
            flash("Login required","error")
            return redirect(url_for("login"))



@app.route("/")
def index():
    return render_template("index.html")

@app.route("/teacher")
def teacher():
    students = read_csv(STUDENTS_FILE)
    assignments = read_csv(ASSIGNMENTS_FILE)
    settings = load_settings()
    meetings = read_csv(MEETINGS_FILE)
    return render_template("teacher.html", students=students, assignments=assignments, settings=settings, meetings=meetings)

@app.route("/add_student", methods=["POST"])
def add_student():
    roll = request.form.get("roll","").strip()
    name = request.form.get("name","").strip()
    if not roll or not name:
        flash("Provide roll and name","error"); return redirect(url_for("teacher"))
    students = read_csv(STUDENTS_FILE)
    if any(s["roll"]==roll for s in students):
        flash("Roll already exists","error"); return redirect(url_for("teacher"))
    append_csv(STUDENTS_FILE,[roll,name])
    flash("Student added","success"); return redirect(url_for("teacher"))

@app.route("/mark_attendance", methods=["GET","POST"])
def mark_attendance():
    students = read_csv(STUDENTS_FILE)
    date = request.args.get("date", datetime.date.today().isoformat())
    if request.method=="POST":
        date = request.form.get("date")
        all_att = read_csv(ATTENDANCE_FILE)
        filtered = [r for r in all_att if r["date"] != date]
        for s in students:
            roll = s["roll"]
            status = "Present" if request.form.get(f"present_{roll}")=="on" else "Absent"
            filtered.append({"date":date,"roll":roll,"status":status})
        write_csv(ATTENDANCE_FILE, filtered, ["date","roll","status"])
        flash("Attendance saved for "+date,"success")
        return redirect(url_for("teacher"))
    # Build attendance map for the selected date
    all_att = read_csv(ATTENDANCE_FILE)
    attendance_map = {r["roll"]: r["status"] for r in all_att if r["date"] == date}
    settings = load_settings()
    return render_template("mark_attendance.html", students=students, date=date, attendance_map=attendance_map, settings=settings)
    

@app.route("/create_assignment", methods=["POST"])
def create_assignment():
    title = request.form.get("title","").strip()
    max_marks = request.form.get("max_marks","").strip()
    weight = request.form.get("weight","").strip()
    due_date = request.form.get("due_date","").strip()
    if not title or not max_marks or not weight:
        flash("Provide title, max marks, and weight","error"); return redirect(url_for("teacher"))
    assignments = read_csv(ASSIGNMENTS_FILE)
    next_id = 1
    if assignments:
        ids = [int(a["assignment_id"]) for a in assignments]
        next_id = max(ids)+1
    append_csv(ASSIGNMENTS_FILE,[str(next_id), title, max_marks, weight, due_date])
    flash("Assignment created","success"); return redirect(url_for("teacher"))

@app.route("/enter_marks/<assignment_id>", methods=["GET","POST"])
def enter_marks(assignment_id):
    students = read_csv(STUDENTS_FILE)
    assignments = read_csv(ASSIGNMENTS_FILE)
    assignment = next((a for a in assignments if a["assignment_id"]==assignment_id), None)
    if not assignment:
        flash("Assignment not found","error"); return redirect(url_for("teacher"))
    if request.method=="POST":
        all_marks = read_csv(MARKS_FILE)
        remaining = [m for m in all_marks if m["assignment_id"] != assignment_id]
        for s in students:
            roll = s["roll"]
            marks_val = request.form.get(f"marks_{roll}","").strip()
            if marks_val=="":
                continue
            try:
                float(marks_val)
            except:
                continue
            remaining.append({"assignment_id":assignment_id,"roll":roll,"marks":marks_val})
        write_csv(MARKS_FILE, remaining, ["assignment_id","roll","marks"])
        flash("Marks saved","success"); return redirect(url_for("teacher"))
    existing = read_csv(MARKS_FILE)
    marks_map = {(m["assignment_id"],m["roll"]): m["marks"] for m in existing}
    return render_template("enter_marks.html", students=students, assignment=assignment, marks_map=marks_map)

@app.route("/update_settings", methods=["POST"])
def update_settings():
    settings = load_settings()
    settings["att_red"] = request.form.get("att_red", settings.get("att_red","75"))
    settings["att_yellow"] = request.form.get("att_yellow", settings.get("att_yellow","85"))
    settings["perf_red"] = request.form.get("perf_red", settings.get("perf_red","50"))
    settings["perf_yellow"] = request.form.get("perf_yellow", settings.get("perf_yellow","70"))
    settings["missing_policy"] = request.form.get("missing_policy", settings.get("missing_policy","strict"))
    save_settings(settings)
    flash("Settings updated","success"); return redirect(url_for("teacher"))

# --- Submissions ---
@app.route("/submit_assignment/<assignment_id>", methods=["GET","POST"])
def submit_assignment(assignment_id):
    assignments = read_csv(ASSIGNMENTS_FILE)
    assignment = next((a for a in assignments if a["assignment_id"]==assignment_id), None)
    if not assignment:
        flash("Assignment not found","error"); return redirect(url_for("student"))
    if request.method=="POST":
        roll = request.form.get("roll","").strip()
        if not roll:
            flash("Provide roll","error"); return redirect(url_for("submit_assignment", assignment_id=assignment_id))
        file = request.files.get("file")
        if not file or file.filename=="":
            flash("No file selected","error"); return redirect(url_for("submit_assignment", assignment_id=assignment_id))
        if not allowed_file(file.filename):
            flash("File type not allowed","error"); return redirect(url_for("submit_assignment", assignment_id=assignment_id))
        filename = secure_filename(file.filename)
        # create folder uploads/<assignment_id>/
        dest_dir = os.path.join(UPLOAD_DIR, assignment_id)
        os.makedirs(dest_dir, exist_ok=True)
        save_path = os.path.join(dest_dir, f"{roll}_{filename}")
        file.save(save_path)
        append_csv(SUBMISSIONS_FILE, [assignment_id, roll, f"{roll}_{filename}", datetime.datetime.now().isoformat()])
        flash("Submission uploaded","success")
        return redirect(url_for("student"))
    return render_template("submit_assignment.html", assignment=assignment)

@app.route("/view_submissions/<assignment_id>")
def view_submissions(assignment_id):
    submissions = read_csv(SUBMISSIONS_FILE)
    subs = [s for s in submissions if s["assignment_id"]==assignment_id]
    assignments = read_csv(ASSIGNMENTS_FILE)
    assignment = next((a for a in assignments if a["assignment_id"]==assignment_id), None)
    return render_template("view_submissions.html", subs=subs, assignment=assignment)

@app.route("/download_submission/<assignment_id>/<filename>")
def download_submission(assignment_id, filename):
    folder = os.path.join(UPLOAD_DIR, assignment_id)
    file_path = os.path.join(folder, filename)
    if not os.path.exists(file_path):
        flash("File not found","error")
        return redirect(url_for("view_submissions", assignment_id=assignment_id))
    return send_from_directory(folder, filename, as_attachment=True)


# --- Meetings ---
@app.route("/schedule_meeting", methods=["POST"])
def schedule_meeting():
    title = request.form.get("title","").strip()
    date = request.form.get("date","").strip()
    time = request.form.get("time","").strip()
    link = request.form.get("link","").strip()
    if not title or not date or not time:
        flash("Provide title, date and time","error"); return redirect(url_for("teacher"))
    meetings = read_csv(MEETINGS_FILE)
    next_id = 1
    if meetings:
        ids = [int(m["meeting_id"]) for m in meetings]
        next_id = max(ids)+1
    append_csv(MEETINGS_FILE, [str(next_id), title, date, time, link])
    flash("Meeting scheduled","success"); return redirect(url_for("teacher"))

@app.route("/attend_meeting/<meeting_id>", methods=["POST"])
def attend_meeting(meeting_id):
    roll = request.form.get("roll","").strip()
    if not roll:
        flash("Roll number missing","error")
        return redirect(url_for("student"))

    all_att = read_csv(MEETING_ATT_FILE)
    already_attended = any(r["meeting_id"] == meeting_id and r["roll"] == roll for r in all_att)
    if already_attended:
        flash("⚠️ You have already marked attendance for this meeting.","info")
        return redirect(url_for("view_student", roll=roll))

    all_att.append({"meeting_id":meeting_id,"roll":roll,"status":"Attended"})
    write_csv(MEETING_ATT_FILE, all_att, ["meeting_id","roll","status"])

    flash("✅ Your attendance for the meeting has been marked!","success")
    return redirect(url_for("view_student", roll=roll))


@app.route("/meetings/<roll>")
def view_meetings(roll):
    meetings = read_csv(MEETINGS_FILE)
    return render_template("view_meetings.html", meetings=meetings, roll=roll)

@app.route("/view_meeting_attendance/<meeting_id>")
def view_meeting_attendance(meeting_id):
    all_att = read_csv(MEETING_ATT_FILE)
    attendees = [r for r in all_att if r["meeting_id"]==meeting_id]
    return render_template("view_meeting_attendance.html", attendees=attendees, meeting_id=meeting_id)

# --- Student flows ---
@app.route("/student", methods=["GET","POST"])
def student():
    if request.method=="POST":
        roll = request.form.get("roll","").strip()
        students = read_csv(STUDENTS_FILE)
        if not any(s["roll"]==roll for s in students):
            flash("Roll not found","error"); return redirect(url_for("student"))
        return redirect(url_for("view_student", roll=roll))
    return render_template("student.html")

@app.route("/view_student/<roll>")
def view_student(roll):
    students = read_csv(STUDENTS_FILE)
    student = next((s for s in students if s["roll"]==roll), None)
    if not student:
        flash("Student not found","error"); return redirect(url_for("student"))
    settings = load_settings()
    att_red = float(settings.get("att_red","75"))
    att_yellow = float(settings.get("att_yellow","85"))
    perf_red = float(settings.get("perf_red","50"))
    perf_yellow = float(settings.get("perf_yellow","70"))
    missing_policy = settings.get("missing_policy","strict")

    # attendance
    all_att = read_csv(ATTENDANCE_FILE)
    student_att = [r for r in all_att if r["roll"]==roll]
    total_days = len(student_att)
    present_days = sum(1 for r in student_att if r["status"].lower()=="present")
    attendance_pct = (present_days/total_days*100) if total_days>0 else 0.0
    if attendance_pct < att_red: att_status="red"
    elif attendance_pct < att_yellow: att_status="yellow"
    else: att_status="green"

    # assignments & marks
    assignments = read_csv(ASSIGNMENTS_FILE)
    marks = read_csv(MARKS_FILE)
    subms = read_csv(SUBMISSIONS_FILE)
    assignment_rows = []
    weighted_sum = 0.0
    sum_weights_considered = 0.0
    total_weight = sum(float(a["weight"]) for a in assignments) if assignments else 0.0

    for a in assignments:
        aid=a["assignment_id"]; max_marks=float(a["max_marks"]); weight=float(a["weight"])
        mark_record = next((m for m in marks if m["assignment_id"]==aid and m["roll"]==roll), None)
        sub_record = next((s for s in subms if s["assignment_id"]==aid and s["roll"]==roll), None)
        if mark_record:
            obtained = float(mark_record["marks"])
            score_pct = (obtained/max_marks)*100 if max_marks>0 else 0.0
            contribution = (score_pct/100.0)*weight
            weighted_sum += contribution
            sum_weights_considered += weight
            status_text = f"{obtained}/{int(max_marks)}"
        else:
            status_text = "Not graded"
            if missing_policy=="rescale":
                pass
            else:
                sum_weights_considered += weight
        assignment_rows.append({
            "assignment_id":aid,
            "title":a["title"],
            "max_marks":a["max_marks"],
            "weight":a["weight"],
            "marks": status_text,
            "submitted": bool(sub_record)
        })

    overall_perf = 0.0
    if assignments:
        if missing_policy=="rescale":
            denom = sum_weights_considered if sum_weights_considered>0 else 1.0
            overall_perf = (weighted_sum/denom)*100.0
        else:
            denom = total_weight if total_weight>0 else 1.0
            overall_perf = (weighted_sum/denom)*100.0

    if overall_perf < perf_red: perf_status="red"
    elif overall_perf < perf_yellow: perf_status="yellow"
    else: perf_status="green"

    # meetings
    meetings = read_csv(MEETINGS_FILE)
    meeting_att = read_csv(MEETING_ATT_FILE)
    upcoming = meetings  # small app; you could filter by date

    # recent attendance history
    history = sorted(student_att, key=lambda r: r["date"], reverse=True)

    return render_template("view_student.html",
                           student=student,
                           attendance_pct=round(attendance_pct,2),
                           present_days=present_days,
                           total_days=total_days,
                           att_status=att_status,
                           assignments=assignment_rows,
                           overall_perf=round(overall_perf,2),
                           perf_status=perf_status,
                           history=history,
                           meetings=upcoming,
                           meeting_att=meeting_att)

if __name__ == "__main__":
    app.run(debug=True)