# Projeto: análise empírica de bancas de concurso (alvo: Auditor STC-MA no Concurso Unificado MA / FCC, prova em 04/04/2027)

Fase atual: **MVP — rotulagem v0 quase completa; relatório parcial em `reports/mvp_v0.md`.** Estado em 2026-11-24:
- FEITO: 1.280 questões extraídas (13 cadernos); features feat-0.3; codebook v0; rotulagem A×2 e B×2 (escopo de 142 questões, ADR-022);
  validação e relatório (`python -m concurso.report`).
- PENDENTE: A rep2 parou em 100/142 pela cota diária do Gemini (20 req/dia/modelo). Retomar com
  `.venv/Scripts/python -m concurso.classify run A 2` e depois `python -m concurso.report`.
- PRÓXIMO: codebook v1 (regra "fato escolhe a regra → aplicar_a_fatos"; avaliar fundir recordar + reconhecer), ADR-022.
- Achados de método: as âncoras pegaram 3 erros do parser (C08, C12); o consenso entre modelos subestima casos de fronteira.

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
