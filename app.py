from flask import Flask, render_template, request, redirect, session, flash, send_file
import sqlite3, os
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "secretkey"

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

bad_words = ["kanker", "fuck", "shit", "tering"]

# 🔥 JOUW ADMIN (BELANGRIJK)
ADMIN = "Stefan"

def db():
    return sqlite3.connect("sitspots.db")

def init_db():
    conn = db()
    c = conn.cursor()

    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT)')

    c.execute('''
    CREATE TABLE IF NOT EXISTS spots (
        id INTEGER PRIMARY KEY,
        name TEXT,
        location TEXT,
        description TEXT,
        lat REAL,
        lng REAL,
        username TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    c.execute('CREATE TABLE IF NOT EXISTS images (id INTEGER PRIMARY KEY, spot_id INTEGER, filename TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS ratings (id INTEGER PRIMARY KEY, spot_id INTEGER, username TEXT, rating INTEGER, comment TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS comments (id INTEGER PRIMARY KEY, spot_id INTEGER, username TEXT, text TEXT)')

    conn.commit()
    conn.close()

init_db()

@app.route("/")
def index():
    search = request.args.get("search","")
    conn = db()
    c = conn.cursor()

    if search:
        c.execute("SELECT * FROM spots WHERE location LIKE ?", ('%'+search+'%',))
    else:
        c.execute("SELECT * FROM spots")

    spots = c.fetchall()
    conn.close()

    return render_template(
        "index.html",
        spots=spots,
        user=session.get("user"),
        admin=ADMIN   # 🔥 DIT WAS BELANGRIJK
    )

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        u = request.form["username"]
        p = generate_password_hash(request.form["password"], method='pbkdf2:sha256')

        try:
            conn = db()
            c = conn.cursor()
            c.execute("INSERT INTO users (username,password) VALUES (?,?)",(u,p))
            conn.commit()
            conn.close()
            return redirect("/login")
        except:
            flash("Gebruiker bestaat al")

    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u = request.form["username"]
        p = request.form["password"]

        conn = db()
        c = conn.cursor()
        c.execute("SELECT password FROM users WHERE username=?", (u,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user[0], p):
            session["user"] = u
            return redirect("/")
        else:
            flash("Verkeerde login")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/add", methods=["GET","POST"])
def add():
    if "user" not in session:
        return redirect("/login")

    if request.method == "POST":
        name = request.form["name"]
        loc = request.form["location"]
        desc = request.form["description"]
        lat = request.form["lat"]
        lng = request.form["lng"]
        user = session["user"]

        text = (name + " " + desc).lower()
        for word in bad_words:
            if word in text:
                flash("Ongepaste woorden niet toegestaan")
                return redirect("/add")

        conn = db()
        c = conn.cursor()

        c.execute("SELECT created_at FROM spots WHERE username=? ORDER BY created_at DESC LIMIT 1", (user,))
        last = c.fetchone()

        if last:
            last_time = datetime.strptime(last[0], "%Y-%m-%d %H:%M:%S")
            if datetime.now() - last_time < timedelta(minutes=30):
                flash("Max 1 spot per 30 min")
                return redirect("/add")

        c.execute("""
        INSERT INTO spots (name,location,description,lat,lng,username)
        VALUES (?,?,?,?,?,?)
        """, (name,loc,desc,lat,lng,user))

        sid = c.lastrowid

        files = request.files.getlist("images")
        for f in files:
            if f.filename:
                fname = secure_filename(f.filename)
                f.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
                c.execute("INSERT INTO images (spot_id,filename) VALUES (?,?)",(sid,fname))

        conn.commit()
        conn.close()

        return redirect("/")

    return render_template("add.html")

@app.route("/spot/<int:id>")
def spot(id):
    conn = db()
    c = conn.cursor()

    c.execute("SELECT * FROM spots WHERE id=?", (id,))
    s = c.fetchone()

    c.execute("SELECT filename FROM images WHERE spot_id=?", (id,))
    imgs = c.fetchall()

    c.execute("SELECT username, rating, comment FROM ratings WHERE spot_id=?", (id,))
    reviews = c.fetchall()

    c.execute("SELECT username, text FROM comments WHERE spot_id=?", (id,))
    comments = c.fetchall()

    c.execute("SELECT AVG(rating) FROM ratings WHERE spot_id=?", (id,))
    avg = c.fetchone()[0]

    conn.close()

    return render_template(
        "spot.html",
        s=s,
        imgs=imgs,
        reviews=reviews,
        comments=comments,
        avg=avg,
        user=session.get("user"),
        admin=ADMIN
    )

@app.route("/rate/<int:id>", methods=["POST"])
def rate(id):
    if "user" not in session:
        return redirect("/login")

    user = session["user"]
    rating = request.form["rating"]
    comment = request.form["comment"]

    conn = db()
    c = conn.cursor()

    c.execute("SELECT * FROM ratings WHERE spot_id=? AND username=?", (id,user))
    existing = c.fetchone()

    if existing:
        c.execute("UPDATE ratings SET rating=?, comment=? WHERE spot_id=? AND username=?",(rating, comment, id, user))
    else:
        c.execute("INSERT INTO ratings (spot_id,username,rating,comment) VALUES (?,?,?,?)",(id,user,rating,comment))

    conn.commit()
    conn.close()

    return redirect(f"/spot/{id}")

@app.route("/comment/<int:id>", methods=["POST"])
def comment(id):
    if "user" not in session:
        return redirect("/login")

    text = request.form["text"]
    user = session["user"]

    conn = db()
    c = conn.cursor()
    c.execute("INSERT INTO comments (spot_id,username,text) VALUES (?,?,?)",(id,user,text))
    conn.commit()
    conn.close()

    return redirect(f"/spot/{id}")

@app.route("/delete/<int:id>")
def delete(id):
    if "user" not in session:
        return redirect("/login")

    user = session["user"]

    conn = db()
    c = conn.cursor()

    c.execute("SELECT username FROM spots WHERE id=?", (id,))
    owner = c.fetchone()

    if owner and (owner[0] == user or user == ADMIN):
        c.execute("DELETE FROM spots WHERE id=?", (id,))
        c.execute("DELETE FROM images WHERE spot_id=?", (id,))
        c.execute("DELETE FROM ratings WHERE spot_id=?", (id,))
        c.execute("DELETE FROM comments WHERE spot_id=?", (id,))
        conn.commit()

    conn.close()
    return redirect("/")

# 🔥 BACKUP DOWNLOAD
@app.route("/backup")
def backup():
    return send_file("sitspots.db", as_attachment=True)

# 🔥 RESTORE UPLOAD
@app.route("/restore", methods=["POST"])
def restore():
    file = request.files["file"]
    file.save("sitspots.db")
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)