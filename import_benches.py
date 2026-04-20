import requests
import sqlite3
import os
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")

# 📍 Alleen jouw regio
areas = [
    (53.18, 6.50, 53.24, 6.62),  # Groningen
    (52.98, 6.50, 53.05, 6.62),  # Assen
]

# 🔁 fallback servers
URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter"
]

headers = {
    "User-Agent": "SitSpotApp/1.0"
}

# 🔥 betere straatnaam functie
def get_street(lat, lon):
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}"
        res = requests.get(url, headers=headers, timeout=10)
        data = res.json()

        addr = data.get("address", {})

        road = addr.get("road") or addr.get("pedestrian") or addr.get("footway")
        city = addr.get("city") or addr.get("town") or addr.get("village")

        if road and city:
            return f"{road}, {city}"
        elif road:
            return road
        elif city:
            return city
        else:
            return "Onbekend"

    except:
        return "Onbekend"


db = sqlite3.connect(DB_PATH)
c = db.cursor()

total_added = 0

for area in areas:
    print(f"\n📍 Area: {area}")

    query = f"""
    [out:json];
    node["amenity"="bench"]({area[0]},{area[1]},{area[2]},{area[3]});
    out;
    """

    data = None

    # 🔁 probeer meerdere servers
    for url in URLS:
        try:
            print(f"🌐 {url}")

            res = requests.post(url, data=query, headers=headers, timeout=30)

            if res.status_code != 200:
                print("❌ status:", res.status_code)
                continue

            data = res.json()
            print("✅ success")
            break

        except Exception as e:
            print("⚠️ fout:", e)
            continue

    if not data:
        print("❌ skip area")
        continue

    added = 0

    for el in data.get("elements", []):
        lat = el.get("lat")
        lon = el.get("lon")

        if not lat or not lon:
            continue

        # 🔍 duplicate check
        existing = c.execute(
            "SELECT id FROM spots WHERE lat=? AND lng=?",
            (lat, lon)
        ).fetchone()

        if existing:
            continue

        # 🧠 straat ophalen
        street = get_street(lat, lon)

        name = f"🪑 Bankje – {street}"

        c.execute("""
            INSERT INTO spots (
                name, location, description, lat, lng, username,
                occupied_by, occupied_until
            )
            VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)
        """, (
            name,
            street,  # 🔥 belangrijk → search werkt nu
            "Bankje in jouw regio",
            lat,
            lon,
            "system"
        ))

        added += 1
        total_added += 1

        print(f"➕ {name}")

        time.sleep(1)  # 🔥 rate limit (belangrijk)

    print(f"✔ toegevoegd in area: {added}")

db.commit()
db.close()

print(f"\n🔥 TOTAAL TOEGEVOEGD: {total_added}")