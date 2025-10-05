# db/update_db.py
import sqlite3
from pathlib import Path

DB_PATH = Path("db/aftermidnight.db")

def update_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        # Vérifier si les colonnes existent
        cursor.execute("PRAGMA table_info(images)")
        columns = [column[1] for column in cursor.fetchall()]

        if "ra" not in columns:
            cursor.execute("ALTER TABLE images ADD COLUMN ra REAL")
        if "dec" not in columns:
            cursor.execute("ALTER TABLE images ADD COLUMN dec REAL")
        if "date_obs" not in columns:
            cursor.execute("ALTER TABLE images ADD COLUMN date_obs TEXT")
        if "exposure" not in columns:
            cursor.execute("ALTER TABLE images ADD COLUMN exposure REAL")
        if "filter" not in columns:
            cursor.execute("ALTER TABLE images ADD COLUMN filter TEXT")

        conn.commit()
    print(f"Base de données mise à jour : {DB_PATH}")

if __name__ == "__main__":
    update_db()
