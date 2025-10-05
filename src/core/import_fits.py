# src/core/import_fits.py
import os
import sqlite3
import logging
from pathlib import Path
from astropy.io import fits

# Configuration
DB_PATH = Path("db/aftermidnight.db")
FITS_DIR = Path("/Users/francis/Astro/Traitements/vdB 5/LIGHT/2025-09-29")  # À personnaliser

# Configuration des logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def extract_fits_metadata(self, fits_file):
    """Extraire les métadonnées d'un fichier FITS."""
    metadata = {
        "ra": None,
        "dec": None,
        "date_obs": None,
        "exposure": None,
        "filter": None
    }

    try:
        with fits.open(fits_file) as hdul:
            header = hdul[0].header

            # Extraire RA (Ascension Droite)
            metadata["ra"] = header.get("RA", None)

            # Extraire DEC (Déclinaison)
            metadata["dec"] = header.get("DEC", None)

            # Extraire DATE-LOC (Date d'observation)
            date_loc = header.get("DATE-LOC", None)
            if date_loc:
                date_loc_clean = date_loc.strip()
                # Tronquer les fractions de seconde à 6 chiffres
                if '.' in date_loc_clean:
                    date_part, fractional_part = date_loc_clean.split('.')
                    fractional_part = fractional_part[:6]  # Tronquer à 6 chiffres
                    date_loc_clean = f"{date_part}.{fractional_part}"
                metadata["date_obs"] = date_loc_clean

            # Extraire EXPOSURE (Temps d'exposition)
            exposure = header.get("EXPOSURE", None)
            if exposure is not None:
                try:
                    metadata["exposure"] = float(exposure)
                except ValueError:
                    metadata["exposure"] = None

            # Extraire FILTER (Filtre utilisé)
            metadata["filter"] = header.get("FILTER", None)

    except Exception as e:
        logging.error(f"Erreur lors de l'extraction des métadonnées : {e}")

    return metadata

def import_fits(self):
    """Importer des fichiers FITS depuis une arborescence de répertoires."""
    if self.current_project_id is None:
        QMessageBox.warning(self, "Erreur", "Veuillez sélectionner un projet.")
        return

    # Ouvrir une boîte de dialogue pour sélectionner un répertoire
    dir_path = QFileDialog.getExistingDirectory(self, "Sélectionner un répertoire contenant des FITS")
    if dir_path:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Parcourir récursivement le répertoire
            for root, dirs, files in os.walk(dir_path):
                for file in files:
                    if file.lower().endswith('.fits'):
                        file_path = os.path.join(root, file)
                        filename = os.path.basename(file_path)

                        # Extraire les métadonnées du fichier FITS
                        metadata = self.extract_fits_metadata(file_path)

                        # Vérifier si le fichier existe déjà dans la base de données
                        cursor.execute("""
                        SELECT 1 FROM images WHERE filename = ? AND project_id = ?
                        """, (filename, self.current_project_id))
                        if cursor.fetchone() is None:
                            cursor.execute("""
                            INSERT INTO images (filename, path, project_id, ra, dec, date_obs, exposure, filter)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                filename,
                                file_path,
                                self.current_project_id,
                                metadata["ra"],
                                metadata["dec"],
                                metadata["date_obs"],
                                metadata["exposure"],
                                metadata["filter"]
                            ))
                            logging.info(f"Fichier importé : {file_path}")
            conn.commit()
            self.load_project_images()
            QMessageBox.information(self, "Succès", f"Importation terminée. {cursor.rowcount} nouveaux fichiers ajoutés.")

if __name__ == "__main__":
    import_fits_to_db()
