"""Validação (ARCHITECTURE §5) e relatório do MVP (ANALYSIS). Todo número vem daqui, de código sobre o banco.

Saídas:
  reports/mvp_v0.md                        — público: só agregados, sem texto de questão (ADR-013)
  exports/annotations/mvp_v0.jsonl         — público: rótulos por question_key, sem evidência/justificativa
  data/work/divergencias_mvp_v0.md         — LOCAL: amostra de discordâncias com texto, para auditoria (V6)

Uso:  python -m concurso.report
"""
from __future__ import annotations

import json
import random
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import date

from .classify import CODEBOOK_VERSION, SCOPE_SQL
from .config import ROOT, WORK
from .db import connect, migrate
from .stats import binom_two_sided_p, chi2_uniform_df4, cluster_bootstrap_prop, cohen_kappa, fmt_pct, group

SINGLE = ["cenario", "demanda_cognitiva", "teoria_x_aplicacao", "topico"]
# teoria_x_aplicacao: RECODIFICAÇÃO determinística de demanda_cognitiva (ADR-022): aplicar_a_fatos -> aplicacao;
# recordar_texto/reconhecer_conceito/calcular_ou_contar -> teoria. Responde Q1 sem nova chamada a modelo.
def _tx(v):
    return None if v is None else ("aplicacao" if v == "aplicar_a_fatos" else "teoria")
FONTES = ["lei", "constituicao", "jurisprudencia", "sumula", "doutrina", "indeterminada"]


# ------------------------------------------------------------------ carga dos rótulos

def load_labels(conn: sqlite3.Connection) -> dict:
    """labels[rater][rep][qid] = {'cenario': v, 'demanda_cognitiva': v, 'topico': v, 'fonte_normativa': frozenset}"""
    out: dict = defaultdict(lambda: defaultdict(dict))
    runs = conn.execute("SELECT id, annotator_id, repeticao FROM annotation_run WHERE annotator_type='llm' "
                        "AND codebook_version=? AND purpose='producao'", (CODEBOOK_VERSION,)).fetchall()
    for run_id, annot, rep in runs:
        rater = annot.split(":")[0]
        acc: dict = defaultdict(lambda: {"fonte_normativa": set()})
        for qid, campo, valor in conn.execute("SELECT question_id, campo, valor FROM annotation WHERE run_id=?", (run_id,)):
            if campo == "fonte_normativa":
                acc[qid]["fonte_normativa"].add(valor)
            else:
                acc[qid][campo] = valor
        for qid, d in acc.items():
            d["fonte_normativa"] = frozenset(d["fonte_normativa"])
            d["teoria_x_aplicacao"] = _tx(d.get("demanda_cognitiva"))
            out[rater][rep][qid] = d
    return out


def model_consensus(reps: dict) -> dict:
    """Rótulo do modelo = valor se as 2 repetições concordam; senão None (instável)."""
    r1, r2 = reps.get(1, {}), reps.get(2, {})
    out = {}
    for qid in set(r1) | set(r2):
        a, b = r1.get(qid), r2.get(qid)
        if a is None or b is None:
            out[qid] = a or b if not r2 else None   # só há uma repetição: usa ela (marcado no relatório)
            continue
        out[qid] = {k: (a[k] if a.get(k) == b.get(k) else None) for k in a}
    return out


def resolved(ca: dict, cb: dict) -> dict:
    """Consenso entre modelos (A e B estáveis e iguais); senão None. Fonte: por rótulo binário."""
    out = {}
    for qid in set(ca) & set(cb):
        a, b = ca[qid] or {}, cb[qid] or {}
        d = {k: (a.get(k) if a.get(k) is not None and a.get(k) == b.get(k) else None) for k in SINGLE}
        fa, fb = a.get("fonte_normativa"), b.get("fonte_normativa")
        d["fonte_normativa"] = {f: ((f in fa) if fa is not None and fb is not None and (f in fa) == (f in fb) else None)
                                for f in FONTES}
        out[qid] = d
    return out


# ------------------------------------------------------------------ relatório

def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    conn = connect()
    migrate(conn)
    scope = {r["id"]: r for r in conn.execute(SCOPE_SQL)}
    meta = {r["id"]: dict(r) for r in conn.execute(
        "SELECT q.id, q.question_key, q.prova_id, q.disciplina_rotulo, p.corpus_id FROM question q JOIN prova p ON p.id=q.prova_id")}
    feats: dict = defaultdict(dict)
    for qid, alt, name, num, txt in conn.execute("SELECT question_id, alternativa, name, value_num, value_text FROM question_feature WHERE alternativa=''"):
        feats[qid][name] = txt if txt is not None else num
    labels = load_labels(conn)
    raters = sorted(labels)
    cons = {r: model_consensus(labels[r]) for r in raters}
    L: list[str] = []
    w = L.append

    w(f"# Relatório do MVP — perfil estrutural da FCC em Direito Administrativo (codebook {CODEBOOK_VERSION})\n")
    w(f"Gerado por `python -m concurso.report` em {date.today().isoformat()}. Todos os números vêm de código sobre o banco; "
      "nenhum foi produzido por IA. Intervalos: 95%, bootstrap reamostrando **cadernos** (não questões).\n")
    incompletos = [r for r in conn.execute("SELECT r.annotator_id, r.repeticao, COUNT(DISTINCT a.question_id) FROM annotation_run r "
                   "LEFT JOIN annotation a ON a.run_id=r.id WHERE r.codebook_version=? GROUP BY r.id", (CODEBOOK_VERSION,))
                   if len(set(q for (q,) in conn.execute("SELECT DISTINCT question_id FROM annotation a JOIN annotation_run rr ON rr.id=a.run_id "
                   "WHERE rr.annotator_id=? AND rr.repeticao=?", (r[0], r[1]))) & set(scope)) < len(scope)]
    if incompletos:
        w("> ⚠️ **RELATÓRIO PARCIAL:** execuções incompletas: " + ", ".join(f"{a} rep{b}" for a, b, _ in incompletos)
          + ". Rode `python -m concurso.classify run <avaliador> <rep>` e gere de novo.\n")
    w("> **Limitação central (ADR-012):** não há rótulo humano. Concordância entre modelos mede *confiabilidade*, não "
      "*validade*: dois modelos podem errar juntos. As conclusões abaixo só são afirmadas quando robustas aos dois modelos.\n")

    # --- corpus
    w("## 1. Corpus\n")
    rows = conn.execute("SELECT p.corpus_id, COUNT(*) FROM question q JOIN prova p ON p.id=q.prova_id GROUP BY 1 ORDER BY 1").fetchall()
    w(f"- {sum(n for _, n in rows)} questões extraídas de {len(rows)} cadernos FCC (2013–2018 + 1 de 2022); lista em `corpus/candidatos.csv`.")
    w(f"- Escopo da classificação por IA (ADR-018): {len(scope)} questões (Direito Administrativo + 40 sem título do C10).\n")

    # --- execução
    w("## 2. Execução dos avaliadores\n")
    w("| Run | Avaliador (modelo informado pelo provedor) | Repetição | Questões rotuladas |")
    w("|---|---|---|---|")
    for r in conn.execute("SELECT r.id, r.annotator_id, r.model_reported, r.repeticao, COUNT(DISTINCT a.question_id) "
                          "FROM annotation_run r LEFT JOIN annotation a ON a.run_id=r.id WHERE r.codebook_version=? "
                          "GROUP BY r.id ORDER BY r.id", (CODEBOOK_VERSION,)):
        w(f"| {r[0]} | {r[1]} ({r[2]}) | {r[3]} | {r[4]}/{len(scope)} |")
    w("")

    # --- V4 estabilidade
    w("## 3. Validação\n")
    w("### V4 — Estabilidade (mesmo modelo, 2 execuções)\n")
    w("| Avaliador | " + " | ".join(SINGLE + ["fonte_normativa (conjunto)"]) + " |")
    w("|---|" + "---|" * (len(SINGLE) + 1))
    for r in raters:
        r1, r2 = labels[r].get(1, {}), labels[r].get(2, {})
        both = set(r1) & set(r2)
        cells = []
        for k in SINGLE + ["fonte_normativa"]:
            if not both:
                cells.append("—")
                continue
            agree = sum(r1[q].get(k) == r2[q].get(k) for q in both) / len(both)
            cells.append(f"{100 * agree:.0f}% (troca {100 * (1 - agree):.0f}%)")
        w(f"| {r} (n={len(both)}) | " + " | ".join(cells) + " |")
    w("\nLimiar do projeto: troca ≤ 10% por variável.\n")

    # --- V3 entre modelos
    w("### V3 — Concordância entre modelos (κ de Cohen, rótulos estáveis de cada modelo)\n")
    kappas = {}
    if len(raters) >= 2:
        a, b = raters[0], raters[1]
        w(f"Modelos comparados: **{a}** × **{b}**.\n")
        w("| Variável | n | concordância | κ | uso (limiares do projeto) |")
        w("|---|---|---|---|---|")
        items = [(k, None) for k in SINGLE] + [("fonte_normativa", f) for f in FONTES if f != "indeterminada"]
        for k, f in items:
            pairs = []
            for qid in set(cons[a]) & set(cons[b]):
                x, y = cons[a][qid], cons[b][qid]
                if not x or not y:
                    continue
                if f is None:
                    if x.get(k) is not None and y.get(k) is not None:
                        pairs.append((x[k], y[k]))
                else:
                    if x.get(k) is not None and y.get(k) is not None:
                        pairs.append((f in x[k], f in y[k]))
            kap = cohen_kappa(pairs)
            name = k if f is None else f"fonte: {f}"
            kappas[name] = kap
            use = "—" if kap is None else ("usar" if kap >= 0.7 else "só exploratório" if kap >= 0.5 else "não usar / redefinir")
            agree = (sum(x == y for x, y in pairs) / len(pairs)) if pairs else float("nan")
            w(f"| {name} | {len(pairs)} | {fmt_pct(agree)} | {'—' if kap is None else f'{kap:.2f}'} | {use} |")
        w("")

    res = resolved(cons[raters[0]], cons[raters[1]]) if len(raters) >= 2 else {}

    # --- V2 âncoras
    w("### V2 — Âncoras por regra (casos em que uma regex dá a resposta quase certa)\n")
    w("| Âncora (regra → rótulo esperado) | n | " + " | ".join(f"acerto {r}" for r in raters) + " |")
    w("|---|---|" + "---|" * len(raters))
    anchors = [
        ("'situação hipotética'/'caso concreto' → cenario_hipotetico", lambda q: feats[q].get("cenario_marcador_forte") == 1,
         lambda d: d.get("cenario") == "cenario_hipotetico"),
        ("nome próprio de agente no enunciado → cenario_hipotetico", lambda q: feats[q].get("tem_nome_proprio_agente") == 1,
         lambda d: d.get("cenario") == "cenario_hipotetico"),
        ("enunciado invoca entendimento de tribunal/súmula → fonte inclui jurisprudencia ou sumula",
         lambda q: feats[q].get("cita_jurisprudencia_explicita") == 1,
         lambda d: bool(d.get("fonte_normativa", set()) & {"jurisprudencia", "sumula"})),
        ("título do caderno = Direito Administrativo → topico ≠ nao_dir_adm",
         lambda q: "Direito Administrativo" in (meta[q]["disciplina_rotulo"] or ""), lambda d: d.get("topico") not in (None, "nao_dir_adm")),
    ]
    for name, sel, ok in anchors:
        qs = [q for q in scope if sel(q)]
        cells = []
        for r in raters:
            vals = [ok(labels[r][1][q]) for q in qs if q in labels[r].get(1, {})]
            cells.append(f"{fmt_pct(sum(vals) / len(vals))} ({sum(vals)}/{len(vals)})" if vals else "—")
        w(f"| {name} | {len(qs)} | " + " | ".join(cells) + " |")
    w("\nLimiar: ≥ 95%. Âncoras são fáceis por construção: passar é necessário, não suficiente.\n")

    # --- escopo final Dir. Adm.
    dir_adm = [q for q in scope if "Direito Administrativo" in (meta[q]["disciplina_rotulo"] or "")
               or (res.get(q, {}).get("topico") not in (None, "nao_dir_adm"))]
    c10_in = [q for q in scope if meta[q]["corpus_id"] == "C10" and q in dir_adm]
    w("## 4. Resultados — Direito Administrativo\n")
    w(f"Universo: **{len(dir_adm)} questões** ({len(dir_adm) - len(c10_in)} pelo título do caderno + {len(c10_in)} do C10 "
      f"que os dois modelos classificaram como Direito Administrativo), em "
      f"{len({meta[q]['prova_id'] for q in dir_adm})} cadernos.\n")

    def prop_table(title: str, variable: str, values: list[str], kappa_key: str):
        w(f"### {title}\n")
        w(f"κ entre modelos: {'—' if kappas.get(kappa_key) is None else f'{kappas[kappa_key]:.2f}'}. "
          "Colunas A e B: rótulo estável de cada modelo; Consenso: só onde A e B concordam.\n")
        w("| Valor | " + " | ".join(raters) + " | Consenso | robusto? |")
        w("|---|" + "---|" * (len(raters) + 2))
        for v in values:
            cells, ps = [], []
            for src in raters + ["consenso"]:
                lab = cons[src] if src != "consenso" else res
                rows_ = [(meta[q]["prova_id"], int(lab[q][variable] == v)) for q in dir_adm
                         if q in lab and lab[q] and lab[q].get(variable) is not None]
                p, lo, hi, n, k = cluster_bootstrap_prop(group(rows_))
                ps.append(p)
                cells.append(f"{fmt_pct(p, lo, hi)} n={n}")
            robust = "sim" if len(ps) >= 3 and abs(ps[0] - ps[1]) < 0.10 else "não (modelos divergem ≥10 p.p.)"
            w(f"| {v} | " + " | ".join(cells) + f" | {robust} |")
        excl = sum(1 for q in dir_adm if not (q in res and res[q].get(variable) is not None))
        w(f"\nSem consenso (fora da coluna Consenso): {excl}/{len(dir_adm)}.\n")

    prop_table("4.1 Cenário (Q1, Q2)", "cenario", ["sem_cenario", "cenario_hipotetico"], "cenario")
    prop_table("4.2a Teoria × aplicação (Q1) — recodificação binária da demanda", "teoria_x_aplicacao",
               ["teoria", "aplicacao"], "teoria_x_aplicacao")
    prop_table("4.2 Demanda cognitiva (Q1)", "demanda_cognitiva",
               ["recordar_texto", "reconhecer_conceito", "aplicar_a_fatos", "calcular_ou_contar"], "demanda_cognitiva")

    # cruzamento cenário × demanda (H-001)
    w("### 4.3 Cenário × demanda — o “cenário decorativo” (H-001)\n")
    both = [q for q in dir_adm if q in res and res[q]["cenario"] and res[q]["demanda_cognitiva"]]
    tab = Counter((res[q]["cenario"], res[q]["demanda_cognitiva"]) for q in both)
    dems = ["recordar_texto", "reconhecer_conceito", "aplicar_a_fatos", "calcular_ou_contar"]
    w("| | " + " | ".join(dems) + " | total |")
    w("|---|" + "---|" * (len(dems) + 1))
    for cen in ["sem_cenario", "cenario_hipotetico"]:
        tot = sum(tab[(cen, d)] for d in dems)
        w(f"| {cen} | " + " | ".join(str(tab[(cen, d)]) for d in dems) + f" | {tot} |")
    cen_q = [q for q in both if res[q]["cenario"] == "cenario_hipotetico"]
    rows_ = [(meta[q]["prova_id"], int(res[q]["demanda_cognitiva"] != "aplicar_a_fatos")) for q in cen_q]
    p, lo, hi, n, k = cluster_bootstrap_prop(group(rows_))
    w(f"\nEntre as questões **com cenário** (consenso), a fração que **não exige aplicar os fatos** (cenário decorativo): "
      f"**{fmt_pct(p, lo, hi)}** (n={n}, {k} cadernos). H-001 previa > 50%.\n")
    w("> ⚠️ **Viés de seleção do consenso:** os casos decorativos são justamente os de fronteira, em que os modelos "
      "mais discordam; restringir ao consenso tende a SUBESTIMAR o cenário decorativo. Por isso, a estimativa por modelo "
      "(cada um com seus rótulos estáveis) é a referência:\n")
    for src in raters:
        lab = cons[src]
        cq = [q for q in dir_adm if q in lab and lab[q] and lab[q].get("cenario") == "cenario_hipotetico"
              and lab[q].get("demanda_cognitiva") is not None]
        rows_ = [(meta[q]["prova_id"], int(lab[q]["demanda_cognitiva"] != "aplicar_a_fatos")) for q in cq]
        p, lo, hi, n, k = cluster_bootstrap_prop(group(rows_))
        w(f"- Avaliador {src}: cenário decorativo em **{fmt_pct(p, lo, hi)}** das questões com cenário (n={n}).")
    w("")

    # fonte normativa
    w("### 4.4 Fonte normativa da alternativa correta (Q6)\n")
    w("| Fonte | " + " | ".join(raters) + " | Consenso | κ |")
    w("|---|" + "---|" * (len(raters) + 2))
    for f in FONTES:
        cells = []
        for src in raters:
            rows_ = [(meta[q]["prova_id"], int(f in cons[src][q]["fonte_normativa"])) for q in dir_adm
                     if q in cons[src] and cons[src][q] and cons[src][q].get("fonte_normativa") is not None]
            p, lo, hi, n, k = cluster_bootstrap_prop(group(rows_))
            cells.append(f"{fmt_pct(p, lo, hi)} n={n}")
        rows_ = [(meta[q]["prova_id"], int(res[q]["fonte_normativa"][f])) for q in dir_adm
                 if q in res and res[q]["fonte_normativa"].get(f) is not None]
        p, lo, hi, n, k = cluster_bootstrap_prop(group(rows_))
        kk = kappas.get(f"fonte: {f}")
        w(f"| {f} | " + " | ".join(cells) + f" | {fmt_pct(p, lo, hi)} n={n} | {'—' if kk is None else f'{kk:.2f}'} |")
    w("")

    # tópicos
    w("### 4.5 Incidência por tópico (consenso)\n")
    tops = Counter(res[q]["topico"] for q in dir_adm if q in res and res[q].get("topico"))
    tot = sum(tops.values())
    w("| Tópico | n | % |")
    w("|---|---|---|")
    for t, n in tops.most_common():
        w(f"| {t} | {n} | {100 * n / tot:.0f}% |")
    w(f"\nSem consenso de tópico: {len(dir_adm) - tot}/{len(dir_adm)}.\n")

    # --- derivados (sem IA)
    w("## 5. Resultados por regra (sem IA) — corpus inteiro e Direito Administrativo\n")
    allq = list(meta)
    for title, qs in (("Todas as questões", allq), ("Direito Administrativo", dir_adm)):
        w(f"### {title} (n={len(qs)})\n")
        for name, vals in (("comando_tipo", None), ("comando_polaridade", None), ("formato_alternativas", None)):
            cnt = Counter(feats[q].get(name) for q in qs)
            w(f"- **{name}**: " + ", ".join(f"{v} {100 * n / len(qs):.0f}%" for v, n in cnt.most_common()))
        rows_ = [(meta[q]["prova_id"], int(feats[q].get("comando_polaridade") == "negativo")) for q in qs]
        p, lo, hi, n, k = cluster_bootstrap_prop(group(rows_))
        w(f"- comando negativo (INCORRETA/EXCETO/NÃO): {fmt_pct(p, lo, hi)}")
        w("")
    # H-002 e H-004 no corpus inteiro
    w("### H-002 — A alternativa correta é a mais longa?\n")
    uniq = [q for q in allq if feats[q].get("rank_comprimento_correta") is not None]
    # considera só questões em que existe uma única alternativa mais longa
    alt_len: dict = defaultdict(dict)
    for qid, alt, num in conn.execute("SELECT question_id, alternativa, value_num FROM question_feature WHERE name='n_palavras' AND alternativa<>''"):
        alt_len[qid][alt] = num
    elig = [q for q in uniq if q in alt_len and sorted(alt_len[q].values(), reverse=True)[0] > sorted(alt_len[q].values(), reverse=True)[1]]
    k_obs = sum(int(feats[q]["correta_e_mais_longa"]) for q in elig)
    rows_ = [(meta[q]["prova_id"], int(feats[q]["correta_e_mais_longa"])) for q in elig]
    p, lo, hi, n, kcl = cluster_bootstrap_prop(group(rows_))
    w(f"Questões com uma única alternativa mais longa: {len(elig)}. A correta é a mais longa em **{fmt_pct(p, lo, hi)}** "
      f"({k_obs}/{len(elig)}); acaso = 20%. Teste binomial exato bilateral p = {binom_two_sided_p(k_obs, len(elig), 0.2):.2g} "
      "(assume independência; o IC por cadernos é a referência).\n")
    w("### H-004 — As letras do gabarito são equilibradas?\n")
    pos = Counter(feats[q].get("posicao_correta") for q in allq if feats[q].get("posicao_correta"))
    x, pv = chi2_uniform_df4([pos[c] for c in "ABCDE"])
    w("| A | B | C | D | E |\n|---|---|---|---|---|\n| " + " | ".join(str(pos[c]) for c in "ABCDE") + " |")
    w(f"\nχ² de uniformidade = {x:.2f} (gl=4), p = {pv:.2g}.\n")

    # --- export público de rótulos
    exp = ROOT / "exports" / "annotations"
    exp.mkdir(parents=True, exist_ok=True)
    with open(exp / f"mvp_{CODEBOOK_VERSION}.jsonl", "w", encoding="utf-8") as f:
        for r in raters:
            for rep, d in labels[r].items():
                for qid, lab in sorted(d.items()):
                    f.write(json.dumps({"question_key": meta[qid]["question_key"], "avaliador": r, "repeticao": rep,
                                        "cenario": lab.get("cenario"), "demanda_cognitiva": lab.get("demanda_cognitiva"),
                                        "topico": lab.get("topico"), "fonte_normativa": sorted(lab.get("fonte_normativa", []))},
                                       ensure_ascii=False) + "\n")

    # --- V6: amostra local de divergências (texto das questões → só em data/work)
    if len(raters) >= 2:
        a, b = raters[0], raters[1]
        div = [q for q in dir_adm if q in labels[a].get(1, {}) and q in labels[b].get(1, {})
               and labels[a][1][q].get("demanda_cognitiva") != labels[b][1][q].get("demanda_cognitiva")]
        random.Random(7).shuffle(div)
        with open(WORK / f"divergencias_mvp_{CODEBOOK_VERSION}.md", "w", encoding="utf-8") as f:
            for q in div[:30]:
                row = conn.execute("SELECT enunciado, gabarito_definitivo FROM question WHERE id=?", (q,)).fetchone()
                alts = {x["letra"]: x["texto"] for x in conn.execute("SELECT letra, texto FROM alternative WHERE question_id=?", (q,))}
                f.write(f"## q{q} {meta[q]['question_key']}\n{row[0]}\n")
                for k_, v_ in sorted(alts.items()):
                    f.write(f"- ({k_}) {v_}\n")
                f.write(f"\nGabarito: {row[1]}\n")
                for r in (a, b):
                    d = labels[r][1][q]
                    f.write(f"- **{r}**: cenario={d.get('cenario')} demanda={d.get('demanda_cognitiva')} fonte={sorted(d.get('fonte_normativa', []))} topico={d.get('topico')}\n")
                f.write("\n")
        w(f"## 6. Auditoria qualitativa (V6)\n\n{len(div)} questões com demanda_cognitiva divergente na repetição 1; "
          f"amostra local (com texto, fora do git) em `data/work/divergencias_mvp_{CODEBOOK_VERSION}.md`.\n")

    out = ROOT / "reports" / f"mvp_{CODEBOOK_VERSION}.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(L), encoding="utf-8")
    print(f"relatório: {out}")


if __name__ == "__main__":
    main()
