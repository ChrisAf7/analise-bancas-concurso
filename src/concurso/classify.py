"""Classificação por IA com proveniência (ARCHITECTURE §4, ADR-012/016/018).

Cada (avaliador, prompt_version, codebook, repetição) é um annotation_run. A execução é RETOMÁVEL:
rodar de novo só classifica as questões que ainda não têm anotação naquele run (útil com limites diários).

Uso:
  python -m concurso.classify run A 1      # avaliador A, repetição 1, escopo do MVP
  python -m concurso.classify run B 2 --lote 10
  python -m concurso.classify status
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tomllib
from datetime import datetime, timezone

from .config import ROOT
from .db import connect, migrate
from .llm import LLMClient, load_raters

CODEBOOK_VERSION = "v0"
PROMPT_FILE = ROOT / "prompts" / "classify_v0.md"
CODEBOOK_FILE = ROOT / "codebook" / "v0.toml"
TAXONOMY_FILE = ROOT / "taxonomy" / "dir_adm_v0.toml"

# Escopo do MVP (ADR-018): Dir. Adm. pelo rótulo observado + Conhecimentos Específicos sem título do C10.
SCOPE_SQL = """
SELECT q.id, q.enunciado, q.texto_base, q.gabarito_definitivo
FROM question q JOIN prova p ON p.id = q.prova_id
WHERE q.status = 'valida' AND (
      q.disciplina_rotulo LIKE '%Direito Administrativo%'
   OR (p.corpus_id = 'C10' AND q.disciplina_rotulo = 'Conhecimentos Específicos'))
ORDER BY q.id
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_codebook() -> dict:
    with open(CODEBOOK_FILE, "rb") as f:
        return tomllib.load(f)


def build_system_prompt() -> tuple[str, str]:
    cb = load_codebook()
    parts = []
    for v in cb["variavel"]:
        parts.append(f"## {v['nome']} ({'um valor' if v['tipo'] == 'unico' else 'lista com um ou mais valores'})")
        parts.append(f"Pergunta: {v['pergunta']}")
        parts.append("Valores permitidos: " + ", ".join(v["valores"]))
        parts += [f"- {d}" for d in v["definicoes"]]
        if v.get("regras"):
            parts.append("Regras de decisão:")
            parts += [f"- {r}" for r in v["regras"]]
        if v.get("exemplos"):
            parts.append("Exemplos (sintéticos):")
            parts += [f"- {e}" for e in v["exemplos"]]
        parts.append("")
    with open(TAXONOMY_FILE, "rb") as f:
        tax = tomllib.load(f)
    taxo = "\n".join(f"- {t['slug']}: {t['nome']} — {t.get('descricao', '')}" for t in tax["topico"])
    template = PROMPT_FILE.read_text(encoding="utf-8")
    system = template.replace("{codebook}", "\n".join(parts)).replace("{taxonomia}", taxo)
    version = hashlib.sha256(system.encode("utf-8")).hexdigest()[:12]
    return system, version


def validate(item: dict, cb: dict) -> list[str]:
    errs = []
    allowed = {v["nome"]: (v["tipo"], set(v["valores"])) for v in cb["variavel"]}
    for nome, (tipo, vals) in allowed.items():
        val = item.get(nome)
        if tipo == "unico":
            if val not in vals:
                errs.append(f"{nome}={val!r}")
        else:
            if not isinstance(val, list) or not val or any(x not in vals for x in val):
                errs.append(f"{nome}={val!r}")
            elif "indeterminada" in val and len(val) > 1:
                errs.append(f"{nome}: indeterminada combinada")
    return errs


def format_questions(rows) -> str:
    payload = []
    for r in rows:
        alts = {a: t for a, t in r["alts"].items()}
        q = {"id": r["id"], "enunciado": r["enunciado"], "alternativas": alts, "gabarito": r["gabarito"]}
        if r.get("texto_base"):
            q["texto_base"] = r["texto_base"]
        payload.append(q)
    return "Classifique as questões abaixo (JSON):\n" + json.dumps(payload, ensure_ascii=False, indent=1)


def get_or_create_run(conn, rater, prompt_version: str, rep: int) -> int:
    annotator = f"{rater.name}:{rater.model}"
    row = conn.execute("SELECT id FROM annotation_run WHERE annotator_id=? AND prompt_version=? AND codebook_version=? "
                       "AND repeticao=? AND purpose='producao'",
                       (annotator, prompt_version, CODEBOOK_VERSION, rep)).fetchone()
    if row:
        return row[0]
    with conn:
        return conn.execute(
            "INSERT INTO annotation_run (annotator_type, annotator_id, provider, prompt_version, codebook_version, "
            "params_json, purpose, repeticao, blind, started_at) VALUES ('llm',?,?,?,?,?,'producao',?,1,?)",
            (annotator, rater.provider, prompt_version, CODEBOOK_VERSION,
             json.dumps({"json_mode": rater.json_mode, "base_url": rater.base_url}), rep, now())).lastrowid


def pending_questions(conn, run_id: int) -> list[dict]:
    done = {r[0] for r in conn.execute("SELECT DISTINCT question_id FROM annotation WHERE run_id=?", (run_id,))}
    out = []
    for r in conn.execute(SCOPE_SQL):
        if r["id"] in done:
            continue
        alts = {a["letra"]: a["texto"] for a in conn.execute(
            "SELECT letra, texto FROM alternative WHERE question_id=? ORDER BY letra", (r["id"],))}
        out.append({"id": r["id"], "enunciado": r["enunciado"], "texto_base": r["texto_base"],
                    "gabarito": r["gabarito_definitivo"], "alts": alts})
    return out


def save(conn, run_id: int, item: dict, model_reported: str) -> None:
    ts = now()
    rows = [(run_id, item["id"], "cenario", item["cenario"]),
            (run_id, item["id"], "demanda_cognitiva", item["demanda_cognitiva"]),
            (run_id, item["id"], "topico", item["topico"])]
    rows += [(run_id, item["id"], "fonte_normativa", v) for v in sorted(set(item["fonte_normativa"]))]
    with conn:
        conn.executemany(
            "INSERT OR IGNORE INTO annotation (run_id, question_id, alternativa, campo, valor, evidencia, justificativa, created_at) "
            "VALUES (?,?,'',?,?,?,?,?)",
            [(r, q, c, v, str(item.get("evidencia", ""))[:500], str(item.get("justificativa", ""))[:800], ts)
             for r, q, c, v in rows])
        conn.execute("UPDATE annotation_run SET model_reported=? WHERE id=?", (model_reported, run_id))


def run(rater_name: str, rep: int, lote: int) -> None:
    conn = connect()
    migrate(conn)
    rater = load_raters()[rater_name]
    client = LLMClient(rater)
    cb = load_codebook()
    system, prompt_version = build_system_prompt()
    run_id = get_or_create_run(conn, rater, prompt_version, rep)
    todo = pending_questions(conn, run_id)
    print(f"[{rater_name} rep{rep}] run={run_id} prompt={prompt_version} pendentes={len(todo)}", flush=True)

    queue = [todo[i:i + lote] for i in range(0, len(todo), lote)]
    while queue:
        batch = queue.pop(0)
        try:
            res = client.chat_json(system, format_questions(batch), max_attempts=8)  # limites gratuitos: paciência
        except Exception as e:  # noqa: BLE001
            print(f"  lote falhou ({type(e).__name__}: {str(e)[:200]}); parando — rode de novo para retomar", flush=True)
            break
        by_id = {it.get("id"): it for it in res.data.get("resultados", []) if isinstance(it, dict)}
        retry = []
        for q in batch:
            it = by_id.get(q["id"])
            errs = validate(it, cb) if it else ["ausente na resposta"]
            if errs:
                retry.append(q)
                print(f"  q{q['id']}: inválida ({'; '.join(errs)[:150]})", flush=True)
            else:
                save(conn, run_id, it, res.model_reported)
        if retry and len(batch) > 1:
            queue += [[q] for q in retry]          # refaz uma a uma
        done = conn.execute("SELECT COUNT(DISTINCT question_id) FROM annotation WHERE run_id=?", (run_id,)).fetchone()[0]
        print(f"  ok lote de {len(batch)} ({res.latency_s}s) — total no run: {done}", flush=True)
    with conn:
        conn.execute("UPDATE annotation_run SET finished_at=? WHERE id=?", (now(), run_id))


def status() -> None:
    conn = connect()
    migrate(conn)
    total = len(conn.execute(SCOPE_SQL).fetchall())
    print(f"escopo do MVP: {total} questões")
    for r in conn.execute("SELECT r.id, r.annotator_id, r.repeticao, r.prompt_version, r.model_reported, "
                          "COUNT(DISTINCT a.question_id) n FROM annotation_run r LEFT JOIN annotation a ON a.run_id=r.id "
                          "GROUP BY r.id ORDER BY r.id"):
        print(f"  run {r['id']}: {r['annotator_id']} rep{r['repeticao']} prompt={r['prompt_version']} "
              f"modelo={r['model_reported']} -> {r['n']}/{total}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("rater")
    r.add_argument("rep", type=int)
    r.add_argument("--lote", type=int, default=10)
    sub.add_parser("status")
    sub.add_parser("prompt")
    a = ap.parse_args()
    if a.cmd == "run":
        run(a.rater, a.rep, a.lote)
    elif a.cmd == "status":
        status()
    else:
        s, v = build_system_prompt()
        print(f"prompt_version={v}\n\n{s}")


if __name__ == "__main__":
    main()
