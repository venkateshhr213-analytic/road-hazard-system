from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import random
import os
from flask_dance.contrib.google import make_google_blueprint, google
from flask_dance.contrib.facebook import make_facebook_blueprint, facebook
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "fallback-secret") # already exists probably

google_bp = make_google_blueprint(
    client_id="596222164061-o26hb0rdvnuajh2h67o7hpkm4kp53jt9.apps.googleusercontent.com",
    client_secret="GOCSPX-MJe_Qx0_O8Qbnph6o-60FvllNLw",
    scope=["profile", "email"],
    redirect_url="/login/google/authorized"
)

app.register_blueprint(google_bp, url_prefix="/login")

facebook_bp = make_facebook_blueprint(
    client_id="2334926873679451",
    client_secret="aa799577827886141d0903a0fd17a7d9",
    scope=["email"],
    redirect_url="/facebook-callback"
)

app.register_blueprint(facebook_bp, url_prefix="/login")

UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.secret_key = "road_hazard_secret"

# ================= EMAIL CONFIG =================
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = "venkateshhr213@gmail.com"      # 🔁 replace
app.config["MAIL_PASSWORD"] = "dlgjvhaqsvlsefzz"       # 🔁 replace

mail = Mail(app)

# ================= DATABASE =================
def get_db():
    return sqlite3.connect("database.db")

def init_db():
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            username TEXT UNIQUE,
            email TEXT UNIQUE,
            password TEXT,
            otp TEXT
        )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS hazards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        title TEXT,
        description TEXT,
        location TEXT,
        hazard_type TEXT,
        priority TEXT,
        status TEXT DEFAULT 'Pending',
        image TEXT,
        latitude REAL,
        longitude REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)

    db.commit()
    db.close()

init_db()

# ================= LOGIN =================
@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT id, name, password FROM users WHERE email=?", (email,))
        user = cursor.fetchone()
        db.close()

        if user and check_password_hash(user[2], password):
            session["user_id"] = user[0]
            session["user_name"] = user[1]
            return redirect(url_for("dashboard"))
        else:
            error = "Invalid email or password"

    return render_template("login.html", error=error)

# ================= SIGNUP =================
@app.route("/signup", methods=["GET", "POST"])
def signup():
    error = None

    if request.method == "POST":
        name = request.form["name"]
        username = request.form["username"]
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])

        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute(
                "INSERT INTO users (name, username, email, password) VALUES (?, ?, ?, ?)",
                (name, username, email, password)
            )
            db.commit()
            db.close()
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            error = "Username or email already exists"

    return render_template("signup.html", error=error)

# ================= FORGOT PASSWORD =================
@app.route("/forgot", methods=["GET", "POST"])
def forgot():
    if request.method == "POST":
        email = request.form["email"]
        otp = str(random.randint(100000, 999999))

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT id FROM users WHERE email=?", (email,))
        user = cursor.fetchone()

        if not user:
            return "Email not registered"

        cursor.execute("UPDATE users SET otp=? WHERE email=?", (otp, email))
        db.commit()
        db.close()

        msg = Message(
            "Password Reset OTP",
            sender=app.config["MAIL_USERNAME"],
            recipients=[email]
        )
        msg.body = f"Your OTP is: {otp}"
        mail.send(msg)

        session["reset_email"] = email
        return redirect(url_for("verify_otp"))

    return render_template("forgot.html")

# ================= VERIFY OTP =================
@app.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    if request.method == "POST":
        otp_input = request.form["otp"]
        email = session.get("reset_email")

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT otp FROM users WHERE email=?", (email,))
        db_otp = cursor.fetchone()
        db.close()

        if db_otp and otp_input == db_otp[0]:
            return redirect(url_for("reset_password"))
        else:
            return "Invalid OTP"

    return render_template("verify_otp.html")

# ================= RESET PASSWORD =================
@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    if request.method == "POST":
        new_password = generate_password_hash(request.form["password"])
        email = session.get("reset_email")

        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "UPDATE users SET password=?, otp=NULL WHERE email=?",
            (new_password, email)
        )
        db.commit()
        db.close()

        session.pop("reset_email", None)
        return redirect(url_for("login"))

    return render_template("reset_password.html")

# ================= DASHBOARD =================
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    cursor = db.cursor()

    # ===== STATS =====
    cursor.execute(
        "SELECT COUNT(*) FROM hazards WHERE user_id=?",
        (session["user_id"],)
    )
    total = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM hazards WHERE user_id=? AND status='Pending'",
        (session["user_id"],)
    )
    pending = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM hazards WHERE user_id=? AND status='Resolved'",
        (session["user_id"],)
    )
    resolved = cursor.fetchone()[0]

    # ===== RECENT HAZARDS (🔥 THIS WAS MISSING) =====
    cursor.execute("""
        SELECT
            id,
            title,
            location,
            hazard_type,
            priority,
            status,
            image,
            latitude,
            longitude
        FROM hazards
        WHERE user_id=?
        ORDER BY created_at DESC
        LIMIT 5
    """, (session["user_id"],))

    recent_hazards = cursor.fetchall()

    # ===== MAP HAZARDS =====
    cursor.execute("""
        SELECT id, title, latitude, longitude, hazard_type, priority
        FROM hazards
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    """)
    map_hazards = cursor.fetchall()

    db.close()

    return render_template(
        "dashboard.html",
        name=session["user_name"],
        total=total,
        pending=pending,
        resolved=resolved,
        recent_hazards=recent_hazards,   # ✅ NOW PASSED
        map_hazards=map_hazards
    )
    
# ================= EDIT/DELETE HAZARD =================
    
@app.route("/edit-hazard/<int:hazard_id>", methods=["GET", "POST"])
def edit_hazard(hazard_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    cursor = db.cursor()

    # Ensure hazard belongs to user
    cursor.execute("""
        SELECT title, description, location, hazard_type
        FROM hazards
        WHERE id=? AND user_id=?
    """, (hazard_id, session["user_id"]))

    hazard = cursor.fetchone()

    if not hazard:
        db.close()
        return "Unauthorized access"

    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        location = request.form["location"]
        hazard_type = request.form["hazard_type"]

        cursor.execute("""
            UPDATE hazards
            SET title=?, description=?, location=?, hazard_type=?
            WHERE id=? AND user_id=?
        """, (title, description, location, hazard_type, hazard_id, session["user_id"]))

        db.commit()
        db.close()
        return redirect(url_for("dashboard"))

    db.close()
    return render_template(
        "edit_hazard.html",
        hazard=hazard
    )
@app.route("/delete-hazard/<int:hazard_id>")
def delete_hazard(hazard_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        DELETE FROM hazards
        WHERE id=? AND user_id=?
    """, (hazard_id, session["user_id"]))

    db.commit()
    db.close()

    return redirect(url_for("dashboard"))
    
# ================= REPORT HAZARD =================
@app.route("/report", methods=["GET", "POST"])
def report():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        location = request.form["location"]
        hazard_type = request.form["hazard_type"]
        latitude = request.form.get("latitude")
        longitude = request.form.get("longitude")

        if hazard_type in ["Accident", "Open Manhole"]:
            priority = "High"
        elif hazard_type in ["Pothole", "Broken Signal"]:
            priority = "Medium"
        else:
            priority = "Low"

        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO hazards
            (user_id, title, description, location, hazard_type, priority, status, latitude, longitude)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session["user_id"],
            title,
            description,
            location,
            hazard_type,
            priority,
            "Pending",
            latitude,
            longitude
        ))

        db.commit()
        db.close()
        return redirect(url_for("dashboard"))

    return render_template("report.html")

# ================= LOGOUT =================
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))
# ================= USER PROFILE =================
@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        "SELECT name, email, profile_image FROM users WHERE id=?",
        (session["user_id"],)
    )
    user = cursor.fetchone()
    db.close()

    # 🔐 Safety fallback
    if not user:
        return redirect(url_for("logout"))

    name = user[0] or "User"
    email = user[1] or "Not available"
    profile_image = user[2] or "default.png"

    return render_template(
        "profile.html",
        name=name,
        email=email,
        profile_image=profile_image
    )
# Start Google Login
@app.route("/google-login")
def google_login():
    return redirect(url_for("google.login"))


# Google Callback
@app.route("/google-callback")
def google_callback():
    if not google.authorized:
        return redirect(url_for("google.login"))

    resp = google.get("/oauth2/v2/userinfo")
    user_info = resp.json()

    session["user"] = user_info["email"]
    session["name"] = user_info["name"]

    return redirect("/dashboard")
# Start Facebook Login
@app.route("/facebook-login")
def facebook_login():
    return redirect(url_for("facebook.login"))


# Facebook Callback
@app.route("/facebook-callback")
def facebook_callback():
    if not facebook.authorized:
        return redirect(url_for("facebook.login"))

    resp = facebook.get("/me?fields=id,name,email")
    user_info = resp.json()

    session["user"] = user_info.get("email", user_info["id"])
    session["name"] = user_info["name"]

    return redirect("/dashboard")
# ================= RUN =================
if __name__ == "__main__":
    app.run(debug=True)
