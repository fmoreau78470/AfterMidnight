# db/update_db.py
import sqlite3
from pathlib import Path

DB_PATH = Path("db/aftermidnight.db")

def update_database():
    try:
        # Connexion à la base de données
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Vérifier si la colonne IMAGETYP existe déjà dans la table 'images'
        cursor.execute("PRAGMA table_info(images)")
        columns = [column[1] for column in cursor.fetchall()]

        if "IMAGETYP" not in columns:
            # Ajouter la colonne IMAGETYP avec une contrainte CHECK
            cursor.execute("""
                ALTER TABLE images
                ADD COLUMN IMAGETYP TEXT
                DEFAULT 'LIGHT'
                CHECK(IMAGETYP IN ('LIGHT', 'FLAT', 'DARK', 'BIAS'))
            """)
            print("Colonne 'IMAGETYP' ajoutée avec succès à la table 'images'.")
        else:
            print("La colonne 'IMAGETYP' existe déjà dans la table 'images'.")

        # Valider les modifications
        conn.commit()

    except sqlite3.Error as e:
        print(f"Erreur lors de la mise à jour de la base de données : {e}")
    finally:
        # Fermer la connexion
        if conn:
            conn.close()

if __name__ == "__main__":
    update_database()