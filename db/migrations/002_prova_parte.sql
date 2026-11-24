-- 002: um PDF de prova pode conter mais de um caderno (ex.: C12 = Conhecimentos Gerais + Básicos),
-- e um corpus_id pode ter mais de um PDF (ex.: C02). Cada caderno vira uma linha de `prova`
-- identificada por (corpus_id, parte). As tabelas ainda estão vazias quando esta migração roda.
DROP TABLE prova_cargo;
DROP TABLE prova;

CREATE TABLE prova (
  id INTEGER PRIMARY KEY,
  concurso_id INTEGER NOT NULL REFERENCES concurso(id),
  corpus_id TEXT NOT NULL,
  parte INTEGER NOT NULL DEFAULT 1,
  secao TEXT,                            -- ex.: 'Conhecimentos Gerais' (rótulo do bloco do gabarito)
  caderno_codigo TEXT,                   -- ex.: 'A01' (do cabeçalho "Caderno de Prova 'A01', Tipo 001")
  tipo_caderno TEXT,
  data_aplicacao TEXT,
  formato_resposta TEXT NOT NULL DEFAULT 'multipla_escolha'
                   CHECK (formato_resposta IN ('multipla_escolha','certo_errado')),
  n_questoes_esperado INTEGER,
  source_document_id INTEGER NOT NULL REFERENCES source_document(id),
  gabarito_document_id INTEGER REFERENCES source_document(id),
  gabarito_origem TEXT,                  -- 'pdf' ou caminho da transcrição manual (corpus/gabaritos_manuais/...)
  UNIQUE (corpus_id, parte)
);

CREATE TABLE prova_cargo (
  prova_id INTEGER NOT NULL REFERENCES prova(id),
  cargo_texto TEXT NOT NULL,
  cargo_normalizado TEXT,
  PRIMARY KEY (prova_id, cargo_texto)
);
