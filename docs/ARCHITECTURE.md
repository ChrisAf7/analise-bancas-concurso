# ARCHITECTURE — Pipeline, uso de IA, validação e riscos

> Status: **proposta**. Restrição explícita do briefing: nada de microsserviços, orquestradores,
> infraestrutura distribuída ou abstrações sem uso. É um projeto local, de uma pessoa, em Python.

## 1. Visão geral

```
 fontes primárias           ingestão               observado            derivado          classificação          análise
 (PDF prova, gabarito,  →  registrar + hash  →  parse + verificar  →  features por  →  LLM + humano        →  notebooks/
  edital)                   data/raw/           SQLite (question,     regra             (annotation_run,       relatórios
                            source_document     alternative)          question_feature  annotation)            (código → números)
                                                    ↑                                       ↑
                                              verificação humana                     gold set + auditoria
```

Cada estágio é um **comando de CLI idempotente** que lê do banco e escreve no banco. Não há
orquestrador: a ordem é linear e um `Makefile` ou script `run_all` basta.

## 2. Layout do repositório (proposto)

```
CONCURSO/
├── CLAUDE.md                  # ponteiro para docs/ (contexto de novas sessões)
├── .env                       # chaves de API (fora do git); ver .env.example
├── docs/                      # SPEC, DATA_MODEL, ARCHITECTURE, ANALYSIS, DECISIONS, SETUP_IA
│   └── diagrams/              # data_model.png + fonte .elements.json + render.mjs
├── config/
│   └── models.toml            # provedores e modelos gratuitos em uso (A e B)
├── codebook/
│   └── v0.yaml                # definições das variáveis de classificação (humano e IA)
├── prompts/
│   └── classify_v0.md         # template; o hash do arquivo vira prompt_version
├── db/
│   └── migrations/001_init.sql
├── src/concurso/
│   ├── ingest.py              # registra source_document (hash, origem, URL)
│   ├── parse_fcc.py           # PDF → questões e alternativas (parser específico por banca)
│   ├── checks.py              # verificações estruturais
│   ├── features.py            # features derivadas (EXTRACTOR_VERSION)
│   ├── llm.py                 # cliente único compatível com OpenAI (Gemini / OpenRouter / Ollama)
│   ├── classify.py            # lotes de questões → annotation_run e annotation
│   └── stats.py               # IC agrupado, kappa, âncoras, sensibilidade
├── notebooks/                 # exploração; só consomem src/ e o banco
├── data/                      # fora do git (ver ADR-007)
│   ├── raw/                   # PDFs originais, nomeados pelo sha256
│   ├── concurso.sqlite
├── exports/                   # VERSIONADO: rótulos por chave da questão (sem texto) + tabelas agregadas
└── tests/                     # testes do parser e das regex, com fixtures pequenas
```

Os parsers são **por banca** (`parse_fcc.py`, depois `parse_fgv.py`…) porque cada banca tem layout
próprio. Todos produzem a mesma estrutura intermediária, então o resto do pipeline é agnóstico à
banca. Essa é a única abstração justificada no começo.

## 3. Pipeline de ingestão e tratamento

| # | Estágio | Entrada → saída | Controles |
|---|---|---|---|
| 1 | **Registrar fonte** | arquivo e metadados → `source_document`, arquivo em `data/raw/<sha256>.pdf` | hash único (sem duplicatas); origem e URL obrigatórias |
| 2 | **Catalogar** | metadados digitados (banca, órgão, ano, cargo, tipo de caderno) → `concurso`, `prova`, `prova_cargo` | cadastro manual, poucos registros; sem IA |
| 3 | **Extrair texto** | PDF → texto bruto por página (biblioteca decidida no spike, ADR-004) | PDFs sem camada de texto são marcados `ocr`, ficam fora do MVP |
| 4 | **Segmentar** | texto → questões (número, cabeçalho de disciplina, enunciado) e alternativas A–E | regex por banca; cabeçalho de seção é **observado** |
| 5 | **Gabarito** | PDF do gabarito → `gabarito_preliminar` e `gabarito_definitivo`, `status` | atenção ao tipo de caderno: a numeração e o gabarito variam por tipo |
| 6 | **Verificar** | → relatório de falhas | ver §3.1; uma prova só "entra" quando passa |
| 7 | **Deduplicar** | `text_hash` normalizado | mesma questão em cadernos de cargos diferentes do mesmo concurso |
| 8 | **Features** | questão → `question_feature` | puro código; recalcula tudo quando `EXTRACTOR_VERSION` muda |
| 9 | **Classificar** | questão + codebook → `annotation` | ver §4 |
| 10 | **Exportar** | rótulos → `exports/annotations/*.jsonl` (chave natural `banca-orgao-ano-caderno-numero`, sem texto) | trilha de auditoria pública e reconstruível |

### 3.1 Verificações estruturais (automáticas)
- número de questões extraídas = `n_questoes_esperado`;
- numeração contínua, sem buracos nem repetição;
- exatamente 5 alternativas (FCC), nenhuma vazia;
- gabarito com letra válida para toda questão não anulada;
- nenhuma alternativa contendo o início da questão seguinte (vazamento de segmentação);
- cabeçalhos de disciplina cobrindo todas as questões;
- amostragem: 1 questão em cada 10 conferida visualmente contra o PDF até o parser se estabilizar.

**Regra inviolável:** o LLM **não** transcreve nem "corrige" o texto da questão. Se algum dia um
LLM for usado na extração (por exemplo, para PDFs ruins), a saída passa por comparação caractere a
caractere com o texto do PDF, porque modelos tendem a normalizar redação, e redação é o objeto de estudo.

## 4. Uso de IA

### 4.1 Para que a IA é usada (e para que não é)
| Sim | Não |
|---|---|
| classificar variáveis do codebook (tópico, cenário, demanda, fonte) | gerar qualquer número do relatório |
| propor o mapeamento edital → taxonomia (revisado por humano) | transcrever questões |
| agrupar questões semelhantes (embeddings, fase 2) | decidir sozinha o valor de uma variável sem trilha |
| gerar hipóteses a partir de tabelas já calculadas | "estimar" proporções ou tendências |
| ajudar a ler os resultados | |

### 4.2 Desenho da classificação
- **Uma chamada por questão, todas as variáveis juntas**, com saída estruturada (JSON schema). Para
  cada variável: valor, trecho de evidência e justificativa curta.
- O prompt contém o codebook completo. Ele é o prefixo estável e entra em cache. A questão vem no fim.
- `prompt_version` = hash do template mais o codebook. Qualquer alteração gera um novo `annotation_run`.
- **Modelos: só gratuitos (ADR-012).** O cliente é **neutro quanto ao provedor**: uma única função
  fala o protocolo compatível com OpenAI (`base_url` + chave), que Google AI Studio (Gemini),
  OpenRouter e Ollama expõem. O provedor e o modelo são configuração (`config/models.toml`), não código.
- **Dois avaliadores de famílias diferentes** (por exemplo, um Gemini e um modelo aberto via
  OpenRouter), para que a concordância entre eles signifique alguma coisa. Modelos da mesma família
  tendem a errar juntos.
- **Lotes de várias questões por chamada** (~5–10), porque o OpenRouter gratuito limita a 50
  requisições por dia em contas sem créditos. Cada questão no lote tem um ID e a resposta é validada
  contra o schema; um lote com resposta inválida é refeito questão a questão.
- **Temperatura baixa quando o provedor aceitar**, mas a determinação não é presumida: cada modelo
  roda **duas vezes** e a troca de rótulo entre execuções é medida.
- **Confiança autodeclarada pelo modelo é mal calibrada** e não é usada para decidir nada. A
  confiança operacional é a concordância entre execuções e entre modelos.
- **Modelos gratuitos mudam e somem** (as listas de modelos `:free` são rotativas). Por isso o ID exato
  do modelo e o provedor ficam em `annotation_run`, e o pipeline aceita trocar de modelo sem mudar código.
- **Privacidade:** nos planos gratuitos, os provedores podem usar as entradas para treinar modelos.
  Aqui isso é aceitável, porque o texto enviado é de provas públicas; nada pessoal é enviado.

### 4.3 Resolução de rótulos
`v_label_resolved` segue a regra: **rótulo humano** se existir (reservado para o futuro) → senão
**consenso entre os 2 modelos (e entre as execuções)** → senão `NULL`. Questões sem consenso ficam
fora da estatística daquela variável, e a fração excluída é reportada e verificada contra viés
(por exemplo, se as exclusões se concentram num tópico).

## 5. Estratégia de validação

> Decisão do usuário (2026-11-20): **nenhuma rotulagem humana**. Sem gold set humano, não dá para
> medir se a IA está *certa*; dá para medir se ela é *consistente*, *concorda com regras objetivas* e
> se as conclusões são *robustas* à troca de modelo. A estratégia abaixo faz isso e declara a limitação.

| Nível | O que valida | Como | Métrica e limiar |
|---|---|---|---|
| V1 Transcrição | texto e gabarito batem com o PDF | verificações automáticas (§3.1) e amostra visual feita por mim (Claude) na fase de desenvolvimento do parser | 0 falhas estruturais; ≥ 95% de segmentação sem correção |
| V2 Âncoras por regra | o modelo acerta nos casos em que a resposta é quase certa | subconjunto em que uma regex dá a resposta com segurança: "Considere a seguinte situação hipotética" → `cenario`; "Súmula", "STF", "STJ" no enunciado → `fonte_normativa` inclui jurisprudência; "art." com número de lei citado → inclui lei | concordância ≥ 95%. Abaixo disso, o prompt ou o modelo está com defeito |
| V3 Entre modelos | duas famílias diferentes chegam ao mesmo rótulo | κ por variável entre o modelo A e o modelo B (consenso de execuções) | κ ≥ 0,7: usar; 0,5–0,7: só exploratório; < 0,5: variável subjetiva demais, redefinir ou descartar |
| V4 Estabilidade | cada modelo concorda consigo mesmo | 2 execuções por modelo | troca de rótulo ≤ 10% por variável |
| V5 Sensibilidade | a conclusão não depende do modelo escolhido | cada estatística calculada 3 vezes (modelo A, modelo B, consenso) | conclusão só é afirmada se tiver a **mesma direção** nas três |
| V6 Auditoria qualitativa | os erros fazem sentido | eu (Claude, nesta ferramenta) leio uma amostra de 30 discordâncias e classifico a causa (codebook ambíguo, questão ambígua, erro do modelo) | ajuste do codebook; não gera número de validade |

Detalhes que importam:
- **Limitação declarada em todo relatório:** concordância entre modelos mede confiabilidade, não
  validade. Dois modelos podem compartilhar o mesmo viés. Por isso as âncoras (V2) e a exigência de
  robustez (V5) importam.
- As âncoras são **fáceis por construção**: passar nelas é necessário, mas não suficiente.
- Os limiares de κ são **convenção do projeto**, não verdade estatística. Ficam registrados aqui
  para não serem ajustados depois de ver os resultados.
- A arquitetura continua aceitando rótulos humanos (`annotator_type='human'`) se algum dia você
  quiser revisar uma amostra. Nesse caso, a correção de prevalência de ANALYSIS §3.4 volta a ser possível.

## 6. Riscos de qualidade dos dados

| Risco | Efeito | Mitigação |
|---|---|---|
| **Classificação da IA tratada como fato** | conclusões falsas com aparência de precisão | camadas separadas; `v_label_resolved` explícita; κ publicado junto de cada estatística baseada em IA |
| **Viés de prevalência** do classificador | um classificador com 90% de acurácia ainda distorce proporções (por exemplo, se superestima "cenário") | sem gold humano não há correção formal; reportar a faixa entre modelos (V5) e afirmar só conclusões robustas |
| **Viés compartilhado entre modelos** | dois modelos concordam no erro | famílias diferentes; âncoras por regra (V2); limitação declarada |
| **Modelo gratuito descontinuado no meio do corpus** | rótulos de um modelo que não existe mais | `annotation_run` guarda o ID exato; trocar de modelo exige rodar de novo o corpus inteiro daquela variável, nunca misturar modelos numa mesma série |
| **Corpus não representativo** (sobra de provas antigas, falta das recentes; ver SPEC §5.3) | "perfil da FCC" vira "perfil da FCC até 2019" | registrar a composição do corpus em todo relatório; buscar fonte primária para 2023–2026; nunca extrapolar para período sem dados |
| **Confusão banca × órgão × cargo** | atribuir à FCC um traço que é dos tribunais de contas | desenho amostral cruzado e modelos com efeito de órgão (ANALYSIS §4) |
| **Dependência dentro da prova** | IC estreitos demais (n efetivo menor que o n de questões) | IC agrupados por prova (bootstrap por prova) |
| **Duplicatas entre cadernos** | infla a contagem | `text_hash` e `v_question_dedup` |
| **Gabarito preliminar × definitivo; anuladas** | rótulo de "correta" errado | usar sempre o definitivo; excluir anuladas das análises de alternativas |
| **Deriva de definição** (codebook muda e rótulos antigos ficam incompatíveis) | séries quebradas | `codebook_version` em cada rótulo; relabel ao mudar |
| **Erro de OCR** | métricas linguísticas contaminadas | MVP só com PDF de texto; `extraction_method` registrado |
| **Taxonomia inadequada** | tópicos de concordância baixa | taxonomia rasa (2 níveis) no MVP; subtópico exploratório |
| **Muitas comparações** | "achados" por acaso | registro de hipóteses e correção de Benjamini–Hochberg nas varreduras (ANALYSIS §5) |

## 7. Fontes de dados, direitos autorais e termos de uso

> Isto **não é parecer jurídico**: são sinalizações para decisão consciente.

| Fonte | Uso proposto | Sinalização |
|---|---|---|
| **Site da banca (FCC)** | **fonte principal** (decisão de 2026-11-20): edital do concurso-alvo e provas e gabaritos de concursos recentes | Verificar por quanto tempo os arquivos ficam disponíveis e se os termos do site restringem download em massa. Download pontual, concurso a concurso, com URL registrada. |
| **Diário Oficial / site do órgão** | editais, retificações, homologações | Atos oficiais são, em regra, excluídos da proteção autoral (Lei 9.610/98, art. 8º, IV). Menor risco. |
| **PCI Concursos** | **opcional**: catálogo e fonte de reserva para provas antigas (2013–2019) que a FCC não hospeda mais; MCP para metadados | O MCP oficial é uma interface de consulta e o uso dele é legítimo. **Não** construir scraper do site sem ler os termos e o robots.txt. O banco não depende do PCI: `origin='pci'` é só mais uma proveniência. |
| **Bancos comerciais** (QConcursos, TEC etc.) | no máximo referência manual | Os termos tipicamente proíbem extração. As classificações deles são dados de terceiros. **Não ingerir.** |
| **Texto das questões** | armazenado **só localmente** para análise | As provas são obras com autoria (da banca). O repositório é **público** (decisão de 2026-11-20), então o texto das questões, os PDFs e o banco **nunca** entram no git. O repositório publica código, documentação, codebook, rótulos (por chave da questão) e estatísticas agregadas. Quem clonar reconstrói o banco a partir das fontes oficiais. |
| **Textos legais (Planalto)** | base de literalidade (fase 2) | Leis não têm proteção autoral (art. 8º, IV). |

## 8. Extensibilidade (sem construir agora)

| Futuro | O que já está preparado |
|---|---|
| Outras bancas | parser por banca; `banca` como dimensão; `formato_resposta` suporta Certo/Errado |
| Histórico pessoal | `attempt` referencia `question` |
| Literalidade objetiva | `law_text` mais uma feature derivada nova; sem mudança de esquema |
| Mais volume | SQLite aguenta com folga centenas de milhares de questões. DuckDB lê o mesmo arquivo para análise pesada sem migração (ADR-002). |
