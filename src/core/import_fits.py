import sqlite3
from astropy.io import fits
from pathlib import Path

# Chemin mis à jour vers la base de données
DB_PATH = Path(__file__).parent / "db" / "aftermidnight.db"

def import_fits(file_path, project_id):
    """
    Importe un fichier FITS dans la base de données.

    Args:
        file_path (str): Chemin vers le fichier FITS.
        project_id (int): Identifiant du projet associé.

    Returns:
        bool: True si l'import a réussi, False sinon.
    """
    try:
        # Lire les métadonnées du fichier FITS
        with fits.open(file_path) as hdul:
            header = hdul[0].header

            # Extraire les métadonnées
            date_obs = header.get('DATE-OBS', '')
            exposure = header.get('EXPOSURE', 0.0)
            ra = header.get('RA', 0.0)
            dec = header.get('DEC', 0.0)
            filter = header.get('FILTER', '')
            imagetyp = header.get('IMAGETYP', 'LIGHT')  # Valeur par défaut : 'LIGHT'

            # Valider que IMAGETYP est une valeur autorisée
            valid_imagetyp = {'LIGHT', 'FLAT', 'DARK', 'BIAS'}
            if imagetyp not in valid_imagetyp:
                print(f"Avertissement : Valeur invalide pour IMAGETYP ({imagetyp}). Utilisation de 'LIGHT' par défaut.")
                imagetyp = 'LIGHT'

            # Connexion à la base de données
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            # Insérer les métadonnées dans la table 'images'
            cursor.execute("""
                INSERT INTO images
                (project_id, file_path, date_obs, exposure, ra, dec, filter, imagetyp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (project_id, file_path, date_obs, exposure, ra, dec, filter, imagetyp))

            # Valider la transaction
            conn.commit()
            print(f"Fichier {file_path} importé avec succès.")
            return True

    except fits.header.HeaderMissingKeyError as e:
        print(f"Erreur lors de la lecture du fichier FITS : {e}")
        return False

    except sqlite3.Error as e:
        print(f"Erreur lors de l'insertion dans la base de données : {e}")
        return False

    finally:
        # Fermer la connexion à la base de données
        if 'conn' in locals():
            conn.close()

# Exemple d'utilisation
if __name__ == "__main__":
    import_fits("/chemin/vers/votre_fichier.fits", project_id=1)
