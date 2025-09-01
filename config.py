import os
from dotenv import load_dotenv

# Carica le variabili d'ambiente dal file .env
load_dotenv()

class Config:
    """Configurazioni di base per l'applicazione Flask."""
    # Chiave segreta per la sessione Flask e i messaggi flash
    SECRET_KEY = os.environ.get('SECRET_KEY', 'una-chiave-segreta-molto-difficile-da-indovinare')
    
    # Configurazione del database
    # Usa l'URL del database fornito dalla variabile d'ambiente.
    # Se non è disponibile, usa un database SQLite locale per lo sviluppo.
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'database.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Configurazione di Cloudinary per l'upload dei file
    CLOUDINARY_URL = os.environ.get('CLOUDINARY_URL')