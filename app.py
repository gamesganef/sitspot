from flask import Flask, render_template, request, redirect, session
import sqlite3
import os
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image
import math

app = Flask(__name__)
app.secret_key = "secret123"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_FOLDER = os.path.join(BASE_DIR, "static/uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def get_db():
    return sqlite3.connect(os.path.join(BASE_DIR, "database.db"))


# 🔥 DISTANCE FUNCTION
def calc_distance(lat1, lon1, lat2, lon2):
    R = 6371
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)

    a = (math.sin(dLat/2)**2 +
         math.cos(math.radians(lat1)) *
         math.cos(math.radians(lat2)) *
         math.sin(dLon/2)**2)

    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1-a)))


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

    user_lat = request.args.get("lat", type=float)
    user_lng = request.args.get("lng", type=float)

    spots_with_distance = []

    for s in spots:
        s_list = list(s)

        dist = None
        if user_lat and user_lng:
            try:
                dist = calc_distance(user_lat, user_lng, float(s[4]), float(s[5]))
            except:
                dist = None

        spots_with_distance.append({
            "data": s_list,
            "distance": dist
        })

    if user_lat and user_lng:
        spots_with_distance.sort(key=lambda x: x["distance"] if x["distance"] is not None else 999999)

    ratings_data = c.execute("""
        SELECT spot_id, AVG(rating), COUNT(*)
        FROM ratings
        GROUP BY spot_id
    """).fetchall()

    ratings = {r[0]: {"avg": r[1], "count": r[2]} for r in ratings_data}

    favorites = []
    if "user" in session:
        favs = c.execute(
            "SELECT spot_id FROM favorites WHERE username=?",
            (session["user"],)
        ).fetchall()
        favorites = [f[0] for f in favs]

    images_data = c.execute("SELECT spot_id, filename FROM images").fetchall()
    images = {}
    for sid, filename in images_data:
        if sid not in images:
            images[sid] = filename

    db.close()

    return render_template(
        "index.html",
        spots=spots_with_distance,
        ratings=ratings,
        images=images,
        search=search,
        favorites=favorites,
        user=session.get("user"),
        user_lat=user_lat,
        user_lng=user_lng
    )


# 🔐 REGISTER
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        db = get_db()
        c = db.cursor()

        existing = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if existing:
            db.close()
            return "Email bestaat al"

        hashed = generate_password_hash(password)

        c.execute(
            "INSERT INTO users (email, password) VALUES (?, ?)",
            (email, hashed)
        )
        db.commit()
        db.close()

        return redirect("/login")

    return render_template("register.html")


# 🔐 LOGIN
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        db = get_db()
        c = db.cursor()

        user = c.execute(
            "SELECT * FROM users WHERE email=?",
            (email,)
        ).fetchone()

        db.close()

        if user and check_password_hash(user[2], password):
            session["user"] = user[1]
            return redirect("/")
        else:
            return "Login fout"

    return render_template("login.html")


# 🔐 LOGOUT
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


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

    db.close()

    return render_template("favorites.html", spots=spots)


# ❤️ ADD FAVORITE
@app.route("/favorite/<int:id>")
def favorite(id):
    if "user" not in session:
        return redirect("/login")

    db = get_db()
    c = db.cursor()

    c.execute("""
        INSERT OR IGNORE INTO favorites (username, spot_id)
        VALUES (?, ?)
    """, (session["user"], id))

    db.commit()
    db.close()

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
    db.close()

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
    db.close()

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
    db.close()

    return redirect(f"/spot/{id}")


# ⭐ RATE
@app.route("/rate/<int:id>", methods=["POST"])
def rate(id):
    if "user" not in session:
        return redirect("/login")

    rating = int(request.form["rating"])
    comment = request.form["comment"]

    db = get_db()
    c = db.cursor()

    c.execute("""
        INSERT INTO ratings (spot_id, username, rating, comment)
        VALUES (?, ?, ?, ?)
    """, (id, session["user"], rating, comment))

    db.commit()
    db.close()

    return redirect(f"/spot/{id}")


# 🔥 DELETE
@app.route("/delete/<int:id>", methods=["POST"])
def delete(id):
    if "user" not in session:
        return redirect("/login")

    db = get_db()
    c = db.cursor()

    spot = c.execute("SELECT username FROM spots WHERE id=?", (id,)).fetchone()

    if not spot:
        db.close()
        return redirect("/")

    if spot[0] != session["user"]:
        db.close()
        return "Niet toegestaan"

    images = c.execute(
        "SELECT filename FROM images WHERE spot_id=?",
        (id,)
    ).fetchall()

    for img in images:
        filepath = os.path.join(UPLOAD_FOLDER, img[0])
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except:
                pass

    c.execute("DELETE FROM ratings WHERE spot_id=?", (id,))
    c.execute("DELETE FROM images WHERE spot_id=?", (id,))
    c.execute("DELETE FROM favorites WHERE spot_id=?", (id,))
    c.execute("DELETE FROM spots WHERE id=?", (id,))
    db.commit()
    db.close()

    return redirect("/")


# 🔥 ADD (FIXED stability)
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
                try:
                    filename = f"{spot_id}_{i}.jpg"
                    filepath = os.path.join(UPLOAD_FOLDER, filename)

                    img = Image.open(file)

                    if img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")

                    img.thumbnail((1280, 1280))
                    img.save(filepath, "JPEG", quality=40, optimize=True)

                    c.execute(
                        "INSERT INTO images (spot_id, filename) VALUES (?, ?)",
                        (spot_id, filename)
                    )
                except Exception as e:
                    print("IMAGE ERROR:", e)

        db.commit()
        db.close()

        return redirect("/")

    return render_template("add.html")


# 🔥 SPOT DETAIL
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

    db.close()

    ratings = [r[1] for r in reviews]
    avg = sum(ratings) / len(ratings) if ratings else None

    remaining = None
    if s[8]:
        try:
            remaining = int((datetime.fromisoformat(s[8]) - datetime.now()).total_seconds())
        except:
            remaining = None

    return render_template(
        "spot.html",
        s=s,
        reviews=reviews,
        imgs=imgs,
        avg=avg,
        user=session.get("user"),
        remaining=remaining
    )


if __name__ == "__main__":
    app.run(debug=True)