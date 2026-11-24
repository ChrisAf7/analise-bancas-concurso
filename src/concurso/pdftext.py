"""Texto de PDF em ordem de leitura para cadernos em duas colunas (ADR-004: pdfplumber).

Estratégia (decidida no spike de 2026-11-24):
1. Palavras com coordenadas (pdfplumber.extract_words).
2. Uma linha é de LARGURA TOTAL se alguma palavra dela atravessa o centro da página
   (ex.: título de disciplina centralizado, cabeçalho "Caderno de Prova ...").
3. As linhas de largura total dividem a página em faixas horizontais; em cada faixa,
   lê-se a coluna esquerda inteira e depois a direita.
4. Linhas de ruído (marca d'água do PCI com IP e data do download, cabeçalho/rodapé)
   são descartadas AQUI, antes de qualquer outro estágio — nunca chegam ao banco nem a um LLM.

Uso de depuração:  python -m concurso.pdftext <source_document_id> [pagina_inicial] [pagina_final]
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass

import pdfplumber

# Marca d'água injetada pelo PCI em cada download: base64 com IP e data/hora do download (dado pessoal).
_NOISE = [
    re.compile(r"pcimark", re.I),
    re.compile(r"^www\.pciconcursos\.com\.br$", re.I),
    re.compile(r"^Caderno de Prova\s*['’‘]?\s*\w+\s*['’‘]?,?\s*Tipo\s*\d+", re.I),
    re.compile(r"^\d{1,3}$"),                                  # número de página solto
    re.compile(r"^[A-Z][A-Za-z]{1,10}-[\w.\-]+-[A-Z]\d{2}\b"),  # código do caderno no rodapé (ex.: PMSLZ-Aud.Cont.Int-Geral-A01)
    re.compile(r"^[A-Z]{3,}[\w.]*-[\w.\-]+(\s+\d{1,3})?$"),     # rodapé "PMSLA-Conhec.Gerais 1"
    re.compile(r"^\d{1,3}\s+[A-Z]{3,}[\w.]*-[\w.\-]+$"),        # rodapé com número antes
    re.compile(r"^MODELO$"),
]


@dataclass
class Line:
    page: int
    text: str
    full_width: bool
    column: str          # 'F' (largura total), 'L' ou 'R'
    top: float


# Rodapé com código do caderno: "8 SEFAZ-AFRE-Adm.Tributária-CG 1 -P1-S01", "PMSLA-ACI-Abrangência Geral-A01-CE 13"
_FOOTER = re.compile(r"^(\d{1,3}\s+)?[A-Z]{3,}[A-Za-z]*-\S")


_FOOTER_CODE = re.compile(r"^(\d{1,3}\s+)?[A-Z][A-Z0-9]{2,}[A-Za-z0-9]*-(Conhec|Conhecimentos|CG|CE|CB|P\d)", re.I)


def is_noise(text: str) -> bool:
    t = text.strip()
    if not t or any(p.search(t) for p in _NOISE):
        return True
    if len(t.split()) > 7:
        return False
    # "TCEGO-Conhecimentos Gerais 2", "TRT5R-Conhec.Gerais 1 3", "CNMPD-Conhecimentos Básicos 2"
    if _FOOTER_CODE.match(t) and re.search(r"\d$", t):
        return True
    return bool(_FOOTER.match(t)) and t.count("-") >= 2


def _group_lines(words: list[dict], tol: float = 3.0) -> list[list[dict]]:
    words = sorted(words, key=lambda w: (round(w["top"]), w["x0"]))
    lines: list[list[dict]] = []
    for w in words:
        if lines and abs(lines[-1][0]["top"] - w["top"]) <= tol:
            lines[-1].append(w)
        else:
            lines.append([w])
    return [sorted(l, key=lambda w: w["x0"]) for l in lines]


def _join(words: list[dict]) -> str:
    if len(words) > 1 and _FOOTER_WORD.match(words[0]["text"]):
        words = words[1:]
    return " ".join(w["text"] for w in words)


GUTTER_MIN = 10.0   # pt: vão mínimo no centro para considerar que a linha tem duas colunas

# Palavras de ruído removidas ANTES de montar as linhas: o rodapé do PCI às vezes cai na mesma linha
# do texto da questão. Inclui a marca d'água (IP e data do download em base64) e artefatos "(cid:N)".
_NOISE_WORD = re.compile(r"pciconcursos|pcimark|\(cid:\d+\)|^[A-Za-z0-9+/]{30,}={0,2}(:[A-Za-z0-9+/]+=*)?$", re.I)
# Código de rodapé colado no início de um título na mesma linha ("PMSLA-Conhec.Gerais1 Administração ...").
# Só "-Conhec…" e só como PRIMEIRA palavra da linha: siglas reais como "TCE-CE" não podem casar (bug corrigido em 2026-11-24).
_FOOTER_WORD = re.compile(r"^[A-Z][A-Z0-9]{2,}-Conhec\S*$")


def _spans_center(row: list[dict], mid: float) -> bool:
    """Linha atravessa o centro: uma palavra cruza o meio, ou o vão no meio é só espaço entre palavras.

    Separadores '____' são ignorados: na coluna direita eles começam alguns pontos à esquerda do centro.
    """
    row = [w for w in row if not re.fullmatch(r"_+", w["text"])]
    if any(w["x0"] < mid - 2 and w["x1"] > mid + 2 for w in row):
        return True
    left = [w for w in row if w["x1"] <= mid]
    right = [w for w in row if w["x0"] >= mid]
    if left and right:
        return min(w["x0"] for w in right) - max(w["x1"] for w in left) < GUTTER_MIN
    return False


def page_lines(page, page_no: int) -> list[Line]:
    mid = page.width / 2
    words = page.extract_words(keep_blank_chars=False, use_text_flow=False, x_tolerance=1.5, y_tolerance=2)
    words = [w for w in words if not _NOISE_WORD.search(w["text"])]
    rows = _group_lines(words)
    both_sides = [r for r in rows if any(w["x1"] <= mid for w in r) and any(w["x0"] >= mid for w in r)]
    spanning = [r for r in rows if _spans_center(r, mid)]
    single_column = bool(both_sides) and len([r for r in both_sides if _spans_center(r, mid)]) / len(both_sides) > 0.5
    if single_column:   # página em coluna única: todas as linhas na ordem natural
        spanning = rows
    full_set = {round(r[0]["top"]) for r in spanning}

    out: list[Line] = []
    band_words = {"L": [], "R": []}

    def flush():
        for col in ("L", "R"):
            for row in _group_lines(band_words[col]):
                if is_noise(" ".join(w["text"] for w in row)):   # testa a linha INTEIRA antes de limpar o código
                    continue
                out.append(Line(page_no, _join(row), False, col, row[0]["top"]))
            band_words[col] = []

    for row in rows:
        if round(row[0]["top"]) in full_set:
            flush()
            if not is_noise(" ".join(w["text"] for w in row)):
                out.append(Line(page_no, _join(row), True, "F", row[0]["top"]))
        else:
            for w in row:
                band_words["L" if (w["x0"] + w["x1"]) / 2 < mid else "R"].append(w)
    flush()
    return out


def document_lines(path: str, first: int = 1, last: int | None = None) -> list[Line]:
    lines: list[Line] = []
    with pdfplumber.open(path) as pdf:
        n = len(pdf.pages)
        for i in range(first - 1, min(last or n, n)):
            lines.extend(page_lines(pdf.pages[i], i + 1))
    return lines


if __name__ == "__main__":
    import sqlite3

    from .config import DB_PATH, RAW

    sys.stdout.reconfigure(encoding="utf-8")
    sid = int(sys.argv[1])
    a = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    b = int(sys.argv[3]) if len(sys.argv) > 3 else None
    lp = sqlite3.connect(DB_PATH).execute("SELECT local_path FROM source_document WHERE id=?", (sid,)).fetchone()[0]
    for ln in document_lines(str(RAW / lp), a, b):
        print(f"p{ln.page:02d} {ln.column} | {ln.text}")
