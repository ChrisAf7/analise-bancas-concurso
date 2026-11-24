# ANALYSIS — Plano de análises e métodos estatísticos

> Status: **proposta**. Nenhuma métrica foi calculada. Este documento define *como* calcular, para
> que os métodos sejam escolhidos antes de ver os dados.

## 1. Regras gerais

1. **Todo número vem de código** (`src/concurso/stats.py` ou notebook) executado sobre o banco. A IA
   pode comentar uma tabela, nunca produzi-la.
2. Toda estatística é publicada com **n de questões, n de provas e intervalo de confiança**.
3. Toda estatística baseada em classificação declara a **fonte de rótulo** (modelo A, modelo B ou
   consenso), o **κ entre modelos** da variável e a fração de questões sem consenso.
4. Todo relatório traz a **composição do corpus** (provas por ano, órgão e cargo), porque o resultado
   vale para o corpus, não para "a FCC" em abstrato.
5. Separar **análise confirmatória** (hipótese registrada antes, §6) de **exploratória** (varreduras,
   que geram hipóteses e não conclusões).

## 2. Famílias de análise

### 2.1 Incidência (o que cai)
- Contagem e proporção por disciplina, tópico, subtópico, banca e ano.
- **Duas ponderações**, com resultados possivelmente diferentes:
  - *por questão*: a prova com mais questões pesa mais;
  - *por prova*: média das proporções de cada prova, em que cada prova pesa igual. Para prever "a próxima
    prova", a ponderação por prova costuma ser mais adequada.
- **Edital × prova**: fração dos itens do edital que tiveram ao menos uma questão; itens nunca cobrados;
  concentração (quantos tópicos respondem por 50% das questões).

### 2.2 Estrutura (como cai)
- Proporções de `cenario`, `demanda_cognitiva`, `fonte_normativa`, `comando_tipo`,
  `comando_polaridade` e `formato_alternativas`.
- **Tabela cruzada central para Q1: `cenario` × `demanda_cognitiva`**. A célula "com cenário ×
  recordar_texto" (cenário decorativo) separa "a banca conta histórias" de "a banca exige aplicação".
- Probabilidades condicionais no formato pedido, por exemplo
  `P(aplicar_a_fatos | FCC, Dir. Adm., tópico)`.

### 2.3 Linguagem
- Distribuições (mediana, IQR) de comprimento de enunciado e alternativas, `n_assertivas`, negações e
  absolutos. Comparações por Mann-Whitney ou regressão quantílica. Evitar médias com caudas longas.
- **Vieses exploráveis** (diretamente úteis para a prova):
  - *a alternativa correta é a mais longa?* Teste binomial contra 1/5, com empates tratados à parte;
  - *distribuição das letras do gabarito*: χ² de uniformidade por prova e agregado;
  - *absolutos* ("sempre", "somente") por alternativa correta × incorreta: razão de chances.
  Esses testes desmontam ou confirmam "macetes" com dados.

### 2.4 Comparação entre bancas (quando houver mais de uma)
Mesmas métricas, mas comparadas **dentro da mesma disciplina e do mesmo tipo de cargo**. Comparar FCC em
tribunais de contas com Cebraspe em polícia mede cargo, não banca.

### 2.5 Evolução temporal
- Períodos do briefing: 2015–2018, 2019–2022, 2023–2026, com o ano também como variável contínua
  (tendência). Períodos são legíveis; o ano contínuo tem mais poder.
- **Ressalva já conhecida:** o corpus 2023–2026 depende de fonte primária (SPEC §5.3). Sem provas
  suficientes num período, o resultado é "dado insuficiente", não "estável".

### 2.6 Perfil individual (futuro, Q11)
Regressão logística `erro ~ features da questão + disciplina` sobre o histórico pessoal. Responde "em que
tipo de questão eu erro", não só "em que assunto".

## 3. Métodos

### 3.1 Intervalos de confiança agrupados
Questões da mesma prova não são independentes (mesma equipe de elaboradores, mesmo estilo). O IC
binomial ingênuo é estreito demais. Padrão do projeto:
- **descritivo**: *bootstrap por prova* (reamostrar cadernos, não questões), com IC de percentis a 95%;
- **comparações**: regressão logística com erro-padrão robusto agrupado por prova (`statsmodels` GLM,
  `cov_type='cluster'`).

### 3.2 Separar banca × órgão × disciplina × tópico (Q9)
Modelo logístico misto, por variável estrutural *y*:

```
logit P(y = 1) = β0 + β_banca + β_disciplina + β_período + β_tipo_órgão + u_órgão + v_prova
```

- `u_órgão` e `v_prova` são efeitos aleatórios. A **decomposição de variância** (ICC) diz quanto da
  variação está entre órgãos dentro da banca e quanto está entre provas dentro do órgão.
- **Identificabilidade é uma questão de desenho amostral, não de modelo:**
  - o efeito de **banca** só se separa do de órgão se houver vários órgãos por banca e, idealmente,
    o mesmo órgão avaliado por bancas diferentes em anos diferentes;
  - **com só a FCC (MVP)**, já é possível responder se o tipo de órgão "controle" difere do restante
    da FCC, comparando `tipo_órgão` dentro da FCC. Isso cobre o caso de uso da STC-MA.
- Implementação: `statsmodels` (`BinomialBayesMixedGLM`) ou, mais simples e muitas vezes suficiente,
  GLM com `tipo_órgão` fixo e erro agrupado por prova. Só subir para o modelo misto com ≥ ~8–10
  órgãos distintos.

### 3.3 Concordância
- Cohen's κ (2 avaliadores) e, para multirrótulo ou mais avaliadores, α de Krippendorff.
- Sempre acompanhado da **matriz de confusão**. Um κ médio esconde a classe que o modelo erra.
- κ é sensível à prevalência: para classes raras, reportar também precisão e recall por classe.

### 3.4 Proporções estimadas por IA
**Situação atual (sem gold humano, ADR-012):** não há como estimar sensibilidade e especificidade
contra a verdade, então não há correção formal. Cada estatística baseada em classificação é publicada
**três vezes** (modelo A, modelo B, consenso). A diferença entre A e B é a faixa de incerteza do
classificador, e uma conclusão só é afirmada se tiver a mesma direção nas três versões.

**Se um dia houver uma amostra revisada por humano**, um classificador imperfeito distorce
prevalências e há duas correções, em ordem de simplicidade:
1. **Rogan-Gladen** (variável binária): `p̂ = (p_obs + esp − 1) / (sens + esp − 1)`, com sensibilidade
   e especificidade estimadas no gold set e IC por bootstrap conjunto (gold mais corpus).
   Multiclasse: inversão da matriz de confusão.
2. **Prediction-powered inference** (Angelopoulos et al., 2023): combina o gold set pequeno com o
   corpus grande rotulado por IA e produz IC válidos mesmo com erro do classificador. É a opção mais
   rigorosa e vale quando κ estiver entre 0,6 e 0,8.

### 3.5 Tamanho amostral: o que dá e o que não dá para responder
Premissas: cerca de 15 questões de Dir. Adm. por prova; ICC intraprova ~0,05, logo efeito de desenho
≈ 1 + 14 × 0,05 ≈ 1,7. A ICC é suposta e será medida no MVP.

| Objetivo | n de questões | ≈ n de provas |
|---|---|---|
| Estimar uma proporção com ±10 p.p. (IC 95%) | ~165 | ~11 |
| Detectar diferença de 15 p.p. entre 2 grupos (poder de 80%) | ~290 **por grupo** | ~19 por grupo |
| Comparar 3 períodos com diferenças de 15 p.p. | ~870 | ~58 |

**Implicação:** o MVP (~150–250 questões) responde bem "qual é o perfil" e mal "como mudou ao longo
do tempo". A análise temporal só é viável depois de expandir o corpus, e só se houver provas
recentes. Melhor saber isso agora do que depois.

### 3.6 Ferramentas
`pandas` (manipulação), `statsmodels` (GLM, modelos mistos), `scipy.stats` (testes, χ²),
`scikit-learn` só para `cohen_kappa_score` e `confusion_matrix`, `krippendorff` (pacote pequeno)
se houver multirrótulo. Gráficos com `matplotlib`. Nada além disso sem justificativa.

## 4. Saídas para estudo (o produto final)
O relatório do MVP termina com um **perfil por disciplina** que liga dado a ação, por exemplo:

| Achado (exemplo de formato, não resultado) | Implicação de estudo |
|---|---|
| X% das questões são "recordar_texto", inclusive Y% das que têm cenário | priorizar lei seca e revisão por dispositivo |
| comando negativo em Z% | treinar a leitura do comando; erros de "assinalou a correta" |
| assertivas combinadas em W% | treinar a eliminação por assertiva |

Cada linha cita a estatística, o IC e o κ de que depende.

## 5. Múltiplas comparações
Varreduras exploratórias (todas as variáveis × todos os tópicos) produzem falsos positivos. Regras:
correção de **Benjamini–Hochberg** (FDR 10%) nas varreduras; achado exploratório vira hipótese no
registro (§6) e só é afirmado depois de testado em dados novos (outras provas).

## 6. Registro de hipóteses

| ID | Hipótese | Variável e teste | Origem | Status |
|---|---|---|---|---|
| H-001 | Em Dir. Adm., a maioria das questões FCC com cenário exige apenas recordar texto legal (cenário decorativo) | `cenario` × `demanda_cognitiva`; proporção com IC agrupado | briefing (Q1) | **inconclusiva** (MVP v0: A 22% [11–30], B 53% [27–72]; depende da fronteira do codebook → v1) |
| H-002 | A alternativa correta da FCC **não** é mais longa que as demais com frequência acima do acaso (1/5) | `correta_e_mais_longa`; teste binomial | folclore de concurso | **confirmada** no corpus MVP: 20% [17–24], n=745, p=0,78 |
| H-003 | Provas FCC de órgãos de controle cobram mais jurisprudência e TCU que outras provas FCC na mesma disciplina | `fonte_normativa` ~ `tipo_órgão`; GLM agrupado | Q9 | proposta |
| H-004 | As letras do gabarito são equilibradas por prova | χ² de uniformidade | Q3 | **confirmada** no agregado: A 261, B 250, C 255, D 260, E 254; χ²=0,32, p=0,99 |
| H-005 | O perfil estrutural da prova da STC-MA 2013 (FGV) difere do perfil FCC em órgãos de controle na mesma disciplina | `cenario`, `demanda_cognitiva` ~ banca, dentro de `tipo_órgão = controle` | Q9 (fase 2) | proposta |

Status possíveis: `proposta` → `registrada` (método fixado antes dos dados) → `testada` (com resultado
e link para o notebook) → `confirmada`, `refutada` ou `inconclusiva`.
