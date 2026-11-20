# SPEC — Análise empírica do comportamento de bancas de concurso

> Status: **aprovada; MVP em andamento** (etapa 0 concluída e etapa 1 parcial em 2026-11-20; ver CLAUDE.md).
> Diagrama do modelo de dados: [diagrams/data_model.png](diagrams/data_model.png).
> Leitura recomendada: este arquivo → [DATA_MODEL.md](DATA_MODEL.md) → [ARCHITECTURE.md](ARCHITECTURE.md) → [ANALYSIS.md](ANALYSIS.md) → [DECISIONS.md](DECISIONS.md).

## 1. Problema

Cursinhos respondem "o que cai" (incidência de assunto). Este projeto quer responder **"como cai"**:
como a banca formula a questão, que tipo de raciocínio exige, de que fonte normativa depende a
resposta e como constrói as alternativas erradas. E quer fazer isso com estatística calculada
sobre dados estruturados e auditáveis, não com impressões.

O alvo atual é o cargo de **Auditor da STC-MA**, com a **FCC** como banca. A arquitetura deve
permitir, mais tarde, comparar bancas (FGV, Cebraspe, Vunesp, Cesgranrio…).

O objetivo final é prático: **identificar características das questões que deveriam mudar a forma
de estudar** (por exemplo, "lei seca" versus jurisprudência versus resolução de casos).

## 2. Perguntas de pesquisa

Cada pergunta indica a variável de que depende e a camada dessa variável (O = observado,
D = derivado, IA = classificação por modelo; ver [DATA_MODEL.md §2](DATA_MODEL.md)).

| # | Pergunta | Variáveis | Camada |
|---|---|---|---|
| Q1 | Em Direito, a banca cobra mais teoria ou aplicação a casos concretos? | `cenario` × `demanda_cognitiva` | D + IA |
| Q2 | Qual a proporção de questões conceituais versus situações hipotéticas? | `cenario`, `demanda_cognitiva` | D + IA |
| Q3 | Como a banca estrutura os enunciados? | `formato_alternativas`, `comando_polaridade`, comprimentos | D |
| Q4 | Quais tipos de comando aparecem mais? | `comando_tipo` | D |
| Q5 | Como são construídos os distratores? | `tipo_distrator` (por alternativa) | IA (fase 2) |
| Q6 | A banca usa mais lei seca, jurisprudência, doutrina ou aplicação? | `fonte_normativa`, `literalidade_score` | IA + D (fase 2) |
| Q7 | Quais padrões linguísticos e estruturais se repetem? | métricas de texto | D |
| Q8 | Como esse comportamento muda por disciplina, tópico e ano? | tudo acima × dimensões | — |
| Q9 | O perfil da banca difere do perfil do órgão ou concurso? | tudo acima × `orgao` | requer desenho amostral (ver [ANALYSIS.md §4](ANALYSIS.md)) |
| Q10 | Quais características deveriam influenciar a forma de estudar? | síntese de Q1–Q9 | hipótese analítica |
| Q11 (futuro) | Em quais características eu erro mais? | histórico pessoal × variáveis | fora do MVP |

Exemplos de estimandos formais que o modelo de dados precisa suportar:

- `P(cenario = sim | banca = FCC, disciplina = Direito Administrativo)`
- `P(fonte = jurisprudência | banca = FCC, tópico = Atos administrativos)`
- essas proporções por período (2015–2018, 2019–2022, 2023–2026), com intervalo de confiança.

## 3. Princípio fundamental: quatro camadas de conhecimento

| Camada | O que é | Exemplo | Onde vive |
|---|---|---|---|
| **Observado** | Extraído diretamente da prova, do gabarito ou do edital | texto do enunciado, alternativas, gabarito definitivo, título da seção ("Direito Administrativo") | tabelas `question`, `alternative`, `prova`… |
| **Derivado** | Calculado de forma determinística a partir do observado, por código versionado | nº de palavras, presença de "EXCETO", formato I/II/III, posição da resposta correta | `question_feature` (regenerável) |
| **Classificação** | Interpretação feita por IA **ou por humano**, sempre com proveniência | tópico, `cenario`, `demanda_cognitiva`, `fonte_normativa` | `annotation` + `annotation_run` |
| **Hipótese analítica** | Afirmação que precisa ser testada | "A FCC cobra mais lei seca em Dir. Adm. do que em Dir. Const." | registro de hipóteses em [ANALYSIS.md](ANALYSIS.md) |

Regras derivadas desse princípio:

1. Nenhuma classificação de IA sobrescreve um dado observado.
2. Toda classificação registra quem classificou (modelo ou pessoa), a versão do prompt, a versão do
   codebook, a data e, quando houver, a evidência textual.
3. Toda análise declara **qual fonte de rótulo usa** (somente humano, somente IA ou regra de resolução).
4. Uma estatística só é publicada no relatório se puder ser recalculada por código a partir do banco.
   A IA pode sugerir hipóteses, mas não produz números.

## 4. Escopo

### Dentro do escopo
- Questões objetivas de múltipla escolha (formato FCC, A–E).
- Provas, gabaritos (preliminar e definitivo) e editais como fontes primárias.
- Taxonomia de conteúdo própria do projeto, mapeada para os itens do edital.
- Classificação estrutural (IA mais validação humana).
- Análises descritivas e inferenciais por banca, órgão, disciplina, tópico e período.

### Fora do escopo (por enquanto)
- Questões discursivas e peças.
- Aplicativo de estudo, banco de questões para resolver ou interface web.
- Coleta automatizada em massa (scraping). Ver os riscos legais em [ARCHITECTURE.md §7](ARCHITECTURE.md).
- Questões Certo/Errado (Cebraspe). O modelo as suporta (`formato_resposta`), mas o MVP não.
- Histórico pessoal de erros. O modelo reserva espaço, mas a tabela ainda não é criada.

## 5. Fatos levantados na descoberta (2026-11-19)

1. **Repositório**: contém apenas o briefing (`Quero desenvolver neste repositório.txt`). Não há
   código, dados, git ou ferramentas configuradas. Python 3.13.7 e git 2.51 estão instalados na máquina.
2. **Concurso-alvo (confirmado em 2026-11-20)**: os cargos de Auditor da STC-MA estão dentro do
   **Concurso Unificado do Maranhão** (Edital nº 01/2026). O concurso tem várias secretarias (SEAD,
   SEDUC, SEPLAN, STC, IMESC) e a banca é a **FCC**. Dados de imprensa (Direção Concursos, Gran,
   Concursos no Brasil, todos de 18–19/11/2026), coerentes entre si:
   - inscrições de 14/12/2026 a 29/01/2027; **prova em 04/04/2027**;
   - Auditor (Área Geral 14 vagas, TI 3, Engenharia 3): **80 questões objetivas** de múltipla escolha
     com **5 alternativas**, sendo 30 de Conhecimentos Gerais (peso 1) e 50 de Conhecimentos Específicos
     (peso 2), mais uma discursiva de **estudo de caso** com 2 questões, só para a STC;
   - os específicos citam auditoria governamental, controle interno, COSO, gestão de riscos,
     contabilidade pública (NBC TSP), **direito administrativo** e avaliação de políticas públicas;
   - página oficial: `https://www.concursosfcc.com.br/concursos/seadm226/`. O conteúdo programático
     detalhado ainda precisa ser extraído do edital oficial (etapa 0 do MVP).
   - Os Conhecimentos Gerais são compartilhados com outros cargos, então a deduplicação entre cadernos
     é obrigatória.
   - **Achado na leitura do edital (2026-11-20):** para o Auditor – Área Geral, Direito Administrativo
     não é disciplina separada. O conteúdo está nos itens 2 (Administração Pública e Direito
     Administrativo), 5 (Licitações e contratos) e 7 (Controle e responsabilização, improbidade) dos
     Específicos. O núcleo da prova é auditoria e controle. A taxonomia v0 está em
     `taxonomy/dir_adm_v0.toml`. O edital oficial ainda contém uma nota interna de edição esquecida
     ("o tem estava nos conhecimentos específicos, puxei para o geral"), o que sugere retificação provável.
     **Acompanhar retificações.**
3. **Cobertura do PCI para a FCC cai a quase zero depois de 2019**. Provas FCC encontradas por ano
   no acervo: 2019: 58; 2021: 1; 2022: 7; 2023: 0; 2024: 0; 2025: 0. Provas de *auditor* FCC no
   PCI vão de 2002 a 2019 (TCEs, TCMs, SEFAZs, Pref. São Luís/MA 2015 e 2018, SEFAZ-MA 2016).
   **Consequência:** o período 2023–2026 terá de vir de fonte primária (site da FCC ou do órgão).
   O PCI serve como catálogo e fonte secundária, não como base.
4. **O concurso anterior da STC-MA (2013) foi da FGV**, não da FCC. Isso é útil: é o caso "mesmo
   órgão, banca diferente", que ajuda a separar perfil de banca de perfil de órgão (Q9, fase 2).
   Os comparáveis FCC mais próximos são provas para controle interno e externo (Pref. São Luís/MA –
   Auditor de Controle Interno 2015, SEFAZ-MA 2016, TCEs e TCMs).
5. **Restrições do usuário (2026-11-20)**: só modelos de IA **gratuitos**; repositório **público**;
   **nenhuma rotulagem humana**. A validação foi redesenhada por causa disso
   (ARCHITECTURE §5, ADR-012).

## 6. MVP — teste da hipótese antes de construir

**Hipótese do MVP:** *características estruturais das questões da FCC em Direito Administrativo
podem ser medidas com confiabilidade aceitável (por regra ou por IA validada) e variam o suficiente
para sugerir mudanças concretas na forma de estudar.*

Se a hipótese falhar, o projeto se reduz às métricas derivadas, que são baratas e objetivas, ou é
encerrado. Se passar, expande-se para outras disciplinas e bancas.

### Recorte
- **Banca:** FCC. **Disciplina:** Direito Administrativo (decisão pendente P3).
- **Corpus:** cerca de 10–15 provas FCC de cargos de controle (auditor, controle interno e externo,
  analista de TC), privilegiando provas com camada de texto (PDF digital). A meta é **150–250 questões**
  de Direito Administrativo.
- **Variáveis:**
  - derivadas: comprimentos, `comando_polaridade`, `comando_tipo`, `formato_alternativas`,
    marcadores (datas, valores, citação legal, menção a tribunal), posição e comprimento relativo
    da alternativa correta;
  - IA (2 famílias de modelos gratuitos): `topico`, `cenario`, `demanda_cognitiva`, `fonte_normativa`.
  - Distratores ficam **fora** do MVP; no máximo um piloto de 30 questões para medir concordância.

### Etapas
0. Baixar o edital oficial da FCC, extrair o conteúdo programático de Direito Administrativo do
   Auditor e montar a taxonomia v0. Montar a lista de provas do corpus com a proveniência de cada uma.
1. **Spike de extração**: 2 PDFs FCC, medir a taxa de questões segmentadas corretamente e escolher
   a biblioteca (ADR-004). No mesmo spike, testar as chaves gratuitas de IA (ADR-012).
2. Carregar o corpus no SQLite e rodar as verificações estruturais (5 alternativas, gabarito
   válido, contagem igual à esperada).
3. Calcular as features derivadas.
4. Escrever o codebook v0 (4 variáveis) com exemplos tirados do próprio corpus.
5. Rotular o corpus com **2 modelos gratuitos de famílias diferentes**, 2 execuções cada.
6. Validar sem humano (ARCHITECTURE §5): âncoras por regra, concordância entre modelos,
   estabilidade e análise de sensibilidade.
7. Produzir **um relatório** com proporções e intervalos de confiança para Q1–Q4 e Q7, a robustez de
   cada conclusão entre modelos e a lista de hipóteses geradas.

### Critérios de decisão (go / no-go)
| Critério | Limiar |
|---|---|
| Extração | ≥ 95% das questões segmentadas sem correção manual |
| Âncoras por regra | o modelo concorda com a regra em ≥ 95% dos casos em que a regra é quase certa |
| Concordância entre modelos | κ ≥ 0,7 em pelo menos 2 das 3 variáveis estruturais |
| Estabilidade | ≤ 10% de troca de rótulo entre 2 execuções do mesmo modelo |
| Utilidade | ≥ 1 achado **robusto** (mesma direção nos 2 modelos) que você considere capaz de mudar sua forma de estudar |
| Custo | US$ 0 de API; nenhuma hora de rotulagem sua |

## 7. Decisões pendentes do usuário
Ver [DECISIONS.md — Pendentes](DECISIONS.md#pendentes-precisam-de-aprovação).
