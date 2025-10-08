class Image:
    def __init__(self, id=None, path=None, date_obs=None, exposure=None, ra=None, dec=None, filter=None, imagetyp="LIGHT"):
        self.id = id  # Identifiant en base de données
        self.path = path  # Chemin vers le fichier FITS
        self.date_obs = date_obs  # Date d'observation
        self.exposure = exposure  # Temps d'exposition
        self.ra = ra  # Ascension droite
        self.dec = dec  # Déclinaison
        self.filter = filter  # Filtre utilisé
        self.imagetyp = imagetyp  # Nouveau champ : type d'image (LIGHT, FLAT, etc.)

    def __repr__(self):
        return f"Image(id={self.id}, path={self.path}, imagetyp={self.imagetyp})"
