# src/ui/main_window.py
"""
Module principal de l'application After Midnight.

Ce module contient la classe MainWindow qui gère l'interface utilisateur principale
et les interactions avec la base de données pour la gestion des projets et des images.
"""

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTreeWidget, QTreeWidgetItem, QListWidget, QListWidgetItem,
    QLineEdit, QMessageBox, QFileDialog, QInputDialog, QTreeWidgetItemIterator, QDialog, QDialogButtonBox, QCheckBox
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
from src.ui.metadata_config_window import MetadataConfigWindow

CONFIG_DIR = Path.home() / ".aftermidnight"
CONFIG_FILE = CONFIG_DIR / "config.json"

class CustomTreeWidget(QTreeWidget):
    """
    Sous-classe de QTreeWidget pour gérer le glisser-déposer des projets.

    Cette classe étend QTreeWidget pour permettre le déplacement des projets
    par glisser-déposer et pour gérer les événements associés.

    Attributes:
        parent_window (MainWindow): Référence à la fenêtre principale pour accéder aux méthodes de gestion des projets.
    """

    def __init__(self, parent=None):
        """
        Initialise une nouvelle instance de CustomTreeWidget.

        Args:
            parent (QWidget, optional): Le widget parent. Par défaut, None.
        """
        super().__init__(parent)
        self.parent_window = parent
        self.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self.setDragDropMode(QTreeWidget.DragDropMode.InternalMove)

    def dropEvent(self, event):
        """
        Gère l'événement de glisser-déposer.

        Cette méthode est appelée lorsqu'un élément est lâché sur le widget.
        Elle appelle la méthode tree_drop_event de la fenêtre principale pour
        mettre à jour la base de données.

        Args:
            event (QDropEvent): L'événement de glisser-déposer.
        """
        super().dropEvent(event)
        if self.parent_window:
            self.parent_window.tree_drop_event(event)

class MainWindow(QMainWindow):
    """
    Classe principale de l'application After Midnight.

    Cette classe gère l'interface utilisateur principale et les interactions
    avec la base de données pour la gestion des projets et des images.

    Attributes:
        db_path (Path): Chemin vers la base de données SQLite.
        current_project_id (int): Identifiant du projet actuellement sélectionné.
    """

    def __init__(self):
        """
        Initialise une nouvelle instance de MainWindow.

        Configure la fenêtre principale, charge les projets et les paramètres.
        """
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
        """
        Convertit les secondes en format hh:mm:ss.

        Args:
            seconds (float): Durée en secondes à convertir.

        Returns:
            str: Durée formatée en heures, minutes et secondes.
        """
        if seconds is None:
            return "inconnu"

        hours = int(seconds // 3600)
        remaining_seconds = seconds % 3600
        minutes = int(remaining_seconds // 60)
        seconds = int(remaining_seconds % 60)

        return f"{hours}h {minutes}m {seconds}s"

    def save_expanded_state(self):
        """
        Sauvegarde l'état déplié des projets.

        Parcourt tous les projets dans l'arborescence et sauvegarde les identifiants
        des projets qui sont dépliés.
        """
        self.expanded_items = []
        iterator = QTreeWidgetItemIterator(self.project_tree)
        while iterator.value():
            item = iterator.value()
            if item.isExpanded():
                self.expanded_items.append(item.data(0, Qt.ItemDataRole.UserRole))
            iterator += 1

    def restore_expanded_state(self):
        """
        Rétablit l'état déplié des projets.

        Parcourt tous les projets dans l'arborescence et déploie ceux qui étaient
        dépliés avant une opération de mise à jour.
        """
        if hasattr(self, 'expanded_items'):
            iterator = QTreeWidgetItemIterator(self.project_tree)
            while iterator.value():
                item = iterator.value()
                if item.data(0, Qt.ItemDataRole.UserRole) in self.expanded_items:
                    item.setExpanded(True)
                iterator += 1

    def expand_project(self, project_id):
        """
        Déploie un projet spécifique dans l'arborescence.

        Args:
            project_id (int): Identifiant du projet à déplier.
        """
        iterator = QTreeWidgetItemIterator(self.project_tree)
        while iterator.value():
            item = iterator.value()
            if item.data(0, Qt.ItemDataRole.UserRole) == project_id:
                item.setExpanded(True)
                break
            iterator += 1

    def init_ui(self):
        """
        Initialise l'interface utilisateur.

        Configure les layouts, les widgets et les connexions des signaux.
        """
        # Layout principal
        main_widget = QWidget()
        main_layout = QHBoxLayout()

        # Panneau des projets (gauche)
        self.project_panel = QWidget()
        project_layout = QVBoxLayout()

        self.project_label = QLabel("Projets :")
        self.project_tree = CustomTreeWidget(self)
        self.project_tree.setHeaderLabel("Arborescence des Projets")
        self.project_tree.itemSelectionChanged.connect(self.on_project_selected)

        self.new_project_button = QPushButton("Nouveau Projet")
        self.new_project_button.clicked.connect(self.create_project)

        self.delete_project_button = QPushButton("Supprimer le Projet")
        self.delete_project_button.clicked.connect(self.delete_project)

        self.config_button = QPushButton("Configurer les Métadonnées")
        self.config_button.clicked.connect(self.open_metadata_config)

        self.clear_db_button = QPushButton("Vider la Base de Données")
        self.clear_db_button.clicked.connect(self.clear_database)

        project_layout.addWidget(self.project_label)
        project_layout.addWidget(self.project_tree)
        project_layout.addWidget(self.new_project_button)
        project_layout.addWidget(self.delete_project_button)
        project_layout.addWidget(self.config_button)
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
        """
        Active ou désactive le bouton d'importation en fonction de la sélection d'un projet.

        Si un projet est sélectionné, charge les images associées à ce projet.
        """
        selected_items = self.project_tree.selectedItems()
        self.import_button.setEnabled(len(selected_items) > 0)
        if selected_items:
            self.load_project_images()

    def save_last_project(self, project_id):
        """
        Sauvegarde le dernier projet utilisé.

        Args:
            project_id (int): Identifiant du projet à sauvegarder.
        """
        CONFIG_DIR.mkdir(exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump({"last_project_id": project_id}, f)

    def load_last_project(self):
        """
        Charge le dernier projet utilisé.

        Si un projet a été utilisé précédemment, il est sélectionné automatiquement.
        """
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                last_project_id = config.get("last_project_id")
                if last_project_id:
                    # Trouver l'item correspondant dans l'arborescence
                    self.select_project_by_id(self.project_tree.invisibleRootItem(), last_project_id)

    def select_project_by_id(self, parent_item, project_id):
        """
        Sélectionne un projet dans l'arborescence par son identifiant.

        Args:
            parent_item (QTreeWidgetItem): Item parent à partir duquel commencer la recherche.
            project_id (int): Identifiant du projet à sélectionner.

        Returns:
            bool: True si le projet a été trouvé et sélectionné, False sinon.
        """
        for i in range(parent_item.childCount()):
            item = parent_item.child(i)
            if item.data(0, Qt.ItemDataRole.UserRole) == project_id:
                self.project_tree.setCurrentItem(item)
                self.on_project_selected()
                return True
            if self.select_project_by_id(item, project_id):
                return True
        return False

    def load_projects(self):
        """
        Charge la liste des projets depuis la base de données sous forme d'arborescence.

        Récupère tous les projets de la base de données et les organise dans une arborescence
        en fonction de leur parent_id. Les projets d'organisation sont affichés en italique.
        """
        # Sauvegarder l'état déplié des projets
        self.save_expanded_state()

        self.project_tree.clear()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, parent_id, is_organization FROM projects")
            projects = cursor.fetchall()

        # Créer un dictionnaire pour stocker les projets par parent_id
        projects_dict = {}
        for project_id, name, parent_id, is_organization in projects:
            if parent_id not in projects_dict:
                projects_dict[parent_id] = []
            projects_dict[parent_id].append((project_id, name, is_organization))

        # Fonction récursive pour ajouter les projets à l'arborescence
        def add_projects_to_tree(parent_item, parent_id):
            if parent_id in projects_dict:
                for project_id, name, is_organization in projects_dict[parent_id]:
                    item = QTreeWidgetItem(parent_item, [name])
                    item.setData(0, Qt.ItemDataRole.UserRole, project_id)
                    if is_organization:
                        font = item.font(0)
                        font.setItalic(True)
                        item.setFont(0, font)
                    add_projects_to_tree(item, project_id)

        # Ajouter les projets de niveau racine (parent_id = NULL)
        add_projects_to_tree(self.project_tree.invisibleRootItem(), None)

        # Rétablir l'état déplié des projets
        self.restore_expanded_state()

        # Désactiver le bouton d'importation si aucun projet n'est sélectionné
        self.import_button.setEnabled(False)

    def create_project(self):
        """
        Crée un nouveau projet, éventuellement comme sous-projet d'un projet existant.

        Affiche une boîte de dialogue pour saisir le nom du projet et choisir s'il s'agit
        d'un projet d'organisation. Demande également si le projet doit être un sous-projet.
        """
        # Sauvegarder l'état déplié des projets
        self.save_expanded_state()

        # Créer une boîte de dialogue pour le nom du projet et le type de projet
        dialog = QDialog(self)
        dialog.setWindowTitle("Nouveau Projet")
        dialog_layout = QVBoxLayout()

        name_label = QLabel("Nom du projet :")
        name_edit = QLineEdit()
        dialog_layout.addWidget(name_label)
        dialog_layout.addWidget(name_edit)

        org_check = QCheckBox("Projet d'organisation")
        dialog_layout.addWidget(org_check)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        dialog_layout.addWidget(button_box)

        dialog.setLayout(dialog_layout)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        project_name = name_edit.text()
        if not project_name:
            return

        is_organization = org_check.isChecked()

        # Demander si l'utilisateur veut créer un sous-projet
        selected_items = self.project_tree.selectedItems()
        parent_id = None
        if selected_items:
            reply = QMessageBox.question(
                self,
                "Créer un sous-projet",
                "Voulez-vous créer ce projet comme sous-projet du projet sélectionné ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                parent_item = selected_items[0]
                parent_id = parent_item.data(0, Qt.ItemDataRole.UserRole)

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO projects (name, parent_id, is_organization) VALUES (?, ?, ?)
                """, (project_name, parent_id, is_organization))
                conn.commit()
                self.load_projects()

                # Déplier le projet parent si un sous-projet a été créé
                if parent_id is not None:
                    self.expand_project(parent_id)

                # Rétablir l'état déplié des projets
                self.restore_expanded_state()
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Erreur", "Un projet avec ce nom existe déjà.")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Une erreur est survenue : {e}")

    def delete_project(self):
        """
        Supprime le projet sélectionné.

        Vérifie si le projet a des sous-projets avant de le supprimer.
        Affiche une boîte de dialogue de confirmation avant la suppression.
        """
        selected_items = self.project_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Erreur", "Veuillez sélectionner un projet à supprimer.")
            return

        selected_item = selected_items[0]
        project_id = selected_item.data(0, Qt.ItemDataRole.UserRole)
        project_name = selected_item.text(0)

        # Vérifier si le projet a des sous-projets
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM projects WHERE parent_id = ?", (project_id,))
            has_children = cursor.fetchone()[0] > 0

        if has_children:
            QMessageBox.warning(self, "Erreur", f"Le projet '{project_name}' contient des sous-projets et ne peut pas être supprimé.")
            return

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

    def is_child_of(self, project_id, potential_parent_id):
        """
        Vérifie si un projet est un ancêtre d'un autre projet.

        Utilise une requête SQL récursive pour vérifier si potential_parent_id est un
        sous-projet de project_id, ce qui créerait une boucle dans l'arborescence.

        Args:
            project_id (int): Identifiant du projet à vérifier.
            potential_parent_id (int): Identifiant du projet potentiellement parent.

        Returns:
            bool: True si potential_parent_id est un sous-projet de project_id, False sinon.
        """
        if potential_parent_id is None:
            return False

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            WITH RECURSIVE project_tree AS (
                SELECT id, parent_id FROM projects WHERE id = ?
                UNION ALL
                SELECT p.id, p.parent_id FROM projects p
                INNER JOIN project_tree pt ON p.id = pt.parent_id
            )
            SELECT id FROM project_tree WHERE id = ?
            """, (project_id, potential_parent_id))
            return cursor.fetchone() is not None

    def tree_drop_event(self, event):
        """
        Gère l'événement de glisser-déposer pour mettre à jour la base de données.

        Cette méthode est appelée lorsqu'un projet est déplacé par glisser-déposer.
        Elle met à jour la base de données pour refléter le nouvel emplacement du projet.

        Args:
            event (QDropEvent): L'événement de glisser-déposer.
        """
        # Sauvegarder l'état déplié des projets
        self.save_expanded_state()

        # Récupérer l'item déplacé
        item = self.project_tree.currentItem()
        if item is None:
            return

        # Récupérer l'item cible (celui sur lequel on a lâché l'item déplacé)
        drop_item = self.project_tree.itemAt(event.position().toPoint())
        if drop_item is None or drop_item == item:
            return

        project_id = item.data(0, Qt.ItemDataRole.UserRole)
        new_parent_id = drop_item.data(0, Qt.ItemDataRole.UserRole)

        # Vérifier que le projet n'est pas déplacé dans un de ses sous-projets
        if self.is_child_of(project_id, new_parent_id):
            QMessageBox.warning(self, "Erreur", "Un projet ne peut pas être déplacé dans un de ses sous-projets.")
            self.load_projects()  # Recharger l'arborescence pour annuler le déplacement
            return

        # Mettre à jour la base de données pour le projet et ses sous-projets
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Mettre à jour le parent_id du projet déplacé
                cursor.execute("UPDATE projects SET parent_id = ? WHERE id = ?", (new_parent_id, project_id))

                # Mettre à jour le parent_id de tous les sous-projets récursivement
                self.update_children_parent_id(cursor, project_id, new_parent_id)

                conn.commit()
                self.load_projects()

                # Déplier le projet parent si un projet a été déplacé
                self.expand_project(new_parent_id)

                # Rétablir l'état déplié des projets
                self.restore_expanded_state()
        except Exception as e:
            logging.error(f"Erreur lors du déplacement du projet: {e}")
            QMessageBox.critical(self, "Erreur", f"Une erreur est survenue : {e}")
            self.load_projects()  # Recharger l'arborescence en cas d'erreur

    def update_children_parent_id(self, cursor, old_parent_id, new_parent_id):
        """
        Met à jour le parent_id des sous-projets de manière récursive.

        Cette méthode est utilisée pour déplacer tous les sous-projets d'un projet
        lorsque ce projet est déplacé dans l'arborescence.

        Args:
            cursor: Le curseur de la base de données pour exécuter les requêtes SQL.
            old_parent_id (int): L'identifiant du projet parent actuel.
            new_parent_id (int): L'identifiant du nouveau projet parent.
        """
        # Trouver tous les sous-projets directs
        cursor.execute("SELECT id FROM projects WHERE parent_id = ?", (old_parent_id,))
        children = cursor.fetchall()

        # Mettre à jour le parent_id des sous-projets directs
        for child in children:
            child_id = child[0]  # Accéder au premier élément du tuple (l'identifiant du projet)
            cursor.execute("UPDATE projects SET parent_id = ? WHERE id = ?", (new_parent_id, child_id))

            # Mettre à jour récursivement les sous-projets des sous-projets
            self.update_children_parent_id(cursor, child_id, new_parent_id)

    def load_project_images(self):
        """
        Charge et affiche la synthèse des prises de vue classées par soirée.

        Si le projet sélectionné est un projet d'organisation, affiche un message
        indiquant qu'il ne contient pas d'images. Sinon, affiche les images associées.
        """
        selected_items = self.project_tree.selectedItems()
        if selected_items:
            selected_item = selected_items[0]
            self.current_project_id = selected_item.data(0, Qt.ItemDataRole.UserRole)

            # Vérifier si le projet est un projet d'organisation
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT is_organization FROM projects WHERE id = ?", (self.current_project_id,))
                is_organization = cursor.fetchone()[0]

            if is_organization:
                self.session_list.clear()
                self.session_list.addItem("Ce projet est un projet d'organisation et ne contient pas d'images.")
                return

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

    def open_metadata_config(self):
        """
        Ouvre la fenêtre de configuration des métadonnées.

        Affiche une fenêtre modale pour configurer les mots-clés FITS à extraire.
        """
        config_window = MetadataConfigWindow(self, self.db_path)
        if config_window.exec():
            QMessageBox.information(self, "Succès", "Configuration des métadonnées sauvegardée.")

    def import_fits(self):
        """
        Importe des fichiers FITS depuis une arborescence de répertoires.

        Vérifie que le projet sélectionné n'est pas un projet d'organisation.
        Parcourt récursivement le répertoire sélectionné et importe les fichiers FITS.
        """
        if self.current_project_id is None:
            QMessageBox.warning(self, "Erreur", "Veuillez sélectionner un projet.")
            return

        # Vérifier si le projet est un projet d'organisation
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT is_organization FROM projects WHERE id = ?", (self.current_project_id,))
            is_organization = cursor.fetchone()[0]

        if is_organization:
            QMessageBox.warning(self, "Erreur", "Vous ne pouvez pas importer des images dans un projet d'organisation.")
            return

        # Ouvrir une boîte de dialogue pour sélectionner un répertoire
        dir_path = QFileDialog.getExistingDirectory(self, "Sélectionner un répertoire contenant des FITS")
        if dir_path:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Vérifier que les colonnes nécessaires existent dans la table images
                self.ensure_columns_exist(cursor)

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
                                # Construire la requête d'insertion dynamiquement
                                columns = ["filename", "path", "project_id"]
                                values = [filename, file_path, self.current_project_id]

                                for db_name, value in metadata.items():
                                    columns.append(db_name)
                                    values.append(value)

                                # Entourer les noms de colonnes de guillemets s'ils contiennent des espaces ou caractères spéciaux
                                columns_quoted = ['"' + col + '"' if ' ' in col or not col.isalnum() else col for col in columns]
                                placeholders = ', '.join(['?'] * len(values))
                                columns_str = ', '.join(columns_quoted)

                                query = f"INSERT INTO images ({columns_str}) VALUES ({placeholders})"
                                cursor.execute(query, values)

                                logging.info(f"Fichier importé : {file_path}")
            conn.commit()
            self.load_project_images()
            QMessageBox.information(self, "Succès", f"Importation terminée. {cursor.rowcount} nouveaux fichiers ajoutés.")

    def ensure_columns_exist(self, cursor):
        """
        Vérifie et ajoute les colonnes manquantes dans la table images.

        Args:
            cursor: Le curseur de la base de données pour exécuter les requêtes SQL.
        """
        cursor.execute("PRAGMA table_info(images)")
        existing_columns = {column[1].lower() for column in cursor.fetchall()}

        with sqlite3.connect(self.db_path) as conn:
            config_cursor = conn.cursor()
            config_cursor.execute("SELECT db_name FROM metadata_config")
            required_columns = {row[0] for row in config_cursor.fetchall()}

        for column in required_columns:
            if column.lower() not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE images ADD COLUMN '{column}' TEXT")
                    logging.info(f"Colonne {column} ajoutée à la table images.")
                except sqlite3.OperationalError as e:
                    logging.warning(f"Erreur lors de l'ajout de la colonne {column}: {e}")

    def extract_fits_metadata(self, fits_file):
        """
        Extrait les métadonnées d'un fichier FITS en utilisant la configuration personnalisée.

        Args:
            fits_file (str): Chemin vers le fichier FITS à analyser.

        Returns:
            dict: Dictionnaire contenant les métadonnées extraites.
        """
        metadata = {}

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT fits_keyword, db_name FROM metadata_config")
            config = cursor.fetchall()

        try:
            with fits.open(fits_file) as hdul:
                header = hdul[0].header

                for fits_keyword, db_name in config:
                    value = header.get(fits_keyword, None)

                    if value is not None:
                        if db_name == "exposure" and value is not None:
                            try:
                                metadata[db_name] = float(value)
                            except ValueError:
                                metadata[db_name] = None
                        elif db_name == "date_obs" and value is not None:
                            date_loc_clean = value.strip()
                            if '.' in date_loc_clean:
                                date_part, fractional_part = date_loc_clean.split('.')
                                fractional_part = fractional_part[:6]  # Tronquer à 6 chiffres
                                date_loc_clean = f"{date_part}.{fractional_part}"
                            metadata[db_name] = date_loc_clean
                        else:
                            metadata[db_name] = value

        except Exception as e:
            logging.error(f"Erreur lors de l'extraction des métadonnées : {e}")

        return metadata

    def clear_database(self):
        """
        Vide la base de données avec une double validation, en conservant les métadonnées protégées.

        Affiche deux boîtes de dialogue de confirmation avant de vider la base de données.
        Conserve les métadonnées protégées (date_obs, exposure, ra, dec, filter).
        """
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

                        # Sauvegarder les métadonnées protégées
                        protected_metadata = []
                        for fits_keyword, db_name in [("DATE-LOC", "date_obs"), ("EXPOSURE", "exposure"), ("RA", "ra"), ("DEC", "dec"), ("FILTER", "filter")]:
                            cursor.execute("SELECT 1 FROM metadata_config WHERE fits_keyword = ? AND db_name = ?", (fits_keyword, db_name))
                            if cursor.fetchone() is None:
                                protected_metadata.append((fits_keyword, db_name))

                        # Supprimer toutes les images
                        cursor.execute("DELETE FROM images")
                        # Supprimer tous les projets
                        cursor.execute("DELETE FROM projects")
                        # Supprimer toutes les métadonnées sauf celles protégées
                        cursor.execute("DELETE FROM metadata_config WHERE db_name NOT IN ('date_obs', 'exposure', 'ra', 'dec', 'filter')")

                        # Réinsérer les métadonnées protégées si elles ont été supprimées
                        for fits_keyword, db_name in protected_metadata:
                            cursor.execute("INSERT INTO metadata_config (fits_keyword, db_name) VALUES (?, ?)", (fits_keyword, db_name))

                        conn.commit()
                    self.load_projects()
                    self.session_list.clear()
                    QMessageBox.information(self, "Succès", "La base de données a été vidée avec succès, en conservant les métadonnées protégées.")
                except Exception as e:
                    QMessageBox.critical(self, "Erreur", f"Une erreur est survenue : {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
