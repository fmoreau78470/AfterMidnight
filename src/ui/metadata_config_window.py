# src/ui/metadata_config_window.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QLineEdit, QMessageBox, QFileDialog, QInputDialog, QWidget
)
from PyQt6.QtCore import Qt
import sqlite3
from pathlib import Path
from astropy.io import fits

class MetadataConfigWindow(QDialog):
    def __init__(self, parent=None, db_path=None):
        super().__init__(parent)
        self.setWindowTitle("Configuration des Métadonnées")
        self.setGeometry(200, 200, 800, 500)

        self.db_path = db_path
        self.fits_keywords = []
        self.protected_keywords = {"date_obs", "exposure", "ra", "dec", "filter", "imagetyp"}
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout()

        # Panneau gauche pour les mots-clés FITS
        self.left_panel = QWidget()
        left_layout = QVBoxLayout()

        self.load_fits_button = QPushButton("Lire un fichier FITS")
        self.load_fits_button.clicked.connect(self.load_fits_keywords)
        left_layout.addWidget(self.load_fits_button)

        self.fits_keywords_label = QLabel("Mots-clés FITS :")
        left_layout.addWidget(self.fits_keywords_label)

        self.fits_keywords_list = QListWidget()
        left_layout.addWidget(self.fits_keywords_list)

        self.left_panel.setLayout(left_layout)
        layout.addWidget(self.left_panel, stretch=1)

        # Panneau central pour les boutons d'action
        self.center_panel = QWidget()
        center_layout = QVBoxLayout()

        self.add_button = QPushButton(">>")
        self.add_button.clicked.connect(self.add_keyword)
        center_layout.addWidget(self.add_button)

        self.remove_button = QPushButton("<<")
        self.remove_button.clicked.connect(self.remove_keyword)
        center_layout.addWidget(self.remove_button)

        self.center_panel.setLayout(center_layout)
        layout.addWidget(self.center_panel)

        # Panneau droit pour les mots-clés utilisés
        self.right_panel = QWidget()
        right_layout = QVBoxLayout()

        self.used_keywords_label = QLabel("Mots-clés utilisés :")
        right_layout.addWidget(self.used_keywords_label)

        self.used_keywords_list = QListWidget()
        self.used_keywords_list.itemDoubleClicked.connect(self.edit_keyword)
        right_layout.addWidget(self.used_keywords_list)

        self.right_panel.setLayout(right_layout)
        layout.addWidget(self.right_panel, stretch=1)

        # Boutons de validation et d'annulation
        button_layout = QHBoxLayout()

        self.save_button = QPushButton("Sauvegarder")
        self.save_button.clicked.connect(self.save_config)
        button_layout.addWidget(self.save_button)

        self.cancel_button = QPushButton("Annuler")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)
        self.setLayout(layout)

        # Charger la configuration actuelle
        self.load_config()

    def load_fits_keywords(self):
        """Lire un fichier FITS et extraire ses mots-clés."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Sélectionner un fichier FITS", "", "FITS Files (*.fits *.fit)")
        if file_path:
            try:
                with fits.open(file_path) as hdul:
                    header = hdul[0].header
                    self.fits_keywords = list(header.keys())
                    self.fits_keywords_list.clear()
                    self.fits_keywords_list.addItems(self.fits_keywords)
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Erreur lors de la lecture du fichier FITS : {e}")

    def load_config(self):
        """Charger la configuration actuelle depuis la base de données."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT fits_keyword, db_name FROM metadata_config")
            config = cursor.fetchall()

            self.used_keywords_list.clear()
            for fits_keyword, db_name in config:
                item = QListWidgetItem(f"{fits_keyword} -> {db_name}")
                item.setData(Qt.ItemDataRole.UserRole, (fits_keyword, db_name))
                self.used_keywords_list.addItem(item)

    def add_keyword(self):
        """Ajouter un mot-clé sélectionné à la liste des mots-clés utilisés."""
        selected_items = self.fits_keywords_list.selectedItems()
        if selected_items:
            fits_keyword = selected_items[0].text()
            db_name, ok = QInputDialog.getText(self, "Nom dans la base de données", f"Nom pour {fits_keyword} :")
            if ok and db_name:
                item = QListWidgetItem(f"{fits_keyword} -> {db_name}")
                item.setData(Qt.ItemDataRole.UserRole, (fits_keyword, db_name))
                self.used_keywords_list.addItem(item)

    def remove_keyword(self):
        """Retirer un mot-clé sélectionné de la liste des mots-clés utilisés."""
        selected_items = self.used_keywords_list.selectedItems()
        if selected_items:
            item = selected_items[0]
            fits_keyword, db_name = item.data(Qt.ItemDataRole.UserRole)
            if db_name in self.protected_keywords:
                QMessageBox.warning(self, "Erreur", f"Le mot-clé '{db_name}' est protégé et ne peut pas être supprimé.")
            else:
                self.used_keywords_list.takeItem(self.used_keywords_list.row(item))

    def edit_keyword(self, item):
        """Modifier le nom d'un mot-clé sélectionné dans la liste des mots-clés utilisés."""
        fits_keyword, db_name = item.data(Qt.ItemDataRole.UserRole)

        if db_name in self.protected_keywords:
            QMessageBox.warning(self, "Erreur", f"Le mot-clé '{db_name}' est protégé et ne peut pas être modifié.")
            return

        new_db_name, ok = QInputDialog.getText(self, "Modifier le nom dans la base de données", f"Nouveau nom pour {fits_keyword} :", text=db_name)
        if ok and new_db_name:
            item.setText(f"{fits_keyword} -> {new_db_name}")
            item.setData(Qt.ItemDataRole.UserRole, (fits_keyword, new_db_name))

    def save_config(self):
        """Sauvegarder la configuration des métadonnées dans la base de données."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Supprimer la configuration actuelle
            cursor.execute("DELETE FROM metadata_config")

            # Ajouter la nouvelle configuration
            for i in range(self.used_keywords_list.count()):
                item = self.used_keywords_list.item(i)
                fits_keyword, db_name = item.data(Qt.ItemDataRole.UserRole)
                cursor.execute("INSERT INTO metadata_config (fits_keyword, db_name) VALUES (?, ?)", (fits_keyword, db_name))

            conn.commit()
            self.accept()
