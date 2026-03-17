import logging
from logging.handlers import RotatingFileHandler
import os

LOG_DIR = os.getenv("LOG_DIR", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

def configure_logging(level=logging.INFO):
    root = logging.getLogger()
    root.setLevel(level)

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root.addHandler(ch)

    # Rotating file handler
    fh = RotatingFileHandler(os.path.join(LOG_DIR, "app.log"), maxBytes=5_000_000, backupCount=5)
    fh.setLevel(level)
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s [%(process)d]: %(message)s"))
    root.addHandler(fh)
