# DECISIONS — Registro de decisões arquiteturais

> Formato curto de ADR. **Status:** `proposta`, `aceita` ou `substituída por ADR-NNN`.
> Novas decisões entram no fim, com número sequencial. A partir de agora, uma decisão aceita não é
> editada; se mudar, é substituída por uma nova ADR.

## Respostas do usuário (2026-11-20)

| ID | Pergunta | Resposta | Efeito |
|---|---|---|---|
| P0 | Qual é o concurso-alvo? | A prova da STC-MA está dentro do **Concurso Unificado do Maranhão**, com várias secretarias. A banca **FCC** foi confirmada na imprensa. | SPEC §5.2 |
| P1 | Repositório público ou privado? | **Público** | ADR-013 |
| P2 | Como rodar a IA? | **Só modelos gratuitos**; o usuário configura contas se for preciso | ADR-012, [SETUP_IA.md](SETUP_IA.md) |
| P3 | Disciplina do MVP | Delegada ao Claude: **Direito Administrativo** (está nos Conhecimentos Específicos do Auditor) | SPEC §6 |
| P4 | Rotulagem humana | **Nenhuma** | ADR-012, ARCHITECTURE §5 |
| P5 | Base da taxonomia | Delegada: **edital oficial do Concurso Unificado MA**, conteúdo do Auditor – Área Geral | ADR-008 |
| P6 | Análise temporal fora do MVP | Delegada: aceita | ANALYSIS §3.5 |
| P7 | Inicializar o git | Delegada: feito (sem commit, ver pendência G1) | ADR-013 |
| — | Fonte dos dados | Delegada: **FCC como fonte principal**, PCI opcional | ADR-014 |

## Pendências pequenas (todas resolvidas em 2026-11-20)

| ID | Pendência | Resolução |
|---|---|---|
| **G1** | E-mail pessoal visível nos commits públicos | `user.email` local deste repositório configurado com o *noreply* do GitHub |
| **G2** | Licença | MIT (arquivo `LICENSE`, criado pelo usuário no GitHub) |
| **K1** | Chaves gratuitas (Gemini e OpenRouter) | Criadas e salvas em `.env`, que o git ignora. Ainda falta testar as chaves no spike. |
| — | Repositório remoto | <https://github.com/ChrisAf7/analise-bancas-concurso> (público) |

---

## ADR-001 — Python 3.13 com venv e pyproject.toml
**Status:** aceita
- **Decisão:** Python 3.13 (já instalado), ambiente `venv` da biblioteca padrão e dependências declaradas em `pyproject.toml`.
- **Alternativas:** `uv` (rápido e maduro, mas é mais uma ferramenta); Poetry; conda (pesado; só faria sentido com dependências científicas compiladas, o que não é o caso).
- **Motivo:** zero instalação nova, padrão e suficiente para cerca de 8 dependências. Trocar para `uv` depois é trivial, porque ele lê o mesmo `pyproject.toml`.

## ADR-002 — SQLite como sistema de registro
**Status:** aceita
- **Decisão:** um único arquivo `data/concurso.sqlite`, acessado pelo `sqlite3` da biblioteca padrão. As análises carregam em `pandas`.
- **Alternativas:** DuckDB (ótimo para análise colunar, mais fraco como base transacional de curadoria; consegue ler o arquivo SQLite diretamente, então pode entrar depois sem migração); PostgreSQL (exige servidor); CSV ou Parquet soltos (sem integridade nem proveniência).
- **Motivo:** integridade (FK, CHECK, transações), um arquivo só, maturidade e zero infraestrutura.

## ADR-003 — SQL puro com migrações numeradas, sem ORM
**Status:** aceita
- **Decisão:** `db/migrations/NNN_*.sql` aplicadas em ordem por um script curto que controla `PRAGMA user_version`.
- **Alternativas:** SQLAlchemy com Alembic; `sqlite-utils`.
- **Motivo:** o esquema é pequeno, e as consultas analíticas são SQL de qualquer forma.

## ADR-004 — Biblioteca de extração de PDF: decidir por spike
**Status:** aceita (2026-11-24) — **pdfplumber**. Resultado do spike no fim desta ADR.
- **Candidatas:** `pdfplumber` (MIT, extração por coordenadas); `PyMuPDF` (rápida, boa com duas colunas, **licença AGPL**); `pypdf` (simples, pior com layout).
- **Critério:** em 2 cadernos FCC reais, a fração de questões segmentadas corretamente (meta ≥ 95%), os acentos, a hifenização e a ordem das colunas. Ganha a mais simples que bater a meta.
- **Nota (repositório público):** a AGPL do PyMuPDF obrigaria o código do projeto a ser AGPL se fosse distribuído junto. Isso pesa a favor do `pdfplumber` em caso de empate.
- **Resultado (2026-11-24):** as duas bibliotecas acertam quando a página é cortada por colunas. O pdfplumber dá texto mais limpo (sem recuo), leva 0,14 s por página (suficiente) e tem licença MIT. O PyMuPDF saiu das dependências.
- **Como a ordem de leitura é resolvida (`src/concurso/pdftext.py`):** palavras com coordenadas; a página é de coluna única se a maioria das linhas não tiver vão no centro; nas páginas de duas colunas, as linhas que atravessam o centro (títulos centralizados) dividem a página em faixas, lidas esquerda → direita. Os separadores `____` são ignorados nesse teste.
- **Resultado no corpus:** 13 cadernos, 16 partes, **1.280 questões, 100% aprovadas nas verificações estruturais** (numeração contínua, A–E completas, contagem igual à da capa e à do gabarito).

## ADR-005 — Claude via API paga
**Status:** substituída por ADR-012 (o usuário não quer modelo pago)

## ADR-006 — Quatro camadas e anotação com proveniência
**Status:** aceita
- **Decisão:** dados observados, derivados, classificações e hipóteses ficam em lugares diferentes ([DATA_MODEL §2](DATA_MODEL.md)). Toda classificação é uma linha em `annotation` ligada a um `annotation_run` com provedor, modelo exato, versão do prompt, versão do codebook e data.
- **Alternativa rejeitada:** colunas como `question.tem_cenario`. Apagaria a origem e impediria comparar modelos.

## ADR-007 — O que entra no git
**Status:** substituída por ADR-013 (repositório público)

## ADR-008 — Taxonomia própria, mapeada para o edital
**Status:** aceita
- **Decisão:** a tabela `taxonomy_node` é versionada e tem 2 níveis no MVP (disciplina → tópico). A taxonomia v0 sai do conteúdo programático de Direito Administrativo do **Auditor – Área Geral** no edital oficial do Concurso Unificado MA (FCC, 2026). Os itens do edital ficam em `edital_item` e são mapeados para a taxonomia.
- **Alternativas:** usar a redação do edital diretamente (impede comparar concursos); copiar a taxonomia de um banco comercial (dado de terceiros).

## ADR-009 — Rotulagem humana por planilha
**Status:** substituída por ADR-012 (não haverá rotulagem humana)

## ADR-010 — PCI como catálogo, não como base
**Status:** substituída por ADR-014

## ADR-011 — Unidade de agrupamento estatístico = caderno de prova
**Status:** aceita
- **Decisão:** todos os IC e erros-padrão são agrupados por `prova` (caderno).
- **Motivo:** as questões de um caderno compartilham elaboradores e estilo; tratá-las como independentes produz falsa precisão.

## ADR-012 — IA só com modelos gratuitos, dois avaliadores, validação sem humano
**Status:** aceita (2026-11-20)
- **Contexto:** o usuário não quer modelo pago nem rotular questões.
- **Decisão:**
  1. Cliente único **compatível com o protocolo da OpenAI** (pacote `openai` com `base_url` configurável). Ele atende Google AI Studio, OpenRouter e Ollama sem código específico por provedor.
  2. **Avaliador A:** Gemini no plano gratuito do Google AI Studio (sem cartão). **Avaliador B:** um modelo aberto de outra família pelo OpenRouter, só modelos `:free`. Os modelos exatos são escolhidos no spike, conforme a disponibilidade do dia, e ficam em `config/models.toml`.
  3. Várias questões por chamada (5–10) para caber nos limites gratuitos (OpenRouter sem créditos: 20 requisições por minuto e 50 por dia).
  4. Validação sem humano: âncoras por regra, κ entre modelos, estabilidade entre execuções e sensibilidade das conclusões (ARCHITECTURE §5).
- **Alternativas consideradas:**
  - *Ollama local* (gratuito, ilimitado e privado): esta máquina tem 16 GB de RAM e nenhuma GPU dedicada foi detectada, então modelos de ~8B rodariam na CPU, devagar e com qualidade menor em texto jurídico em português. Fica como **avaliador C opcional**.
  - *Um único modelo gratuito:* mais simples, mas sem humano não haveria nenhuma medida de confiabilidade. Rejeitado.
  - *Claude via API:* pago. Rejeitado pelo usuário.
- **Consequências e limitações:** a concordância entre modelos mede confiabilidade, não validade, e isso é declarado em todo relatório. Os planos gratuitos podem usar as entradas para treino, o que é aceitável porque só texto de provas públicas é enviado. Os modelos gratuitos podem sumir; uma série nunca mistura modelos.

## ADR-013 — Repositório público: o que entra e o que fica fora do git
**Status:** aceita (2026-11-20)
- **Entra:** código, docs, diagramas, codebook, prompts, migrações, testes, `config/models.toml`, `.env.example`, **rótulos exportados por chave natural da questão** (`exports/annotations/*.jsonl`, sem texto) e tabelas agregadas.
- **Nunca entra:** `data/` inteiro (PDFs, banco SQLite com texto das questões), `.env` (chaves).
- **Motivo:** as questões são obras da banca. Publicar só identificadores, rótulos e estatísticas mantém o projeto reprodutível, porque qualquer pessoa reconstrói o banco a partir das fontes oficiais, sem republicar provas.
- **Pendência G1:** usar o e-mail *noreply* do GitHub nos commits.

## ADR-014 — Fontes: FCC primeiro, PCI opcional
**Status:** aceita (2026-11-20)
- **Decisão:** o edital e as provas recentes vêm do **site da FCC** (`concursosfcc.com.br`). As provas antigas (2013–2019) vêm da FCC quando disponíveis; senão, do PCI ou do site do órgão, com `source_document.origin` registrando a origem. O MCP do PCI é usado só como catálogo.
- **Motivo:** fonte primária primeiro; o acervo FCC do PCI é fraco depois de 2019; o banco não depende de nenhum agregador.
- **Coleta:** download pontual e registrado, concurso a concurso. Nada de crawler em massa sem antes ler os termos do site.

## ADR-015 — Download manual dos PDFs do corpus
**Status:** aceita (2026-11-20)
- **Contexto:** o PCI exige CAPTCHA para baixar provas, e as páginas de concurso da FCC não listam cadernos de concursos antigos (carregam resultados por JavaScript e só publicam editais e comunicados).
- **Decisão:** o usuário baixa à mão os cerca de 26 PDFs (prova e gabarito de 13 cadernos) para `data/inbox/Cxx/`; `python -m concurso.ingest inbox` registra hash, origem e URL. **Não** contornar CAPTCHA nem automatizar downloads no PCI.
- **Alternativas rejeitadas:** resolver ou burlar o CAPTCHA (viola a intenção explícita do site); bancos comerciais de questões (termos de uso proíbem extração).
- **Futuro:** para provas recentes, verificar os PDFs publicados pela FCC durante o concurso (por exemplo, o caderno do concurso-alvo após 04/04/2027).

## ADR-016 — Avaliadores escolhidos no teste de fumaça
**Status:** aceita (2026-11-20)
- **Teste:** `python -m concurso.llm smoke` com uma questão sintética. Os três avaliadores responderam com JSON válido e com o mesmo rótulo.
- **A:** `gemini-3.5-flash` (Google AI Studio, plano gratuito); ~50 s por chamada, provavelmente por raciocínio interno.
- **B:** `nvidia/nemotron-3-ultra-550b-a55b:free` (OpenRouter); ~12 s.
- **B_reserva:** `baidu/ernie-5.5-flash-preview:free`; ~3 s.
- Os modelos Gemma, embora gratuitos, ficaram de fora como B por serem da mesma empresa do avaliador A.
- Os IDs ficam em `config/models.toml`. Cada `annotation_run` grava o ID que o provedor devolveu.

## ADR-017 — Gabarito do C11 transcrito à mão
**Status:** aceita (2026-11-24)
- **Contexto:** o gabarito do C11 (Pref. São Luís 2018) no PCI é só imagem.
- **Decisão:** transcrever as 100 respostas do bloco A01 para `corpus/gabaritos_manuais/C11.txt` (versionado: respostas oficiais são dado público, não texto de questão). O parser prefere a transcrição manual quando ela existe e grava `prova.gabarito_origem` com o caminho dela.
- **Alternativa rejeitada:** OCR (Tesseract ou similar), uma dependência nova para um único arquivo.
- **Validação:** a contagem bate com as 100 questões extraídas. A conferência letra a letra ainda depende de uma segunda fonte; risco registrado.

## ADR-018 — Escopo da classificação por IA no MVP
**Status:** aceita (2026-11-24)
- **Corpus extraído:** 1.280 questões, sendo 559 de disciplinas jurídicas e **122 de Direito Administrativo**, pelos rótulos observados "Direito Administrativo", "Direito Administrativo I" e "Noções de Direito Administrativo".
- **Decisão:** o MVP classifica por IA as 122 questões de Direito Administrativo, mais as 40 questões sem título de disciplina dos Conhecimentos Específicos do C10. Nessas 40, a IA também rotula a disciplina e só as de Direito Administrativo entram na análise. São cerca de 160 questões, dentro da meta de 150–250 (SPEC §6).
- **Fase seguinte:** as 559 questões jurídicas, para responder Q1 ("em Direito…") de forma geral.
- **Features derivadas** valem para todas as 1.280 questões desde já (`python -m concurso.features build`).
- **Achado que afeta a validação (V2):** o marcador explícito de cenário ("situação hipotética") aparece em só 0,4% das questões; a FCC monta cenários com "determinado Município…" e nomes próprios. As âncoras de cenário terão poucos casos. Por isso o V2 usará também âncoras de comando e formato (derivadas, alta precisão) e de fonte normativa (citação de tribunal ou dispositivo).

## ADR-019 — Marca d'água do PCI contém dado pessoal
**Status:** aceita (2026-11-24)
- **Achado:** cada PDF baixado do PCI traz uma marca oculta `pcimarkpci <base64>` com o **endereço IP e a data e hora do download** de quem baixou.
- **Decisão:** (1) os PDFs nunca entram no git, como já previa o ADR-013; (2) a marca, o rodapé do PCI e os artefatos `(cid:N)` são removidos palavra por palavra na extração (`pdftext._NOISE_WORD`), antes de qualquer outro estágio, e nunca chegam ao banco nem a um LLM; (3) uma verificação confirmou 0 ocorrências no banco após a carga.
