import json
import os
import sqlite3
import time
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")

headers = {"User-Agent": "SitSpotApp/1.0 (contact: sitspot@gmail.com)"}

BATCH_SIZE = 100
SLEEP_TIME = 1


def get_street(lat, lon):
    try:
        # ✅ JUISTE API
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}"
        res = requests.get(url, headers=headers, timeout=10)

        if res.status_code != 200:
            return "Onbekende locatie"

        data = res.json()
        addr = data.get("address", {})

        road = (
            addr.get("road")
            or addr.get("pedestrian")
            or addr.get("footway")
            or addr.get("cycleway")
            or addr.get("path")
        )

        area = (
            addr.get("neighbourhood")
            or addr.get("suburb")
            or addr.get("city_district")
            or addr.get("village")
            or addr.get("town")
            or addr.get("city")
        )

        # 🌳 natuur / park
        if addr.get("park") or addr.get("leisure") == "park":
            return f"Park {area}" if area else "Park"

        if addr.get("nature_reserve") or addr.get("natural"):
            return f"Natuurgebied {area}" if area else "Natuurgebied"

        if addr.get("landuse") == "forest":
            return f"Bosgebied {area}" if area else "Bosgebied"

        # normaal
        if road and area:
            return f"{road}, {area}"
        if area:
            return area
        if road:
            return road

        # fallback
        display_name = data.get("display_name")
        if display_name:
            return display_name.split(",")[0]

        return "Onbekende locatie"

    except Exception as e:
        print("API fout:", e)
        return "Onbekende locatie"


db = sqlite3.connect(DB_PATH)
c = db.cursor()

total_updated = 0

print("🚀 Script gestart: Willekeurige bankjes worden gezocht...")

try:
    while True:
        rows = c.execute(
            """
            SELECT id, lat, lng
            FROM spots
            WHERE name='🪑 Bankje'
            AND lat BETWEEN 50.75 AND 53.7
            AND lng BETWEEN 3.35 AND 7.22
            ORDER BY RANDOM()
            LIMIT ?
        """,
            (BATCH_SIZE,),
        ).fetchall()

        if not rows:
            print("\n🔥 KLAAR! Geen onbewerkte bankjes meer gevonden in NL.")
            break

        print(f"\n🔄 Batch gestart (Aantal: {len(rows)})")

        updated = 0

        for spot_id, lat, lng in rows:
            street = get_street(lat, lng)

            name = f"🪑 Bankje – {street}"

            c.execute(
                """
                UPDATE spots
                SET name=?, location=?
                WHERE id=?
            """,
                (name, street, spot_id),
            )

            updated += 1
            total_updated += 1

            print(f"✔ {name}")

            time.sleep(SLEEP_TIME)

        db.commit()

        print(f"✔ Batch klaar: {updated}")
        print(f"🔥 Totaal: {total_updated}")

        time.sleep(2)

except KeyboardInterrupt:
    print("\n🛑 Gestopt")

finally:
    db.commit()
    db.close()
    print("🔒 Database gesloten")