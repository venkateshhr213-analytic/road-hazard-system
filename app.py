from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3, random, os
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import base64
import cv2
from datetime import datetime
from flask_mail import Mail, Message
from ml_model import predict_hazard
from flask_dance.contrib.google import make_google_blueprint, google
from flask_dance.contrib.facebook import make_facebook_blueprint, facebook
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB limit
# ================= SECRET =================
app.secret_key = os.environ.get("SECRET_KEY","fallback-secret")

# ================= UPLOAD =================
UPLOAD_FOLDER="static/uploads"
app.config["UPLOAD_FOLDER"]=UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER,exist_ok=True)

# ================= MAIL =================
app.config["MAIL_SERVER"]="smtp.gmail.com"
app.config["MAIL_PORT"]=587
app.config["MAIL_USE_TLS"]=True
app.config["MAIL_USERNAME"]=os.environ.get("MAIL_USERNAME")
app.config["MAIL_PASSWORD"]=os.environ.get("MAIL_PASSWORD")
mail=Mail(app)

# ================= GOOGLE LOGIN =================
google_bp=make_google_blueprint(
client_id=os.environ.get("GOOGLE_CLIENT_ID"),
client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
scope=["profile","email"], redirect_url="/login/google/authorized"
)
app.register_blueprint(google_bp,url_prefix="/login")

# ================= FACEBOOK LOGIN =================
facebook_bp=make_facebook_blueprint(
client_id=os.environ.get("FACEBOOK_CLIENT_ID"),
client_secret=os.environ.get("FACEBOOK_CLIENT_SECRET"),
scope=["email"], redirect_url="/login/facebook/authorized"
)
app.register_blueprint(facebook_bp,url_prefix="/login")

# ================= DATABASE =================
def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db=get_db()
    c=db.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    username TEXT,
    email TEXT UNIQUE,
    password TEXT,
    otp TEXT,
    profile_image TEXT DEFAULT 'default.png',
    role TEXT DEFAULT 'user')
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS hazards(
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(user_id) REFERENCES users(id))
    """)

    db.commit()
    db.close()

init_db()
# ================= AI =================
def predict_priority(text, hazard_pred=None):
    t = text.lower()

    # Text-based detection
    if any(w in t for w in ["accident","injured","fire","death"]):
        text_priority = "High"
    elif any(w in t for w in ["pothole","broken","crack"]):
        text_priority = "Medium"
    else:
        text_priority = "Low"

    #  Combine with ML prediction
    if hazard_pred == 1 and text_priority == "High":
        return "High"
    elif hazard_pred == 1:
        return "Medium"
    else:
        return text_priority
def fake(text):
    text = text.strip().lower()

    # Very short text
    if len(text) < 8:
        return True

    # Spam / fake words
    if text in ["test", "abc", "nothing", "no issue"]:
        return True

    return False

# ================= LOGIN =================
@app.route("/",methods=["GET","POST"])
@app.route("/login",methods=["GET","POST"])
def login():
    err=None
    if request.method=="POST":
        email=request.form["email"]
        pwd=request.form["password"]

        db=get_db();c=db.cursor()
        c.execute("""SELECT id,name, username,email,password,otp,profile_image,role
                  FROM users WHERE email=?""",(email,))
        u=c.fetchone();db.close()

        if u and check_password_hash(u[4],pwd):
            session["user_id"]=u[0]
            session["user_name"]=u[1]
            session["role"]=u[7]
            return redirect("/dashboard")
        else:
          err="Invalid email or password"
    return render_template("login.html",error=err)

# ================= SIGNUP =================
@app.route("/signup",methods=["GET","POST"])
def signup():
    error=None
    if request.method=="POST":
        name=request.form["name"]
        username=request.form["username"]
        email=request.form["email"]
        password = generate_password_hash(request.form["password"])
        try:
            db=get_db();c=db.cursor()
            c.execute("INSERT INTO users(name,username,email,password) VALUES(?,?,?,?)",
            (name,username,email,password))
            db.commit();db.close()
            return redirect(url_for("/login"))
        except sqlite3.IntegrityError:
          error =  "username or email already exists"
    return render_template("signup.html",error=error)
         
# ================= GOOGLE LOGIN ROUTE =================
@app.route("/google-login")
def g_login():
    return redirect(url_for("google.login"))

@app.route("/google-callback")
def g_callback():
    if not google.authorized: return redirect(url_for("google.login"))
    info=google.get("/oauth2/v2/userinfo").json()
    session["user_name"]=info["name"]
    session["user_id"]=info["email"]
    session["role"]="user"
    return redirect("/dashboard")

# ================= FACEBOOK =================
@app.route("/facebook-login")
def f_login():
    return redirect(url_for("facebook.login"))

@app.route("/facebook-callback")
def f_callback():
    if not facebook.authorized: return redirect(url_for("facebook.login"))
    info=facebook.get("/me?fields=name,email").json()
    session["user_name"]=info["name"]
    session["user_id"]=info.get("email","fb")
    session["role"]="user"
    return redirect("/dashboard")

# ================= FORGOT =================
@app.route("/forgot",methods=["GET","POST"])
def forgot():
    if request.method=="POST":
        email=request.form["email"]
        otp=str(random.randint(100000,999999))
        db=get_db();c=db.cursor()
        c.execute("UPDATE users SET otp=? WHERE email=?",(otp,email))
        db.commit();db.close()

        msg=Message("OTP",sender=app.config["MAIL_USERNAME"],recipients=[email])
        msg.body=f"OTP: {otp}"
        mail.send(msg)

        session["reset"]=email
        return redirect("/verify-otp")
    return render_template("forgot.html")

@app.route("/verify-otp",methods=["GET","POST"])
def verify():
    if request.method=="POST":
        otp=request.form["otp"]
        db=get_db();c=db.cursor()
        c.execute("SELECT otp FROM users WHERE email=?",(session["reset"],))
        if c.fetchone()[0]==otp: return redirect("/reset-password")
    return render_template("verify_otp.html")

@app.route("/reset-password",methods=["GET","POST"])
def reset():
    if request.method=="POST":
        db=get_db();c=db.cursor()
        c.execute("UPDATE users SET password=? WHERE email=?",
        (generate_password_hash(request.form["password"]),session["reset"]))
        db.commit();db.close()
        return redirect("/login")
    return render_template("reset_password.html")

# ================= DASHBOARD =================
@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect("/login")

    db = get_db()
    c = db.cursor()

    # counts
    c.execute("SELECT COUNT(*) FROM hazards WHERE user_id=?", (session["user_id"],))
    total = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM hazards WHERE user_id=? AND status='Pending'", (session["user_id"],))
    pending = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM hazards WHERE user_id=? AND status='Resolved'", (session["user_id"],))
    resolved = c.fetchone()[0]


    # FIX IS HERE 
    c.execute("""
        SELECT id,title,location,hazard_type,priority,status,image,latitude,longitude
        FROM hazards
        WHERE user_id=?
        ORDER BY id DESC
        LIMIT 5
    """, (session["user_id"],))

    recent_hazards = [dict(row) for row in c.fetchall()]


    # map hazards
    c.execute("""
        SELECT title, latitude, longitude, hazard_type, priority
        FROM hazards
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    """)

    rows = c.fetchall()
    map_hazards = [list(r) for r in rows]

    db.close()

    return render_template(
        "dashboard.html",
        total=total,
        pending=pending,
        resolved=resolved,
        recent_hazards=recent_hazards,
        map_hazards=map_hazards,
        google_maps_api_key=os.environ.get("GOOGLE_MAPS_API_KEY")
    )
# ================= REPORT =================
@app.route("/report", methods=["GET", "POST"])
def report():
    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":

        desc = request.form["description"]

        # Fake detection
        if fake(desc):
            return "Fake report detected"

        # ML Inputs
        road_condition = int(request.form["road_condition"])
        traffic = int(request.form["traffic"])
        weather = int(request.form["weather"])
        accident_history = int(request.form["accident_history"])

        #  ML Prediction
        hazard_pred = predict_hazard(
            road_condition, traffic, weather, accident_history
        )

        #  CAMERA IMAGE
        img = None
        photo_data = request.form.get("photo_data")
        image_result = "Low"

        if photo_data:
            header, encoded = photo_data.split(",", 1)
            binary_data = base64.b64decode(encoded)

            filename = f"{datetime.now().timestamp()}.png"
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)

            with open(filepath, "wb") as f:
                f.write(binary_data)

            img = filename

            #  OpenCV Image Analysis
            import cv2

            image = cv2.imread(filepath)
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 100, 200)

            edge_score = edges.mean()

            if edge_score > 50:
                image_result = "High"
            elif edge_score > 25:
                image_result = "Medium"
            else:
                image_result = "Low"

        #  TEXT + ML PRIORITY
        text_ml_priority = predict_priority(desc, hazard_pred)

        #  FINAL HYBRID AI DECISION
        if image_result == "High" or text_ml_priority == "High":
            pr = "High"
        elif image_result == "Medium" or text_ml_priority == "Medium":
            pr = "Medium"
        else:
            pr = "Low"

        #  SAVE TO DATABASE
        db = get_db()
        c = db.cursor()

        c.execute("""
        INSERT INTO hazards(user_id, title, description, location,
        hazard_type, priority, status, image, latitude, longitude)
        VALUES(?,?,?,?,?,?,?,?,?,?)
        """,
        (
            session["user_id"],
            request.form["title"],
            desc,
            request.form["location"],
            request.form["hazard_type"],
            pr,
            "Pending",
            img,
            request.form.get("latitude"),
            request.form.get("longitude")
        ))

        db.commit()
        db.close()

        return redirect("/dashboard")

    return render_template(
        "report.html",
        GOOGLE_MAPS_API_KEY=os.environ.get("GOOGLE_MAPS_API_KEY")
    )
# ================= EDIT =================
@app.route("/edit-hazard/<int:hazard_id>", methods=["GET","POST"])
def edit_hazard(hazard_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    c = db.cursor()

    # ---------- UPDATE ----------
    if request.method == "POST":

        desc = request.form["description"]

        #  ML Inputs
        road_condition = int(request.form["road_condition"])
        traffic = int(request.form["traffic"])
        weather = int(request.form["weather"])
        accident_history = int(request.form["accident_history"])

        #  ML Prediction
        hazard_pred = predict_hazard(
            road_condition, traffic, weather, accident_history
        )

        #  Hybrid AI Priority
        pr = predict_priority(desc, hazard_pred)

        c.execute("""
            UPDATE hazards
            SET title=?, description=?, location=?, hazard_type=?,
                status=?, priority=?, latitude=?, longitude=?
            WHERE id=? AND user_id=?
        """,(
            request.form["title"],
            desc,
            request.form["location"],
            request.form["hazard_type"],
            request.form["status"],
            pr,
            request.form.get("latitude"),
            request.form.get("longitude"),
            hazard_id,
            session["user_id"]
        ))

        db.commit()
        db.close()
        return redirect(url_for("dashboard"))

    # ---------- GET DATA ----------
    c.execute("""
        SELECT title,description,location,hazard_type,status,priority,latitude,longitude
        FROM hazards
        WHERE id=? AND user_id=?
    """,(hazard_id, session["user_id"]))

    h = c.fetchone()
    db.close()

    if not h:
        return "Hazard not found"

    return render_template(
        "edit_hazard.html",
        hazard={
            "title":h[0],
            "description":h[1],
            "location":h[2],
            "hazard_type":h[3],
            "status":h[4],
            "priority":h[5],
            "latitude":h[6],
            "longitude":h[7]
        },
        google_maps_api_key=os.environ.get("GOOGLE_MAPS_API_KEY")
    )
# ================= DELETE =================
@app.route("/delete-hazard/<int:hazard_id>")
def delete_hazard(hazard_id):

    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        "DELETE FROM hazards WHERE id=? AND user_id=?",
        (hazard_id, session["user_id"])
    )

    db.commit()
    db.close()

    return redirect(url_for("dashboard"))

@app.route("/admin/resolve/<int:id>",methods=["POST"])
def resolve(id):
    db=get_db();c=db.cursor()
    c.execute("UPDATE hazards SET status='Resolved' WHERE id=?",(id,))
    db.commit();db.close()
    return redirect("/admin/dashboard")

# ================= PROFILE =================
@app.route("/profile")
def profile():
    db=get_db();c=db.cursor()
    c.execute("SELECT name,email,profile_image FROM users WHERE id=?",(session["user_id"],))
    u=c.fetchone();db.close()
    return render_template("profile.html",name=u[0],email=u[1],profile_image=u[2])

# ================= LOGOUT =================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/resolve/<int:hazard_id>", methods=["POST"])
def resolve_hazard(hazard_id):

    if "user_id" not in session or session.get("role") != "admin":
        return redirect("/login")

    db = get_db()
    c = db.cursor()

    c.execute(
        "UPDATE hazards SET status='Resolved' WHERE id=?",
        (hazard_id,)
    )

    db.commit()
    db.close()

    return redirect(url_for("admin_dashboard"))
@app.route("/admin/dashboard")
def admin_dashboard():

    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("dashboard"))

    db = get_db()
    c = db.cursor()

    # stats
    c.execute("SELECT COUNT(*) FROM hazards")
    total = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM hazards WHERE status='Pending'")
    pending = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM hazards WHERE status='Resolved'")
    resolved = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM hazards WHERE priority='High'")
    high_priority = c.fetchone()[0]

    # table
    c.execute("""
        SELECT id,title,location,hazard_type,priority,status
        FROM hazards ORDER BY id DESC
    """)
    hazards = c.fetchall()

    # ⭐l CONVERT HEATMAP DATA TO NORMAL LIST
    c.execute("""
        SELECT latitude, longitude
        FROM hazards
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    """)

    rows = c.fetchall()
    heatmap_points = [[r["latitude"], r["longitude"]] for r in rows]

    db.close()

    return render_template(
        "admin_dashboard.html",
        hazards=hazards,
        total=total,
        pending=pending,
        resolved=resolved,
        high_priority=high_priority,
        heatmap_points=heatmap_points,
        google_maps_api_key=os.environ.get("GOOGLE_MAPS_API_KEY")
    )
# ================= RUN =================
if __name__=="__main__":
    app.run(debug=True)