"""Carrega a taxonomia e os itens do edital-alvo no banco (ADR-008).

Uso:  python -m concurso.taxonomy load taxonomy/dir_adm_v0.toml
"""
from __future__ import annotations

import sqlite3
import sys
import tomllib
from pathlib import Path

from .db import connect, migrate

# Concurso-alvo (SPEC §5.2). O edital é registrado em source_document pelo sha256.
ALVO = {
    "banca": ("FCC", "Fundação Carlos Chagas"),
    "orgao": ("STC-MA", "Secretaria de Estado de Transparência e Controle do Maranhão", "MA", "estadual", "controladoria"),
    "ano": 2027,  # ano de aplicação da prova (04/04/2027)
    "nome": "Concurso Unificado MA – Edital nº 01/2026",
    "edital_sha256": "fd1f2d44d104f19ca7f3ca7dfc81b46e9f27c3f3cc5fff4a7b7a0bf2099a163c",
}


def _upsert_id(conn, select_sql, select_args, insert_sql, insert_args) -> int:
    row = conn.execute(select_sql, select_args).fetchone()
    if row:
        return row[0]
    return conn.execute(insert_sql, insert_args).lastrowid


def ensure_alvo(conn: sqlite3.Connection) -> int:
    sigla, nome = ALVO["banca"]
    banca_id = _upsert_id(conn, "SELECT id FROM banca WHERE sigla=?", (sigla,),
                          "INSERT INTO banca (sigla, nome) VALUES (?,?)", (sigla, nome))
    o = ALVO["orgao"]
    orgao_id = _upsert_id(conn, "SELECT id FROM orgao WHERE sigla=?", (o[0],),
                          "INSERT INTO orgao (sigla, nome, uf, esfera, tipo) VALUES (?,?,?,?,?)", o)
    edital = conn.execute("SELECT id FROM source_document WHERE sha256=?", (ALVO["edital_sha256"],)).fetchone()
    return _upsert_id(
        conn,
        "SELECT id FROM concurso WHERE banca_id=? AND orgao_id=? AND ano=? AND nome=?",
        (banca_id, orgao_id, ALVO["ano"], ALVO["nome"]),
        "INSERT INTO concurso (banca_id, orgao_id, ano, nome, edital_document_id) VALUES (?,?,?,?,?)",
        (banca_id, orgao_id, ALVO["ano"], ALVO["nome"], edital[0] if edital else None),
    )


def load(conn: sqlite3.Connection, path: Path) -> None:
    with open(path, "rb") as f:
        t = tomllib.load(f)
    v = t["version"]
    with conn:
        d = t["disciplina"]
        disc_id = _upsert_id(
            conn, "SELECT id FROM taxonomy_node WHERE slug=? AND taxonomy_version=?", (d["slug"], v),
            "INSERT INTO taxonomy_node (parent_id, nivel, slug, nome, taxonomy_version) VALUES (NULL,'disciplina',?,?,?)",
            (d["slug"], d["nome"], v))
        slug_to_id = {d["slug"]: disc_id}
        for tp in t["topico"]:
            slug_to_id[tp["slug"]] = _upsert_id(
                conn, "SELECT id FROM taxonomy_node WHERE slug=? AND taxonomy_version=?", (tp["slug"], v),
                "INSERT INTO taxonomy_node (parent_id, nivel, slug, nome, descricao, taxonomy_version) "
                "VALUES (?,'topico',?,?,?,?)",
                (disc_id, tp["slug"], tp["nome"], tp.get("descricao"), v))
        concurso_id = ensure_alvo(conn)
        for it in t.get("edital_item", []):
            item_id = _upsert_id(
                conn,
                "SELECT id FROM edital_item WHERE concurso_id=? AND cargo=? AND disciplina_rotulo=? AND ordem=?",
                (concurso_id, it["cargo"], it["disciplina_rotulo"], it["ordem"]),
                "INSERT INTO edital_item (concurso_id, cargo, disciplina_rotulo, ordem, texto) VALUES (?,?,?,?,?)",
                (concurso_id, it["cargo"], it["disciplina_rotulo"], it["ordem"], it["texto"]))
            for slug in it["mapeia"]:
                conn.execute("INSERT OR IGNORE INTO edital_item_map VALUES (?,?)", (item_id, slug_to_id[slug]))
    n_top = conn.execute("SELECT COUNT(*) FROM taxonomy_node WHERE taxonomy_version=? AND nivel='topico'", (v,)).fetchone()[0]
    n_it = conn.execute("SELECT COUNT(*) FROM edital_item").fetchone()[0]
    print(f"taxonomia {v}: {n_top} tópicos; {n_it} itens de edital mapeados")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "load":
        c = connect()
        migrate(c)
        load(c, Path(sys.argv[2]))
    else:
        print(__doc__)
