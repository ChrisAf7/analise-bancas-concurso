# Projeto: análise empírica de bancas de concurso (alvo: Auditor STC-MA no Concurso Unificado MA / FCC, prova em 04/04/2027)

Fase atual: **especificação aprovada (2026-11-20); MVP ainda não implementado.** Próximo passo:
etapa 0–1 do MVP (edital → taxonomia; spike de extração de PDF e teste das chaves gratuitas), ver docs/SPEC.md §6.

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
