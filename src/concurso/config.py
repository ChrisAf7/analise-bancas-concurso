"""Caminhos do projeto. Tudo em data/ fica fora do git (ADR-013)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = DATA / "raw"          # PDFs originais, nomeados pelo sha256
INBOX = DATA / "inbox"      # downloads manuais aguardando registro
WORK = DATA / "work"        # artefatos intermediários regeneráveis
DB_PATH = DATA / "concurso.sqlite"
MIGRATIONS = ROOT / "db" / "migrations"
CONFIG = ROOT / "config"
