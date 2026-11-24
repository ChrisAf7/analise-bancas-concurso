"""Features derivadas por regra (DATA_MODEL §4.2). Determinísticas, versionadas e regeneráveis.

Tabela question_feature em formato longo: (question_id, alternativa, name, value_num, value_text).
alternativa = '' → feature da questão; 'A'..'E' → feature da alternativa.

Uso:  python -m concurso.features build      # apaga e recalcula tudo (EXTRACTOR_VERSION)
"""
from __future__ import annotations

import re
import sqlite3
import sys

from .db import connect, migrate

EXTRACTOR_VERSION = "feat-0.1"

# --- vocabulário (tudo testado em tests/test_features.py) -----------------------------------
RE_NEG_CMD = re.compile(r"\b(INCORRET[AO]S?|EXCETO|ERRAD[AO]S?|NÃO|N Ã O)\b|\bincorret[ao]s?\b")
RE_ROMAN_ITEM = re.compile(r"(?:^|\s)(I{1,3}|IV|V|VI{0,3}|IX|X)\s?[.\-–)]\s+(?=\S)")
RE_COMBO_ALT = re.compile(r"^(I{1,3}|IV|V|VI{0,3})(\s*,\s*(I{1,3}|IV|V|VI{0,3}))*\s*(e\s+(I{1,3}|IV|V|VI{0,3}))?\s*,?\s*(apenas|somente)?\.?$")
RE_VF_ALT = re.compile(r"^[VF](\s*[–\-,/]?\s*[VF]){2,}\.?$")
RE_NUMERIC_ALT = re.compile(r"^(R\$\s*)?[\d.,]+\s*(%|reais|dias|anos|meses)?\.?(\s*\((positivo|negativo)\))?$", re.I)
RE_DATE = re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b|\b\d{1,2}\s+de\s+(janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\b", re.I)
RE_MONEY = re.compile(r"R\$\s*[\d.]")
RE_PERCENT = re.compile(r"\d\s*%")
RE_NUMBER = re.compile(r"\b\d+[\d.,]*\b")
RE_DISPOSITIVO = re.compile(r"\bart(igo)?s?\.?\s*\d|§|\bincisos?\b|\bLei\s+(Complementar\s+)?(n[ºo°.]?\s*)?\d|\bDecreto\b|\bEmenda Constitucional\b|\bConstituição\b", re.I)
RE_TRIBUNAL = re.compile(r"\b(STF|STJ|TST|TSE|TCU|Supremo Tribunal|Superior Tribunal|Súmula|súmula|jurisprudência|entendimento (do|dos) (Tribunais|Tribunal))\b")
RE_CENARIO_FORTE = re.compile(r"situação hipotética|hipoteticamente|Considere a seguinte situação|caso concreto", re.I)
RE_DETERMINADO = re.compile(r"\bdeterminad[oa]s?\s+(Município|Estado|órgão|servidor|servidora|empresa|autarquia|entidade|agente|cidadão|particular|sociedade|Prefeit|Secretaria|fundação)", re.I)
RE_NOME_PROPRIO = re.compile(r"(?<![.!?]\s)(?<!^)\b[A-Z][a-zà-ú]{2,}\b(?=,?\s+(servidor|servidora|auditor|auditora|analista|técnic|prefeit|secretári|empresári|contribuinte|cidadã|cidadão|agente|ocupante|que|foi|é|era|praticou|ajuizou|celebrou|recebeu|solicitou|requereu|apresentou|deixou))")
RE_ABSOLUTO = re.compile(r"\b(sempre|nunca|jamais|somente|exclusivamente|unicamente|qualquer hipótese|em nenhuma hipótese|todos|todas|nenhum|nenhuma|obrigatoriamente|necessariamente|independentemente)\b", re.I)
RE_NAO = re.compile(r"\bnão\b", re.I)


def words(s: str) -> int:
    return len(re.findall(r"\w+", s or ""))


def comando_tipo(enunciado: str, alts: dict[str, str]) -> str:
    stem = enunciado.strip()
    tail = stem[-220:]
    if sum(bool(RE_VF_ALT.match(a.strip())) for a in alts.values()) >= 4:
        return "sequencia_VF"
    if sum(bool(RE_COMBO_ALT.match(a.strip())) for a in alts.values()) >= 4:
        return "assertivas_combinadas"
    if re.search(r"associ|correlaç|relacione|correspond[ae]m? corretamente|coluna", tail, re.I):
        return "associacao"
    if re.search(r"lacuna|preenche[mr]?\s+corretamente|completa[mr]?\s+corretamente", tail, re.I):
        return "completar_lacunas"
    if re.search(r"\b(INCORRET|EXCETO|ERRAD)", tail) or re.search(r"\bincorret", tail):
        return "assinale_incorreta"
    if re.search(r"corret[ao]|verdadeir|adequad|está de acordo|em conformidade|de acordo com", tail, re.I) and stem[-1:] in ":?.":
        return "assinale_correta"
    if stem[-1:] not in ".?:":
        return "completar_frase"          # enunciado termina "em aberto"; as alternativas completam a frase
    return "outro"


def formato_alternativas(alts: dict[str, str]) -> str:
    vals = [a.strip() for a in alts.values()]
    if sum(bool(RE_VF_ALT.match(v)) for v in vals) >= 4:
        return "sequencia_VF"
    if sum(bool(RE_COMBO_ALT.match(v)) for v in vals) >= 4:
        return "assertivas_combinadas"
    if sum(bool(RE_NUMERIC_ALT.match(v)) for v in vals) >= 4:
        return "numerica"
    return "texto"


def question_features(enunciado: str, texto_base: str | None, alts: dict[str, str], gabarito: str | None) -> list[tuple]:
    """Retorna [(alternativa, name, value_num, value_text)]."""
    f: list[tuple] = []
    add = lambda name, num=None, txt=None, alt="": f.append((alt, name, num, txt))  # noqa: E731
    stem = enunciado or ""
    alt_words = {k: words(v) for k, v in alts.items()}
    full = stem + " " + " ".join(alts.values())

    add("n_palavras_enunciado", words(stem))
    add("n_palavras_texto_base", words(texto_base) if texto_base else 0)
    add("n_palavras_alt_media", round(sum(alt_words.values()) / max(len(alt_words), 1), 2))
    add("n_palavras_alt_max", max(alt_words.values(), default=0))
    add("n_palavras_alt_min", min(alt_words.values(), default=0))
    add("comando_polaridade", txt="negativo" if RE_NEG_CMD.search(stem[-220:]) else "positivo")
    add("comando_tipo", txt=comando_tipo(stem, alts))
    add("formato_alternativas", txt=formato_alternativas(alts))
    add("n_assertivas", len(set(RE_ROMAN_ITEM.findall(stem))))
    add("tem_data", int(bool(RE_DATE.search(stem))))
    add("tem_valor_monetario", int(bool(RE_MONEY.search(full))))
    add("tem_percentual", int(bool(RE_PERCENT.search(full))))
    add("tem_numero", int(bool(RE_NUMBER.search(stem))))
    add("cita_dispositivo", int(bool(RE_DISPOSITIVO.search(stem))))
    add("cita_tribunal", int(bool(RE_TRIBUNAL.search(full))))
    add("cenario_marcador_forte", int(bool(RE_CENARIO_FORTE.search(stem))))   # âncora de alta precisão (V2)
    add("menciona_determinado", int(bool(RE_DETERMINADO.search(stem))))
    add("tem_nome_proprio_agente", int(bool(RE_NOME_PROPRIO.search(stem))))

    for k, v in alts.items():
        add("n_palavras", alt_words[k], alt=k)
        add("tem_absoluto", int(bool(RE_ABSOLUTO.search(v))), alt=k)
        add("n_nao", len(RE_NAO.findall(v)), alt=k)

    if gabarito and gabarito in alts:
        add("posicao_correta", txt=gabarito)
        lens = sorted(alt_words.values(), reverse=True)
        c = alt_words[gabarito]
        add("correta_e_mais_longa", int(c == lens[0] and lens.count(c) == 1))
        add("rank_comprimento_correta", 1 + sum(1 for x in alt_words.values() if x > c))
        add("correta_tem_absoluto", int(bool(RE_ABSOLUTO.search(alts[gabarito]))))
        wrong = [k for k in alts if k != gabarito]
        add("frac_incorretas_com_absoluto", round(sum(bool(RE_ABSOLUTO.search(alts[k])) for k in wrong) / len(wrong), 3))
    return f


def build(conn: sqlite3.Connection) -> int:
    alts_by_q: dict[int, dict[str, str]] = {}
    for qid, letra, texto in conn.execute("SELECT question_id, letra, texto FROM alternative"):
        alts_by_q.setdefault(qid, {})[letra] = texto
    rows = []
    for qid, enun, tb, gab in conn.execute("SELECT id, enunciado, texto_base, gabarito_definitivo FROM question"):
        for alt, name, num, txt in question_features(enun, tb, alts_by_q.get(qid, {}), gab):
            rows.append((qid, alt, name, num, txt, EXTRACTOR_VERSION))
    with conn:
        conn.execute("DELETE FROM question_feature")
        conn.executemany("INSERT INTO question_feature (question_id, alternativa, name, value_num, value_text, "
                         "extractor_version) VALUES (?,?,?,?,?,?)", rows)
    return len(rows)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if sys.argv[1:] == ["build"]:
        c = connect()
        migrate(c)
        print(f"{build(c)} features gravadas ({EXTRACTOR_VERSION})")
    else:
        print(__doc__)
