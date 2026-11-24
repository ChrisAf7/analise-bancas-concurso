"""Parser de cadernos e gabaritos da FCC → tabelas observadas (ARCHITECTURE §3, estágios 2–7).

O texto das questões é copiado do PDF sem nenhuma reescrita (só junção de linhas e de hifenização
de fim de linha). Nenhum LLM participa deste estágio.

Uso:
  python -m concurso.parse_fcc load            # todos os corpus_id com PDFs registrados
  python -m concurso.parse_fcc load C01 C02    # só alguns
  python -m concurso.parse_fcc show C01 15     # imprime uma questão extraída (depuração local)
"""
from __future__ import annotations

import csv
import hashlib
import re
import sqlite3
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber

from .config import RAW, ROOT
from .db import connect, migrate
from .pdftext import Line, document_lines, is_noise

PARSER_VERSION = "fcc-0.1"
LETTERS = "ABCDE"

# ---------------------------------------------------------------- utilidades de texto

def join_lines(lines: list[str]) -> str:
    """Junta linhas desfazendo a hifenização de fim de linha da FCC.

    'le-' + 'gislador' -> 'legislador';  'Estados-' + '-membros' -> 'Estados-membros'.
    """
    out = ""
    for raw in lines:
        ln = raw.strip()
        if not ln:
            continue
        if not out:
            out = ln
        elif out.endswith("-") and ln.startswith("-"):
            out = out[:-1] + ln
        elif out.endswith("-") and ln[:1].islower():
            out = out[:-1] + ln
        else:
            out = out + " " + ln
    return re.sub(r"[ \t]+", " ", out).strip()


def normalize_for_hash(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def slug(s: str) -> str:
    return normalize_for_hash(s).replace(" ", "-")


# ---------------------------------------------------------------- gabaritos

@dataclass
class GabBlock:
    cargo: str | None
    tipo: int | None
    label: str | None
    answers: dict[int, str] = field(default_factory=dict)


_RE_CARGO = re.compile(r"(?:Cargo ou opç[ãa]o\s*|^\d{8}\s+|Número do caderno\s+)([A-Z]\d{2})\s*-")
_RE_TIPO = re.compile(r"Tipo gabarito\s*(\d)?")
_RE_PAIR = re.compile(r"(\d{3})\s*-\s*([A-EX*])\b")
_RE_GRID_NUMS = re.compile(r"^(\d{3})(\s+\d{3})*$")
_RE_GRID_LETTERS = re.compile(r"^(-\s*[A-EX*]\s*)+$")
_RE_LABEL = re.compile(r"(Conhec|C\.\s*(Gerais|Espec|Básic|B[áa]sicos)|Gerais|Espec[íi]fic|B[áa]sic)", re.I)


def gabarito_lines(path: Path) -> list[str]:
    if path.suffix.lower() == ".txt":
        return [l for l in path.read_text(encoding="utf-8").splitlines() if not l.startswith("#")]
    with pdfplumber.open(path) as pdf:
        return [l for p in pdf.pages for l in (p.extract_text() or "").splitlines() if not is_noise(l)]


def parse_gabarito(lines: list[str]) -> list[GabBlock]:
    blocks: list[GabBlock] = []
    cur: GabBlock | None = None
    pending_label: str | None = None
    expect_tipo = False
    i = 0
    while i < len(lines):
        ln = lines[i].strip()
        i += 1
        if not ln:
            continue
        m = _RE_CARGO.search(ln)
        if m:
            cur = GabBlock(m.group(1), None, pending_label)
            blocks.append(cur)
            pending_label = None
            continue
        m = _RE_TIPO.search(ln)
        if m:
            if cur is None:
                cur = GabBlock(None, None, pending_label)
                blocks.append(cur)
            if m.group(1):
                cur.tipo = int(m.group(1))
            else:
                expect_tipo = True
            continue
        if expect_tipo and ln.isdigit():
            cur.tipo = int(ln)
            expect_tipo = False
            continue
        if _RE_GRID_NUMS.match(ln) and i < len(lines) and _RE_GRID_LETTERS.match(lines[i].strip()):
            nums = [int(n) for n in ln.split()]
            lets = re.findall(r"[A-EX*]", lines[i])
            i += 1
            if cur is None:
                cur = GabBlock(None, None, pending_label)
                blocks.append(cur)
            cur.answers.update(zip(nums, lets))
            continue
        pairs = _RE_PAIR.findall(ln)
        if pairs:
            if cur is None:
                cur = GabBlock(None, None, pending_label)
                blocks.append(cur)
            for n, v in pairs:
                cur.answers[int(n)] = v
            continue
        if _RE_LABEL.search(ln) and len(ln) < 80:
            if cur is not None and not cur.answers and cur.label is None:
                cur.label = ln           # rótulo depois de "Tipo gabarito" (formato C12)
            else:
                pending_label = ln       # rótulo antes de "Cargo ou opção" (formato C02)
    return [b for b in blocks if b.answers]


# ---------------------------------------------------------------- provas

_RE_Q = re.compile(r"^(\d{1,3})\s*\.\s*(.*)$")
_RE_ALT = re.compile(r"^\(\s?([A-E])\s?\)\s*(.*)$")         # aceita "( A)" — variação vista em C06 e C08
_RE_ALT_SPLIT = re.compile(r"\s(?=\(\s?[B-E]\s?\)\s)")
_RE_SEP = re.compile(r"^_{8,}$")
_RE_ATENCAO = re.compile(r"^(Atenção|Instruções|Instrução)\s*:|quest(ões|ão) de n[úu]meros?\s+\d+\s+(a|e)\s+\d+", re.I)
_RE_RANGE = re.compile(r"n[úu]meros?\s+(\d+)\s+(?:a|e)\s+(\d+)", re.I)
_RE_SECAO = re.compile(r"^CONHECIMENTOS\s+(GERAIS|ESPEC[ÍI]FICOS|B[ÁA]SICOS)(\s+I+)?$", re.I)
_DISC_HEAD = re.compile(
    r"^(Noções( Básicas)? de |Língua |Português|Inglês|Matemática|Raciocínio|Direito |Legislação|Contabilidade|"
    r"Auditoria|Administração|Economia|Finanças|Estatística|Informática|Tecnologia|Controle |Processo |"
    r"Orçamento|Ética|Atualidades|Realidade|História|Geografia|Gestão|Arquivologia|Comércio|Políticas|"
    r"Análise|Fundamentos|Governança|Lei |Regimento|Licitações|Improbidade|Responsabilidade Fiscal|Teoria )"
)
_RE_COVER_COUNT = re.compile(r"contém\s+(\d+)\s+questões")
_RE_COVER_LINE = re.compile(r"contém\s+\d+\s+questões|Verifique se este caderno|^INSTRUÇÕES$|^I N S T R U", re.I)
_RE_HEADER = re.compile(r"Caderno de Prova\s*['’‘]?\s*(\w+)\s*['’‘]?,?\s*Tipo\s*(\d+)")


@dataclass
class Question:
    numero: int
    disciplina: str | None
    stem: list[str] = field(default_factory=list)
    alts: dict[str, list[str]] = field(default_factory=dict)
    texto_base: str | None = None
    page: int = 0

    @property
    def enunciado(self) -> str:
        return join_lines(self.stem)

    def alternativas(self) -> dict[str, str]:
        return {k: join_lines(v) for k, v in self.alts.items()}


@dataclass
class Part:
    questions: list[Question] = field(default_factory=list)
    secao: str | None = None
    source_id: int | None = None


def _looks_like_heading(text: str, prev: str | None) -> bool:
    t = text.strip()
    if len(t) > 90 or t[-1:] in ".,;:?)" or not _DISC_HEAD.match(t) or len(t.split()) > 8:
        return False
    return prev is None or prev.rstrip()[-1:] in ".?)" or _RE_SEP.match(prev.strip()) is not None


def parse_prova(lines: list[Line], source_id: int) -> list[Part]:
    parts: list[Part] = [Part(source_id=source_id)]
    q: Question | None = None
    cur_alt: str | None = None
    closed = False                # separador "____" visto depois da última alternativa
    disciplina: str | None = None
    secao: str | None = None
    texto_buf: list[str] | None = None
    texto_range: tuple[int, int] | None = None
    textos: list[tuple[tuple[int, int], str]] = []
    prev: str | None = None
    started = False
    boundary_seen = False         # marcador de seção ou capa desde a última questão (permite numeração recomeçar)

    def next_expected() -> int:
        return (q.numero + 1) if q else 1

    def finish_texto():
        nonlocal texto_buf, texto_range
        if texto_buf is not None and texto_range:
            textos.append((texto_range, join_lines(texto_buf)))
        texto_buf, texto_range = None, None

    for ln in lines:
        text = ln.text.strip()
        if _RE_COVER_LINE.search(text):
            boundary_seen = True
        m_sec = _RE_SECAO.match(text)
        if m_sec:
            boundary_seen = True
            secao = text.title()
            if not parts[-1].questions:
                parts[-1].secao = secao
            disciplina = secao      # sem título de disciplina, vale a seção (não arrastar a disciplina anterior)
            prev = None             # um título de disciplina pode vir logo depois da linha de seção
            continue
        if _RE_SEP.match(text):
            closed = True
            prev = text
            continue
        m_q = _RE_Q.match(text)
        if m_q:
            n = int(m_q.group(1))
            restart = n == 1 and q is not None and q.numero > 5 and boundary_seen
            if n == next_expected() or restart:
                if restart:                                  # recomeço de numeração após capa/seção = novo caderno
                    parts.append(Part(secao=secao, source_id=source_id))
                finish_texto()
                q = Question(n, disciplina, [m_q.group(2)] if m_q.group(2) else [], page=ln.page)
                parts[-1].questions.append(q)
                cur_alt, closed, started, boundary_seen = None, False, True, False
                prev = text
                continue
        if not started and not _RE_ATENCAO.search(text):
            if _looks_like_heading(text, None):
                disciplina = text
            prev = text
            continue
        if _looks_like_heading(text, prev) and (q is None or cur_alt == "E" or closed):
            disciplina = text
            finish_texto()
            closed = True
            prev = text
            continue
        if _RE_ATENCAO.search(text) and (q is None or cur_alt == "E" or closed):
            finish_texto()
            m_r = _RE_RANGE.search(text)
            texto_range = (int(m_r.group(1)), int(m_r.group(2))) if m_r else None
            texto_buf = [text]
            closed = True
            prev = text
            continue
        if texto_buf is not None:
            texto_buf.append(text)
            prev = text
            continue
        m_a = _RE_ALT.match(text)
        if m_a and q is not None:
            pieces = _RE_ALT_SPLIT.split(text)       # alternativas curtas lado a lado na mesma linha
            handled = False
            for piece in pieces:
                ma = _RE_ALT.match(piece)
                expected = LETTERS[len(q.alts)] if len(q.alts) < 5 else None
                if ma and ma.group(1) == expected:
                    q.alts[expected] = [ma.group(2)] if ma.group(2) else []
                    cur_alt = expected
                    handled = True
                elif handled and cur_alt:
                    q.alts[cur_alt].append(piece)
            if handled:
                closed = False
                prev = text
                continue
        if q is None or closed:
            prev = text            # texto solto entre questões (ex.: instruções); descartado
            continue
        if cur_alt:
            q.alts[cur_alt].append(text)
        else:
            q.stem.append(text)
        prev = text
    finish_texto()
    for part in parts:
        for qq in part.questions:
            for (a, b), txt in textos:
                if a <= qq.numero <= b:
                    qq.texto_base = txt
    return [p for p in parts if p.questions]


def prova_header(path: Path) -> tuple[str | None, str | None, list[int]]:
    with pdfplumber.open(path) as pdf:
        txt = "\n".join((p.extract_text() or "") for p in pdf.pages)
    m = _RE_HEADER.search(txt)
    counts = [int(c) for c in _RE_COVER_COUNT.findall(txt)]
    return (m.group(1) if m else None, m.group(2) if m else None, counts)


# ---------------------------------------------------------------- casamento parte ↔ bloco do gabarito

def _label_key(s: str | None) -> str | None:
    if not s:
        return None
    s = normalize_for_hash(s)
    if "espec" in s:
        return "espec"
    if "basic" in s:
        return "basic"
    if "gera" in s:
        return "gera"
    return None


def match_blocks(parts: list[Part], blocks: list[GabBlock], code: str | None, tipo: str | None) -> list[GabBlock | None]:
    t = int(tipo) if tipo else None
    cands = [b for b in blocks if (b.cargo in (None, code)) and (b.tipo in (None, t))]
    if len(parts) == 1 and len(cands) == 1:
        return [cands[0]]
    result: list[GabBlock | None] = []
    used: set[int] = set()
    for i, part in enumerate(parts):
        key = _label_key(part.secao)
        pick = None
        for j, b in enumerate(cands):
            if j not in used and key and _label_key(b.label) == key and len(b.answers) == len(part.questions):
                pick = j
                break
        if pick is None:   # por ordem, desde que a contagem bata
            for j, b in enumerate(cands):
                if j not in used and len(b.answers) == len(part.questions):
                    pick = j
                    break
        if pick is not None:
            used.add(pick)
        result.append(cands[pick] if pick is not None else None)
    return result


# ---------------------------------------------------------------- verificações estruturais (ARCHITECTURE §3.1)

def check_part(part: Part, gab: GabBlock | None, n_expected: int | None) -> list[str]:
    issues = []
    nums = [q.numero for q in part.questions]
    if nums != list(range(1, len(nums) + 1)):
        issues.append(f"numeração não contínua: {nums[:5]}...")
    if n_expected and len(nums) != n_expected:
        issues.append(f"{len(nums)} questões extraídas; capa diz {n_expected}")
    bad_alts = [q.numero for q in part.questions if list(q.alts) != list(LETTERS)]
    if bad_alts:
        issues.append(f"{len(bad_alts)} questões sem A–E completas: {bad_alts[:10]}")
    empty = [q.numero for q in part.questions if len(q.enunciado) < 4]   # "O ITR", "O risco" são legítimos
    if empty:
        issues.append(f"{len(empty)} enunciados vazios/curtos: {empty[:10]}")
    leak = [q.numero for q in part.questions for t in q.alternativas().values() if re.search(r"\s\d{1,3}\.\s+[A-Z]", t[-120:] or "")]
    if leak:
        issues.append(f"possível vazamento da questão seguinte em alternativas: {sorted(set(leak))[:10]}")
    if gab is None:
        issues.append("sem bloco de gabarito correspondente")
    else:
        if len(gab.answers) != len(nums):
            issues.append(f"gabarito tem {len(gab.answers)} respostas; prova tem {len(nums)} questões")
        odd = {k: v for k, v in gab.answers.items() if v not in LETTERS}
        if odd:
            issues.append(f"gabarito com valores não A–E (anuladas?): {odd}")
    return issues


# ---------------------------------------------------------------- carga no banco

def _corpus_meta() -> dict[str, dict]:
    with open(ROOT / "corpus" / "candidatos.csv", encoding="utf-8") as f:
        return {r["corpus_id"]: r for r in csv.DictReader(f)}


def _ensure_concurso(conn: sqlite3.Connection, meta: dict) -> int:
    conn.execute("INSERT OR IGNORE INTO banca (sigla, nome) VALUES (?, ?)", (meta["banca"], None))
    banca_id = conn.execute("SELECT id FROM banca WHERE sigla=?", (meta["banca"],)).fetchone()[0]
    conn.execute("INSERT OR IGNORE INTO orgao (sigla, nome, uf, esfera, tipo) VALUES (?,?,?,?,?)",
                 (meta["orgao"], meta["orgao"], meta["uf"], meta["esfera"], meta["orgao_tipo"]))
    orgao_id = conn.execute("SELECT id FROM orgao WHERE sigla=?", (meta["orgao"],)).fetchone()[0]
    nome = f"{meta['orgao']} {meta['ano']}"
    conn.execute("INSERT OR IGNORE INTO concurso (banca_id, orgao_id, ano, nome) VALUES (?,?,?,?)",
                 (banca_id, orgao_id, int(meta["ano"]), nome))
    return conn.execute("SELECT id FROM concurso WHERE banca_id=? AND orgao_id=? AND ano=? AND nome=?",
                        (banca_id, orgao_id, int(meta["ano"]), nome)).fetchone()[0]


def _delete_corpus(conn: sqlite3.Connection, corpus_id: str) -> None:
    ids = [r[0] for r in conn.execute("SELECT id FROM prova WHERE corpus_id=?", (corpus_id,))]
    if not ids:
        return
    qmarks = ",".join("?" * len(ids))
    n_ann = conn.execute(f"SELECT COUNT(*) FROM annotation a JOIN question q ON q.id=a.question_id "
                         f"WHERE q.prova_id IN ({qmarks})", ids).fetchone()[0]
    if n_ann:
        raise RuntimeError(f"{corpus_id}: já há {n_ann} anotações; recarregar apagaria a ligação. Abortado.")
    conn.execute(f"DELETE FROM question_feature WHERE question_id IN (SELECT id FROM question WHERE prova_id IN ({qmarks}))", ids)
    conn.execute(f"DELETE FROM alternative WHERE question_id IN (SELECT id FROM question WHERE prova_id IN ({qmarks}))", ids)
    conn.execute(f"DELETE FROM question WHERE prova_id IN ({qmarks})", ids)
    conn.execute(f"DELETE FROM prova_cargo WHERE prova_id IN ({qmarks})", ids)
    conn.execute(f"DELETE FROM prova WHERE id IN ({qmarks})", ids)


def load_corpus(conn: sqlite3.Connection, corpus_id: str, meta: dict) -> list[str]:
    docs = conn.execute("SELECT id, kind, local_path FROM source_document WHERE corpus_id=? ORDER BY id",
                        (corpus_id,)).fetchall()
    provas = [d for d in docs if d["kind"] == "prova"]
    gabs = [d for d in docs if d["kind"].startswith("gabarito")]
    manual = ROOT / "corpus" / "gabaritos_manuais" / f"{corpus_id}.txt"
    blocks: list[GabBlock] = []
    gab_doc_id, gab_origem = (gabs[0]["id"] if gabs else None), "pdf"
    if manual.exists():
        blocks = parse_gabarito(gabarito_lines(manual))
        gab_origem = str(manual.relative_to(ROOT)).replace("\\", "/")
    else:
        for g in gabs:
            blocks += parse_gabarito(gabarito_lines(RAW / g["local_path"]))

    report: list[str] = []
    with conn:
        _delete_corpus(conn, corpus_id)
        concurso_id = _ensure_concurso(conn, meta)
        part_no = 0
        for d in provas:
            path = RAW / d["local_path"]
            code, tipo, covers = prova_header(path)
            parts = parse_prova(document_lines(str(path)), d["id"])
            matched = match_blocks(parts, blocks, code, tipo)
            for k, (part, gab) in enumerate(zip(parts, matched)):
                part_no += 1
                n_exp = covers[k] if k < len(covers) else None
                issues = check_part(part, gab, n_exp)
                secao = part.secao or (gab.label if gab else None)
                cur = conn.execute(
                    "INSERT INTO prova (concurso_id, corpus_id, parte, secao, caderno_codigo, tipo_caderno, "
                    "n_questoes_esperado, source_document_id, gabarito_document_id, gabarito_origem) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (concurso_id, corpus_id, part_no, secao, code, tipo, n_exp, d["id"], gab_doc_id, gab_origem))
                prova_id = cur.lastrowid
                conn.execute("INSERT INTO prova_cargo (prova_id, cargo_texto) VALUES (?,?)", (prova_id, meta["cargo"]))
                for q in part.questions:
                    alts = q.alternativas()
                    key = f"{slug(meta['banca'])}-{slug(meta['orgao'])}-{meta['ano']}-{corpus_id}-p{part_no}-{q.numero:03d}"
                    h = hashlib.sha256(normalize_for_hash(q.enunciado + " " + " ".join(alts.values())).encode()).hexdigest()
                    resp = gab.answers.get(q.numero) if gab else None
                    status = "anulada" if resp and resp not in LETTERS else "valida"
                    qid = conn.execute(
                        "INSERT INTO question (prova_id, numero, question_key, disciplina_rotulo, texto_base, enunciado, "
                        "gabarito_definitivo, status, text_hash, extraction_method) VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (prova_id, q.numero, key, q.disciplina, q.texto_base, q.enunciado,
                         resp if status == "valida" else None, status, h, f"pdf_text:{PARSER_VERSION}")).lastrowid
                    conn.executemany("INSERT INTO alternative (question_id, letra, texto) VALUES (?,?,?)",
                                     [(qid, letter, txt) for letter, txt in alts.items()])
                discs = sorted({q.disciplina or "?" for q in part.questions})
                status_txt = "OK" if not issues else "PROBLEMAS: " + " | ".join(issues)
                report.append(f"{corpus_id} p{part_no} [{code} tipo {tipo}; seção={secao}] "
                              f"{len(part.questions)} q; gabarito={len(gab.answers) if gab else 0}; "
                              f"{len(discs)} disciplinas -> {status_txt}")
    return report


def main(argv: list[str]) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    conn = connect()
    migrate(conn)
    if argv[:1] == ["load"]:
        meta = _corpus_meta()
        ids = argv[1:] or sorted({r[0] for r in conn.execute(
            "SELECT DISTINCT corpus_id FROM source_document WHERE kind='prova' AND corpus_id IS NOT NULL")})
        for cid in ids:
            try:
                for line in load_corpus(conn, cid, meta[cid]):
                    print(line)
            except Exception as e:  # noqa: BLE001 — um caderno com defeito não deve parar os outros
                print(f"{cid} ERRO: {type(e).__name__}: {e}")
    elif argv[:1] == ["show"] and len(argv) == 3:
        rows = conn.execute(
            "SELECT q.*, p.parte FROM question q JOIN prova p ON p.id=q.prova_id WHERE p.corpus_id=? AND q.numero=?",
            (argv[1], int(argv[2]))).fetchall()
        for r in rows:
            print(f"[{r['question_key']}] disciplina={r['disciplina_rotulo']} gabarito={r['gabarito_definitivo']}")
            if r["texto_base"]:
                print("TEXTO BASE:", r["texto_base"][:300], "...")
            print(r["enunciado"])
            for a in conn.execute("SELECT letra, texto FROM alternative WHERE question_id=? ORDER BY letra", (r["id"],)):
                print(f"  ({a['letra']}) {a['texto']}")
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
