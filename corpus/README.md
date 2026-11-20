# Corpus do MVP

[candidatos.csv](candidatos.csv) lista as provas do MVP: só metadados públicos e links, sem texto de questões.
Critério: provas **FCC** de cargos de **controle, auditoria e fiscalização** que têm Direito
Administrativo, com órgãos variados (tribunais de contas, controladorias, fazendas, MP), para
separar o perfil da banca do perfil do órgão. C13 é um contraste de outro tipo de órgão (judiciário)
e é a única prova posterior à Lei 14.133/2021.

| Papel | Uso |
|---|---|
| `spike` | C01–C02: testar a extração de PDF primeiro |
| `mvp` | C03–C12: corpus principal |
| `contraste` | C13: tipo de órgão diferente e período recente |

## Como baixar (manual, ~15 min)

O PCI protege os downloads com CAPTCHA, então não há download automático (ADR-015).

1. Abra o link da linha em `candidatos.csv`.
2. Resolva o CAPTCHA e baixe **dois arquivos**: a **prova** (em geral `prova-...-tipo-001.pdf`) e os **gabaritos**.
3. Salve os dois em `data/inbox/<corpus_id>/`, por exemplo `data/inbox/C01/`. As pastas já existem.
   Não renomeie os arquivos.
4. Depois rode `python -m concurso.ingest inbox`, que registra tudo com hash e proveniência.

`data/` fica fora do git: os PDFs nunca são publicados.

## Limitações conhecidas do corpus
- **Período:** 2013–2018, mais uma prova de 2022. O acervo FCC do PCI quase não tem provas posteriores a 2019, e o site da FCC não lista cadernos antigos.
- **Licitações:** as provas até 2021 cobram a Lei 8.666/1993, e o edital-alvo cobra a Lei 14.133/2021. Os achados *estruturais* (como a FCC formula) continuam úteis; os de *conteúdo* de licitação precisam dessa ressalva.
- **Banca anterior do órgão:** o concurso anterior da STC-MA (2013) foi da FGV. Ele fica para a fase 2 (comparação mesmo órgão × banca diferente).
