# db/update_db.py
import sqlite3
from pathlib import Path

DB_PATH = Path("db/aftermidnight.db")

def update_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        # Ajouter la colonne parent_id à la table projects si elle n'existe pas
        cursor.execute("PRAGMA table_info(projects)")
        columns = [column[1] for column in cursor.fetchall()]

        if "parent_id" not in columns:
            cursor.execute("ALTER TABLE projects ADD COLUMN parent_id INTEGER")
            cursor.execute("UPDATE projects SET parent_id = NULL WHERE parent_id IS NULL")

        conn.commit()
    print(f"Base de données mise à jour : {DB_PATH}")

if __name__ == "__main__":
    update_db()
