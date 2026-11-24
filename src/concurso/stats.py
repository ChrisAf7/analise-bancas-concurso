"""Estatística mínima em Python puro (sem dependências): κ, bootstrap agrupado, testes exatos.

Decisão: o MVP precisa de poucos métodos e todos cabem aqui com fórmulas conhecidas; numpy/scipy/statsmodels
entram (com ADR) quando houver modelos mistos (ANALYSIS §3.2).
"""
from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from typing import Hashable, Iterable


def cohen_kappa(pairs: list[tuple[Hashable, Hashable]]) -> float | None:
    """κ de Cohen para dois avaliadores. None se indefinido (n=0 ou concordância esperada = 1)."""
    n = len(pairs)
    if n == 0:
        return None
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb.get(k, 0) for k in ca) / (n * n)
    if pe >= 1:
        return None
    return (po - pe) / (1 - pe)


def cluster_bootstrap_prop(values_by_cluster: dict[Hashable, list[int]], b: int = 4000, seed: int = 20261124,
                           alpha: float = 0.05) -> tuple[float, float, float, int, int]:
    """Proporção (média de 0/1) com IC por bootstrap reamostrando clusters (cadernos), não questões.

    Retorna (p, li, ls, n_itens, n_clusters).
    """
    clusters = [v for v in values_by_cluster.values() if v]
    n_items = sum(len(v) for v in clusters)
    if n_items == 0:
        return (float("nan"), float("nan"), float("nan"), 0, 0)
    p = sum(sum(v) for v in clusters) / n_items
    rng = random.Random(seed)
    k = len(clusters)
    stats = []
    for _ in range(b):
        sample = [clusters[rng.randrange(k)] for _ in range(k)]
        tot = sum(len(v) for v in sample)
        stats.append(sum(sum(v) for v in sample) / tot)
    stats.sort()
    lo = stats[int((alpha / 2) * b)]
    hi = stats[int((1 - alpha / 2) * b) - 1]
    return (p, lo, hi, n_items, k)


def binom_two_sided_p(k: int, n: int, p0: float) -> float:
    """Teste binomial exato bilateral (método das probabilidades ≤ à observada)."""
    pmf = [math.comb(n, i) * p0 ** i * (1 - p0) ** (n - i) for i in range(n + 1)]
    obs = pmf[k]
    return min(1.0, sum(x for x in pmf if x <= obs * (1 + 1e-9)))


def chi2_uniform_df4(counts: Iterable[int]) -> tuple[float, float]:
    """χ² de uniformidade para 5 categorias (df=4). Para df=4: P(X>x) = e^(-x/2)·(1 + x/2)."""
    c = list(counts)
    n = sum(c)
    e = n / len(c)
    x = sum((o - e) ** 2 / e for o in c)
    return x, math.exp(-x / 2) * (1 + x / 2)


def group(rows: Iterable[tuple[Hashable, int]]) -> dict[Hashable, list[int]]:
    d: dict[Hashable, list[int]] = defaultdict(list)
    for cluster, v in rows:
        d[cluster].append(v)
    return d


def fmt_pct(p: float, lo: float | None = None, hi: float | None = None) -> str:
    if p != p:  # NaN
        return "—"
    s = f"{100 * p:.0f}%"
    if lo is not None and hi is not None:
        s += f" [{100 * lo:.0f}–{100 * hi:.0f}]"
    return s
