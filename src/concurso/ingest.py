"""Registro de documentos-fonte com proveniência (ARCHITECTURE §3, estágio 1).

Cada arquivo é copiado para data/raw/<sha256>.<ext> e registrado em source_document.
Registrar o mesmo arquivo duas vezes não duplica nada (sha256 único).

Uso:
  python -m concurso.ingest register <arquivo> --kind prova --origin pci --url <url> [--corpus C01] [--notes ...]
  python -m concurso.ingest inbox        # registra tudo em data/inbox/Cxx/ usando corpus/candidatos.csv
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .config import INBOX, RAW, ROOT
from .db import connect, migrate


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def register(conn: sqlite3.Connection, path: Path, kind: str, origin: str, url: str | None,
             corpus_id: str | None = None, notes: str | None = None) -> tuple[int, bool]:
    """Retorna (id, novo?)."""
    digest = sha256_file(path)
    row = conn.execute("SELECT id FROM source_document WHERE sha256 = ?", (digest,)).fetchone()
    if row:
        return row["id"], False
    RAW.mkdir(parents=True, exist_ok=True)
    dest = RAW / f"{digest}{path.suffix.lower()}"
    if not dest.exists():
        shutil.copy2(path, dest)
    with conn:
        cur = conn.execute(
            "INSERT INTO source_document (kind, origin, url, retrieved_at, sha256, local_path, corpus_id, notes) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (kind, origin, url, datetime.now(timezone.utc).isoformat(timespec="seconds"),
             digest, dest.name, corpus_id, notes),
        )
    return cur.lastrowid, True


def guess_kind(filename: str) -> str:
    name = filename.lower()
    if "gabarito" in name:
        return "gabarito"
    if "edital" in name:
        return "edital"
    return "prova"


def register_inbox(conn: sqlite3.Connection) -> None:
    """Registra data/inbox/Cxx/*.pdf; origem e URL vêm de corpus/candidatos.csv."""
    with open(ROOT / "corpus" / "candidatos.csv", encoding="utf-8") as f:
        corpus = {r["corpus_id"]: r for r in csv.DictReader(f)}
    for folder in sorted(p for p in INBOX.glob("C*") if p.is_dir()):
        meta = corpus.get(folder.name)
        if not meta:
            print(f"  {folder.name}: não está em corpus/candidatos.csv, ignorado")
            continue
        pdfs = sorted(folder.glob("*.pdf"))
        if not pdfs:
            continue
        for pdf in pdfs:
            doc_id, new = register(conn, pdf, guess_kind(pdf.name), meta["origem"], meta["url"],
                                   corpus_id=folder.name, notes=f"arquivo original: {pdf.name}")
            print(f"  {folder.name}/{pdf.name}: {'registrado' if new else 'já existia'} (id={doc_id})")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("register")
    r.add_argument("path", type=Path)
    r.add_argument("--kind", required=True)
    r.add_argument("--origin", required=True)
    r.add_argument("--url")
    r.add_argument("--corpus")
    r.add_argument("--notes")
    sub.add_parser("inbox")
    args = ap.parse_args()

    conn = connect()
    migrate(conn)
    if args.cmd == "register":
        doc_id, new = register(conn, args.path, args.kind, args.origin, args.url, args.corpus, args.notes)
        print(f"{'registrado' if new else 'já existia'}: source_document.id={doc_id}")
    else:
        register_inbox(conn)


if __name__ == "__main__":
    main()
