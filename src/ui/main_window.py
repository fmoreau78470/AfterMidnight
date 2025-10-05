# src/ui/main_window.py
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QListWidget, QListWidgetItem, QLineEdit, QMessageBox, QFileDialog, QInputDialog
)
from PyQt6.QtCore import Qt
import sqlite3
import os
import logging
import json
import datetime
from pathlib import Path
import sys
from astropy.io import fits

CONFIG_DIR = Path.home() / ".aftermidnight"
CONFIG_FILE = CONFIG_DIR / "config.json"

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("After Midnight")
        self.setGeometry(100, 100, 800, 600)

        # Configuration du logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

        # Base de données
        self.db_path = Path("db/aftermidnight.db")
        self.current_project_id = None

        # Initialiser l'UI
        self.init_ui()
        self.load_projects()
        self.load_last_project()

    def format_duration(self, seconds):
        """Convertir les secondes en format hh:mm:ss."""
        if seconds is None:
            return "inconnu"

        hours = int(seconds // 3600)
        remaining_seconds = seconds % 3600
        minutes = int(remaining_seconds // 60)
        seconds = int(remaining_seconds % 60)

        return f"{hours}h {minutes}m {seconds}s"

    def init_ui(self):
        # Layout principal
        main_widget = QWidget()
        main_layout = QHBoxLayout()

        # Panneau des projets (gauche)
        self.project_panel = QWidget()
        project_layout = QVBoxLayout()

        self.project_label = QLabel("Projets :")
        self.project_list = QListWidget()
        self.project_list.itemSelectionChanged.connect(self.on_project_selected)

        self.new_project_button = QPushButton("Nouveau Projet")
        self.new_project_button.clicked.connect(self.create_project)

        self.delete_project_button = QPushButton("Supprimer le Projet")
        self.delete_project_button.clicked.connect(self.delete_project)

        self.clear_db_button = QPushButton("Vider la Base de Données")
        self.clear_db_button.clicked.connect(self.clear_database)

        project_layout.addWidget(self.project_label)
        project_layout.addWidget(self.project_list)
        project_layout.addWidget(self.new_project_button)
        project_layout.addWidget(self.delete_project_button)
        project_layout.addWidget(self.clear_db_button)
        self.project_panel.setLayout(project_layout)

        # Panneau des sessions (centre)
        self.session_panel = QWidget()
        session_layout = QVBoxLayout()

        self.session_label = QLabel("Synthèse des prises de vue :")
        self.session_list = QListWidget()

        self.import_button = QPushButton("Importer des FITS")
        self.import_button.clicked.connect(self.import_fits)
        self.import_button.setEnabled(False)  # Désactiver le bouton par défaut

        session_layout.addWidget(self.session_label)
        session_layout.addWidget(self.session_list)
        session_layout.addWidget(self.import_button)
        self.session_panel.setLayout(session_layout)

        # Ajouter les panneaux au layout principal
        main_layout.addWidget(self.project_panel, stretch=1)
        main_layout.addWidget(self.session_panel, stretch=3)
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

    def on_project_selected(self):
        """Activer ou désactiver le bouton d'importation en fonction de la sélection d'un projet."""
        selected_items = self.project_list.selectedItems()
        self.import_button.setEnabled(len(selected_items) > 0)
        if selected_items:
            self.load_project_images()

    def save_last_project(self, project_id):
        """Sauvegarder le dernier projet utilisé."""
        CONFIG_DIR.mkdir(exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump({"last_project_id": project_id}, f)

    def load_last_project(self):
        """Charger le dernier projet utilisé."""
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                last_project_id = config.get("last_project_id")
                if last_project_id:
                    # Trouver l'item correspondant dans la liste
                    for i in range(self.project_list.count()):
                        item = self.project_list.item(i)
                        if item.data(Qt.ItemDataRole.UserRole) == last_project_id:
                            self.project_list.setCurrentItem(item)
                            self.on_project_selected()
                            break

    def load_projects(self):
        """Charger la liste des projets depuis la base de données."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name FROM projects")
            projects = cursor.fetchall()

            self.project_list.clear()
            for project_id, project_name in projects:
                item = QListWidgetItem(project_name)
                item.setData(Qt.ItemDataRole.UserRole, project_id)
                self.project_list.addItem(item)

        # Désactiver le bouton d'importation si aucun projet n'est sélectionné
        self.import_button.setEnabled(False)

    def create_project(self):
        """Créer un nouveau projet."""
        project_name, ok = QInputDialog.getText(self, "Nouveau Projet", "Nom du projet :")
        if ok and project_name:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                    INSERT INTO projects (name) VALUES (?)
                    """, (project_name,))
                    conn.commit()
                    self.load_projects()
            except sqlite3.IntegrityError:
                QMessageBox.warning(self, "Erreur", "Un projet avec ce nom existe déjà.")
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Une erreur est survenue : {e}")

    def load_project_images(self):
        """Charger et afficher la synthèse des prises de vue classées par soirée."""
        selected_items = self.project_list.selectedItems()
        if selected_items:
            selected_item = selected_items[0]
            self.current_project_id = selected_item.data(Qt.ItemDataRole.UserRole)
            self.save_last_project(self.current_project_id)

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Requête pour obtenir les sessions par soirée
                cursor.execute("""
                SELECT
                    strftime('%Y-%m-%d', date(date_obs, '-12 hours')) as session_date,
                    filter,
                    COUNT(*) as count,
                    SUM(exposure) as total_exposure
                FROM images
                WHERE project_id = ?
                GROUP BY session_date, filter
                ORDER BY session_date, filter
                """, (self.current_project_id,))
                sessions = cursor.fetchall()

                # Requête pour obtenir la durée totale par filtre pour tout le projet
                cursor.execute("""
                SELECT
                    filter,
                    SUM(exposure) as total_exposure
                FROM images
                WHERE project_id = ?
                GROUP BY filter
                ORDER BY filter
                """, (self.current_project_id,))
                total_by_filter = cursor.fetchall()

                # Effacer l'ancienne synthèse
                self.session_list.clear()

                # Afficher la synthèse par soirée
                current_date = None
                for session_date, filter_, count, total_exposure in sessions:
                    if session_date:
                        try:
                            if session_date != current_date:
                                current_date = session_date
                                self.session_list.addItem(f"--- Soirée du {session_date} ---")

                            if total_exposure is not None:
                                self.session_list.addItem(f"{filter_} : {count} images, {self.format_duration(total_exposure)} d'exposition")
                            else:
                                self.session_list.addItem(f"{filter_} : {count} images (durée d'exposition inconnue)")
                        except Exception as e:
                            logging.error(f"Erreur de conversion de date : {e}")
                            self.session_list.addItem(f"{filter_} : {count} images (erreur de conversion)")
                    else:
                        self.session_list.addItem(f"{filter_} : {count} images (date inconnue)")

                # Ajouter une séparation
                self.session_list.addItem("")

                # Afficher la synthèse totale par filtre
                self.session_list.addItem("--- Totaux par filtre pour tout le projet ---")
                for filter_, total_exposure in total_by_filter:
                    if total_exposure is not None:
                        self.session_list.addItem(f"{filter_} : {self.format_duration(total_exposure)} d'exposition")
                    else:
                        self.session_list.addItem(f"{filter_} : durée d'exposition inconnue")

    def delete_project(self):
        """Supprimer le projet sélectionné."""
        selected_items = self.project_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Erreur", "Veuillez sélectionner un projet à supprimer.")
            return

        selected_item = selected_items[0]
        project_id = selected_item.data(Qt.ItemDataRole.UserRole)
        project_name = selected_item.text()

        confirm = QMessageBox.question(
            self,
            "Supprimer le Projet",
            f"Voulez-vous vraiment supprimer le projet '{project_name}' ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if confirm == QMessageBox.StandardButton.Yes:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    # Supprimer les images associées au projet
                    cursor.execute("DELETE FROM images WHERE project_id = ?", (project_id,))
                    # Supprimer le projet
                    cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
                    conn.commit()
                    self.load_projects()
                    self.session_list.clear()
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Une erreur est survenue : {e}")

    def clear_database(self):
        """Vider la base de données avec une double validation."""
        # Première confirmation
        confirm1 = QMessageBox.question(
            self,
            "Vider la Base de Données",
            "Êtes-vous sûr de vouloir vider toute la base de données ? Cette action est irréversible.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if confirm1 == QMessageBox.StandardButton.Yes:
            # Deuxième confirmation
            confirm2 = QMessageBox.question(
                self,
                "Vider la Base de Données - Confirmation Finale",
                "Cette action supprimera tous les projets et toutes les images. Voulez-vous vraiment continuer ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if confirm2 == QMessageBox.StandardButton.Yes:
                try:
                    with sqlite3.connect(self.db_path) as conn:
                        cursor = conn.cursor()
                        # Supprimer toutes les images
                        cursor.execute("DELETE FROM images")
                        # Supprimer tous les projets
                        cursor.execute("DELETE FROM projects")
                        conn.commit()
                    self.load_projects()
                    self.session_list.clear()
                    QMessageBox.information(self, "Succès", "La base de données a été vidée avec succès.")
                except Exception as e:
                    QMessageBox.critical(self, "Erreur", f"Une erreur est survenue : {e}")

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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

