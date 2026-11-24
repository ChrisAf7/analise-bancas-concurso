# Projeto: análise empírica de bancas de concurso (alvo: Auditor STC-MA no Concurso Unificado MA / FCC, prova em 04/04/2027)

Fase atual: **MVP em andamento.** Estado em 2026-11-24:
- FEITO: edital + taxonomia `taxonomy/dir_adm_v0.toml`; 13 provas registradas (27 PDFs + gabarito manual do C11);
  parser FCC (`python -m concurso.parse_fcc load`) → 1.280 questões, 16 partes, 100% aprovadas nas verificações;
  features derivadas (`python -m concurso.features build`); testes (`python -m pytest tests`).
- PRÓXIMO: codebook v0 (cenario, demanda_cognitiva, fonte_normativa, topico; mais disciplina para C10) → rotulagem A/B ×2
  (escopo: ADR-018) → validação (ARCHITECTURE §5) → relatório.
- Escopo da IA no MVP: 122 questões de Dir. Adm. + 40 do C10 (ADR-018). Privacidade: ADR-019.

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
