from flask import Flask, render_template, request, redirect, session
import sqlite3
import os
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from PIL import Image

app = Flask(__name__)
app.secret_key = "secret123"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_FOLDER = os.path.join(BASE_DIR, "static/uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def get_db():
    return sqlite3.connect(os.path.join(BASE_DIR, "database.db"))


# 🔥 HOME
@app.route("/")
def index():
    db = get_db()
    c = db.cursor()

    now = datetime.now()

    c.execute("""
        UPDATE spots
        SET occupied_by=NULL, occupied_until=NULL
        WHERE occupied_until IS NOT NULL AND occupied_until < ?
    """, (now,))

    c.execute("""
        UPDATE spots
        SET occupied_by=NULL
        WHERE occupied_by='' OR occupied_by='None'
    """)

    db.commit()

    search = request.args.get("search")

    if search:
        spots = c.execute("""
            SELECT * FROM spots
            WHERE name LIKE ? OR location LIKE ? OR description LIKE ?
        """, (f"%{search}%", f"%{search}%", f"%{search}%")).fetchall()
    else:
        spots = c.execute("SELECT * FROM spots").fetchall()

    reviews = c.execute("SELECT spot_id, rating FROM ratings").fetchall()

    favorites = []
    if "user" in session:
        try:
            favs = c.execute(
                "SELECT spot_id FROM favorites WHERE username=?",
                (session["user"],)
            ).fetchall()
            favorites = [f[0] for f in favs]
        except:
            favorites = []

    images = {}
    for s in spots:
        img = c.execute(
            "SELECT filename FROM images WHERE spot_id=? LIMIT 1",
            (s[0],)
        ).fetchone()
        images[s[0]] = img[0] if img else None

    return render_template(
        "index.html",
        spots=spots,
        reviews=reviews,
        images=images,
        search=search,
        favorites=favorites
    )


# ❤️ FAVORITES PAGE
@app.route("/favorites")
def favorites_page():
    if "user" not in session:
        return redirect("/login")

    db = get_db()
    c = db.cursor()

    spots = c.execute("""
        SELECT s.* FROM spots s
        JOIN favorites f ON s.id = f.spot_id
        WHERE f.username=?
    """, (session["user"],)).fetchall()

    return render_template("favorites.html", spots=spots)


# ❤️ ADD FAVORITE
@app.route("/favorite/<int:id>")
def favorite(id):
    if "user" not in session:
        return redirect("/login")

    db = get_db()
    c = db.cursor()

    try:
        c.execute(
            "INSERT INTO favorites (username, spot_id) VALUES (?, ?)",
            (session["user"], id)
        )
        db.commit()
    except Exception as e:
        print("FAVORITE ERROR:", e)

    return redirect("/")


# 💔 REMOVE FAVORITE
@app.route("/unfavorite/<int:id>")
def unfavorite(id):
    if "user" not in session:
        return redirect("/login")

    db = get_db()
    c = db.cursor()

    c.execute(
        "DELETE FROM favorites WHERE username=? AND spot_id=?",
        (session["user"], id)
    )
    db.commit()

    return redirect("/")


# 🔥 OCCUPY
@app.route("/occupy/<int:id>", methods=["POST"])
def occupy(id):
    if "user" not in session:
        return redirect("/login")

    db = get_db()
    c = db.cursor()

    until = datetime.now() + timedelta(hours=2)

    c.execute("""
        UPDATE spots
        SET occupied_by=?, occupied_until=?
        WHERE id=?
    """, (session["user"], until, id))

    db.commit()
    return redirect(f"/spot/{id}")


# 🔥 LEAVE
@app.route("/leave/<int:id>", methods=["POST"])
def leave(id):
    if "user" not in session:
        return redirect("/login")

    db = get_db()
    c = db.cursor()

    c.execute("""
        UPDATE spots
        SET occupied_by=NULL, occupied_until=NULL
        WHERE id=?
    """, (id,))

    db.commit()
    return redirect(f"/spot/{id}")


# 🔥 DELETE SPOT
@app.route("/delete/<int:id>", methods=["POST"])
def delete(id):
    if "user" not in session:
        return redirect("/login")

    db = get_db()
    c = db.cursor()

    spot = c.execute("SELECT username FROM spots WHERE id=?", (id,)).fetchone()

    if not spot:
        return redirect("/")

    if spot[0] != session["user"]:
        return "Niet toegestaan"

    try:
        c.execute("DELETE FROM ratings WHERE spot_id=?", (id,))
        c.execute("DELETE FROM images WHERE spot_id=?", (id,))
        c.execute("DELETE FROM favorites WHERE spot_id=?", (id,))
        c.execute("DELETE FROM spots WHERE id=?", (id,))
        db.commit()
    except Exception as e:
        print("DELETE ERROR:", e)

    return redirect("/")


# REGISTER
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        db = get_db()
        c = db.cursor()

        existing = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if existing:
            return "Email bestaat al"

        c.execute(
            "INSERT INTO users (email, password) VALUES (?, ?)",
            (email, password)
        )
        db.commit()

        return redirect("/login")

    return render_template("register.html")


# LOGIN
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        db = get_db()
        c = db.cursor()

        user = c.execute(
            "SELECT * FROM users WHERE email=? AND password=?",
            (email, password)
        ).fetchone()

        if user:
            session["user"] = user[1]
            return redirect("/")
        else:
            return "Login fout"

    return render_template("login.html")


# LOGOUT
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# 🔥 ADD SPOT (FIXED MET COMPRESSIE)
@app.route("/add", methods=["GET", "POST"])
def add():
    if "user" not in session:
        return redirect("/login")

    if request.method == "POST":
        name = request.form["name"]
        location = request.form["location"]
        description = request.form["description"]
        lat = request.form["lat"]
        lng = request.form["lng"]

        db = get_db()
        c = db.cursor()

        c.execute("""
            INSERT INTO spots (
                name, location, description, lat, lng, username,
                occupied_by, occupied_until
            )
            VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)
        """, (name, location, description, lat, lng, session["user"]))

        spot_id = c.lastrowid

        files = request.files.getlist("images")

        for i, file in enumerate(files):
            if file and file.filename != "":
                filename = f"{spot_id}_{i}.jpg"
                filepath = os.path.join(UPLOAD_FOLDER, filename)

                print("🔥 COMPRESSIE ACTIEF:", filename)

                img = Image.open(file)

                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")

                img.thumbnail((1280, 1280))
                img.save(filepath, "JPEG", quality=40, optimize=True)

                c.execute(
                    "INSERT INTO images (spot_id, filename) VALUES (?, ?)",
                    (spot_id, filename)
                )

        db.commit()
        return redirect("/")

    return render_template("add.html")


# SPOT DETAIL
@app.route("/spot/<int:id>")
def spot(id):
    db = get_db()
    c = db.cursor()

    s = c.execute("SELECT * FROM spots WHERE id=?", (id,)).fetchone()

    reviews = c.execute("""
        SELECT username, rating, comment
        FROM ratings
        WHERE spot_id=?
    """, (id,)).fetchall()

    imgs = c.execute(
        "SELECT filename FROM images WHERE spot_id=?",
        (id,)
    ).fetchall()

    ratings = [r[1] for r in reviews]
    avg = sum(ratings) / len(ratings) if ratings else None

    return render_template(
        "spot.html",
        s=s,
        reviews=reviews,
        imgs=imgs,
        avg=avg,
        user=session.get("user")
    )


if __name__ == "__main__":
    app.run(debug=True)