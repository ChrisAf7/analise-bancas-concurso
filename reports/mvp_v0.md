# Relatório do MVP — perfil estrutural da FCC em Direito Administrativo (codebook v0)

Gerado por `python -m concurso.report` em 2026-11-24. Todos os números vêm de código sobre o banco; nenhum foi produzido por IA. Intervalos: 95%, bootstrap reamostrando **cadernos** (não questões).

> ⚠️ **RELATÓRIO PARCIAL:** execuções incompletas: A:gemini-3.5-flash rep2. Rode `python -m concurso.classify run <avaliador> <rep>` e gere de novo.

> **Limitação central (ADR-012):** não há rótulo humano. Concordância entre modelos mede *confiabilidade*, não *validade*: dois modelos podem errar juntos. As conclusões abaixo só são afirmadas quando robustas aos dois modelos.

## 1. Corpus

- 1280 questões extraídas de 13 cadernos FCC (2013–2018 + 1 de 2022); lista em `corpus/candidatos.csv`.
- Escopo da classificação por IA (ADR-018): 142 questões (Direito Administrativo + 40 sem título do C10).

## 2. Execução dos avaliadores

| Run | Avaliador (modelo informado pelo provedor) | Repetição | Questões rotuladas |
|---|---|---|---|
| 1 | A:gemini-3.5-flash (gemini-3.5-flash) | 1 | 162/142 |
| 2 | B:nvidia/nemotron-3-ultra-550b-a55b:free (nvidia/nemotron-3-ultra-550b-a55b:free) | 1 | 162/142 |
| 3 | B:nvidia/nemotron-3-ultra-550b-a55b:free (nvidia/nemotron-3-ultra-550b-a55b:free) | 2 | 162/142 |
| 4 | A:gemini-3.5-flash (gemini-3.5-flash) | 2 | 100/142 |

## 3. Validação

### V4 — Estabilidade (mesmo modelo, 2 execuções)

| Avaliador | cenario | demanda_cognitiva | teoria_x_aplicacao | topico | fonte_normativa (conjunto) |
|---|---|---|---|---|---|
| A (n=100) | 100% (troca 0%) | 89% (troca 11%) | 91% (troca 9%) | 99% (troca 1%) | 80% (troca 20%) |
| B (n=162) | 97% (troca 3%) | 85% (troca 15%) | 90% (troca 10%) | 95% (troca 5%) | 83% (troca 17%) |

Limiar do projeto: troca ≤ 10% por variável.

### V3 — Concordância entre modelos (κ de Cohen, rótulos estáveis de cada modelo)

Modelos comparados: **A** × **B**.

| Variável | n | concordância | κ | uso (limiares do projeto) |
|---|---|---|---|---|
| cenario | 99 | 100% | 1.00 | usar |
| demanda_cognitiva | 76 | 87% | 0.82 | usar |
| teoria_x_aplicacao | 82 | 91% | 0.75 | usar |
| topico | 96 | 94% | 0.93 | usar |
| fonte: lei | 69 | 88% | 0.75 | usar |
| fonte: constituicao | 69 | 94% | 0.80 | usar |
| fonte: jurisprudencia | 69 | 96% | 0.38 | não usar / redefinir |
| fonte: sumula | 69 | 100% | — | — |
| fonte: doutrina | 69 | 83% | 0.58 | só exploratório |

### V2 — Âncoras por regra (casos em que uma regex dá a resposta quase certa)

| Âncora (regra → rótulo esperado) | n | acerto A | acerto B |
|---|---|---|---|
| 'situação hipotética'/'caso concreto' → cenario_hipotetico | 2 | 100% (2/2) | 100% (2/2) |
| nome próprio de agente no enunciado → cenario_hipotetico | 3 | 100% (3/3) | 100% (3/3) |
| enunciado invoca entendimento de tribunal/súmula → fonte inclui jurisprudencia ou sumula | 0 | — | — |
| título do caderno = Direito Administrativo → topico ≠ nao_dir_adm | 102 | 100% (102/102) | 100% (102/102) |

Limiar: ≥ 95%. Âncoras são fáceis por construção: passar é necessário, não suficiente.

## 4. Resultados — Direito Administrativo

Universo: **106 questões** (102 pelo título do caderno + 4 do C10 que os dois modelos classificaram como Direito Administrativo), em 13 cadernos.

### 4.1 Cenário (Q1, Q2)

κ entre modelos: 1.00. Colunas A e B: rótulo estável de cada modelo; Consenso: só onde A e B concordam.

| Valor | A | B | Consenso | robusto? |
|---|---|---|---|---|
| sem_cenario | 48% [21–70] n=79 | 54% [32–71] n=104 | 48% [21–70] n=79 | sim |
| cenario_hipotetico | 52% [30–79] n=79 | 46% [29–68] n=104 | 52% [30–79] n=79 | sim |

Sem consenso (fora da coluna Consenso): 27/106.

### 4.2a Teoria × aplicação (Q1) — recodificação binária da demanda

κ entre modelos: 0.75. Colunas A e B: rótulo estável de cada modelo; Consenso: só onde A e B concordam.

| Valor | A | B | Consenso | robusto? |
|---|---|---|---|---|
| teoria | 64% [43–80] n=70 | 83% [70–91] n=92 | 75% [54–89] n=57 | não (modelos divergem ≥10 p.p.) |
| aplicacao | 36% [20–57] n=70 | 17% [9–30] n=92 | 25% [11–46] n=57 | não (modelos divergem ≥10 p.p.) |

Sem consenso (fora da coluna Consenso): 49/106.

### 4.2 Demanda cognitiva (Q1)

κ entre modelos: 0.82. Colunas A e B: rótulo estável de cada modelo; Consenso: só onde A e B concordam.

| Valor | A | B | Consenso | robusto? |
|---|---|---|---|---|
| recordar_texto | 28% [16–37] n=69 | 40% [28–51] n=88 | 33% [15–52] n=49 | não (modelos divergem ≥10 p.p.) |
| reconhecer_conceito | 36% [19–52] n=69 | 42% [30–52] n=88 | 39% [21–55] n=49 | sim |
| aplicar_a_fatos | 36% [20–57] n=69 | 18% [9–32] n=88 | 29% [13–49] n=49 | não (modelos divergem ≥10 p.p.) |
| calcular_ou_contar | 0% [0–0] n=69 | 0% [0–0] n=88 | 0% [0–0] n=49 | sim |

Sem consenso (fora da coluna Consenso): 57/106.

### 4.3 Cenário × demanda — o “cenário decorativo” (H-001)

| | recordar_texto | reconhecer_conceito | aplicar_a_fatos | calcular_ou_contar | total |
|---|---|---|---|---|---|
| sem_cenario | 12 | 19 | 0 | 0 | 31 |
| cenario_hipotetico | 4 | 0 | 14 | 0 | 18 |

Entre as questões **com cenário** (consenso), a fração que **não exige aplicar os fatos** (cenário decorativo): **22% [0–42]** (n=18, 8 cadernos). H-001 previa > 50%.

> ⚠️ **Viés de seleção do consenso:** os casos decorativos são justamente os de fronteira, em que os modelos mais discordam; restringir ao consenso tende a SUBESTIMAR o cenário decorativo. Por isso, a estimativa por modelo (cada um com seus rótulos estáveis) é a referência:

- Avaliador A: cenário decorativo em **22% [11–30]** das questões com cenário (n=32).
- Avaliador B: cenário decorativo em **53% [27–72]** das questões com cenário (n=34).

### 4.4 Fonte normativa da alternativa correta (Q6)

| Fonte | A | B | Consenso | κ |
|---|---|---|---|---|
| lei | 56% [42–69] n=70 | 72% [62–80] n=90 | 65% [49–76] n=57 | 0.75 |
| constituicao | 21% [9–37] n=70 | 14% [4–28] n=90 | 17% [4–35] n=60 | 0.80 |
| jurisprudencia | 4% [0–9] n=70 | 2% [0–5] n=90 | 2% [0–5] n=61 | 0.38 |
| sumula | 0% [0–0] n=70 | 0% [0–0] n=90 | 0% [0–0] n=64 | — |
| doutrina | 41% [29–53] n=70 | 20% [15–26] n=90 | 25% [17–33] n=53 | 0.58 |
| indeterminada | 0% [0–0] n=70 | 0% [0–0] n=90 | 0% [0–0] n=64 | — |

### 4.5 Incidência por tópico (consenso)

| Tópico | n | % |
|---|---|---|
| dir_adm.licitacoes | 10 | 14% |
| dir_adm.organizacao | 10 | 14% |
| dir_adm.atos | 9 | 13% |
| dir_adm.improbidade | 7 | 10% |
| dir_adm.agentes | 7 | 10% |
| dir_adm.contratos | 6 | 9% |
| dir_adm.servicos_publicos | 5 | 7% |
| dir_adm.poderes | 4 | 6% |
| dir_adm.bens_publicos | 4 | 6% |
| dir_adm.responsabilidade_estado | 3 | 4% |
| dir_adm.controle | 2 | 3% |
| dir_adm.processo_administrativo | 2 | 3% |
| dir_adm.principios | 1 | 1% |

Sem consenso de tópico: 36/106.

## 5. Resultados por regra (sem IA) — corpus inteiro e Direito Administrativo

### Todas as questões (n=1280)

- **comando_tipo**: completar_frase 74%, assertivas_combinadas 10%, outro 8%, assinale_correta 6%, associacao 1%, assinale_incorreta 1%, completar_lacunas 0%
- **comando_polaridade**: positivo 98%, negativo 2%
- **formato_alternativas**: texto 83%, assertivas_combinadas 10%, numerica 7%
- comando negativo (INCORRETA/EXCETO/NÃO): 2% [1–3]

### Direito Administrativo (n=106)

- **comando_tipo**: completar_frase 73%, assertivas_combinadas 11%, outro 9%, assinale_correta 6%, assinale_incorreta 1%
- **comando_polaridade**: positivo 98%, negativo 2%
- **formato_alternativas**: texto 88%, assertivas_combinadas 11%, numerica 1%
- comando negativo (INCORRETA/EXCETO/NÃO): 2% [0–5]

### H-002 — A alternativa correta é a mais longa?

Questões com uma única alternativa mais longa: 745. A correta é a mais longa em **20% [17–24]** (152/745); acaso = 20%. Teste binomial exato bilateral p = 0.78 (assume independência; o IC por cadernos é a referência).

### H-004 — As letras do gabarito são equilibradas?

| A | B | C | D | E |
|---|---|---|---|---|
| 261 | 250 | 255 | 260 | 254 |

χ² de uniformidade = 0.32 (gl=4), p = 0.99.

## 6. Auditoria qualitativa (V6)

24 questões com demanda_cognitiva divergente na repetição 1; amostra local (com texto, fora do git) em `data/work/divergencias_mvp_v0.md`.
