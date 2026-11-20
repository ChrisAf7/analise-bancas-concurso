# Projeto: análise empírica de bancas de concurso (alvo: Auditor STC-MA no Concurso Unificado MA / FCC, prova em 04/04/2027)

Fase atual: **MVP em andamento.** Estado em 2026-11-20:
- FEITO: edital oficial registrado; taxonomia `taxonomy/dir_adm_v0.toml` carregada; banco (`python -m concurso.db migrate`);
  registro de fontes (`concurso.ingest`); cliente de IA testado com os 3 avaliadores (`python -m concurso.llm smoke`).
- AGUARDANDO O USUÁRIO: download manual dos PDFs do corpus para `data/inbox/Cxx/` (corpus/README.md; ADR-015).
- PRÓXIMO: `python -m concurso.ingest inbox` → spike de extração com C01–C02 (pdfplumber × PyMuPDF, ADR-004) →
  parser FCC + verificações → features → codebook v0 → rotulagem A/B → validação → relatório.

Ambiente: `.venv` (Python 3.13), projeto instalado em modo editável (`pip install -e .`). Rode módulos com `.venv/Scripts/python -m concurso.<módulo>`.

Leia nesta ordem: docs/SPEC.md → docs/DATA_MODEL.md (com diagrams/data_model.png) → docs/ARCHITECTURE.md
→ docs/ANALYSIS.md → docs/DECISIONS.md. Configuração de chaves: docs/SETUP_IA.md.
O briefing original do usuário está em `Quero desenvolver neste repositório.txt`.

Restrições do usuário (2026-11-20):
- **Só modelos de IA gratuitos** (Gemini no AI Studio e OpenRouter `:free`; Ollama opcional). Nada de API paga.
- **Repositório público**: texto de questões, PDFs, banco e `.env` nunca entram no git (ADR-013).
- **Nenhuma rotulagem humana**: validação por âncoras de regra, concordância entre modelos, estabilidade e sensibilidade (ARCHITECTURE §5).
- O usuário quer ganhar tempo: decidir o que for técnico sem perguntar, registrando como ADR.

Regras que não se negociam:
- Separar observado / derivado / classificação / hipótese. Classificação sempre com proveniência (`annotation` + `annotation_run`).
- Nenhuma estatística gerada por IA: todo número vem de código sobre o banco.
- O LLM nunca transcreve nem altera o texto das questões.
- FCC é a fonte principal; o PCI é opcional. Nada de crawler em massa sem ler os termos do site.
- Sem overengineering: Python, SQLite, SQL puro, scripts de CLI. Novas dependências precisam de ADR.
