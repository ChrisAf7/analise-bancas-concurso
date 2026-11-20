-- 001_init: esquema inicial (docs/DATA_MODEL.md §3). Aplicado por `python -m concurso.db migrate`.

-- ===== Proveniência =====
CREATE TABLE source_document (
  id            INTEGER PRIMARY KEY,
  kind          TEXT NOT NULL CHECK (kind IN
                 ('prova','gabarito_preliminar','gabarito_definitivo','gabarito','edital','retificacao','outro')),
  origin        TEXT NOT NULL,          -- 'fcc_site','orgao_site','diario_oficial','pci','manual'
  url           TEXT,
  retrieved_at  TEXT NOT NULL,
  sha256        TEXT NOT NULL UNIQUE,
  local_path    TEXT NOT NULL,          -- relativo a data/raw/
  corpus_id     TEXT,                   -- ex.: 'C01' (corpus/candidatos.csv)
  notes         TEXT
);

-- ===== Dimensões =====
CREATE TABLE banca (
  id INTEGER PRIMARY KEY, sigla TEXT NOT NULL UNIQUE, nome TEXT
);

CREATE TABLE orgao (
  id INTEGER PRIMARY KEY,
  sigla TEXT NOT NULL UNIQUE, nome TEXT, uf TEXT,
  esfera TEXT CHECK (esfera IN ('federal','estadual','municipal')),
  tipo   TEXT
);

CREATE TABLE concurso (
  id INTEGER PRIMARY KEY,
  banca_id INTEGER NOT NULL REFERENCES banca(id),
  orgao_id INTEGER NOT NULL REFERENCES orgao(id),
  ano INTEGER NOT NULL,
  nome TEXT,
  edital_document_id INTEGER REFERENCES source_document(id),
  UNIQUE (banca_id, orgao_id, ano, nome)
);

CREATE TABLE prova (
  id INTEGER PRIMARY KEY,
  concurso_id INTEGER NOT NULL REFERENCES concurso(id),
  corpus_id TEXT UNIQUE,
  data_aplicacao TEXT,
  tipo_caderno TEXT,
  formato_resposta TEXT NOT NULL DEFAULT 'multipla_escolha'
                   CHECK (formato_resposta IN ('multipla_escolha','certo_errado')),
  n_questoes_esperado INTEGER,
  source_document_id INTEGER NOT NULL REFERENCES source_document(id),
  gabarito_document_id INTEGER REFERENCES source_document(id)
);

CREATE TABLE prova_cargo (
  prova_id INTEGER NOT NULL REFERENCES prova(id),
  cargo_texto TEXT NOT NULL,
  cargo_normalizado TEXT,
  PRIMARY KEY (prova_id, cargo_texto)
);

-- ===== Taxonomia =====
CREATE TABLE taxonomy_node (
  id INTEGER PRIMARY KEY,
  parent_id INTEGER REFERENCES taxonomy_node(id),
  nivel TEXT NOT NULL CHECK (nivel IN ('disciplina','topico','subtopico')),
  slug  TEXT NOT NULL,
  nome  TEXT NOT NULL,
  descricao TEXT,
  taxonomy_version TEXT NOT NULL,
  UNIQUE (slug, taxonomy_version)
);

CREATE TABLE disciplina_alias (
  rotulo TEXT PRIMARY KEY,
  taxonomy_node_id INTEGER NOT NULL REFERENCES taxonomy_node(id)
);

CREATE TABLE edital_item (
  id INTEGER PRIMARY KEY,
  concurso_id INTEGER NOT NULL REFERENCES concurso(id),
  cargo TEXT NOT NULL,
  disciplina_rotulo TEXT NOT NULL,
  ordem INTEGER,
  texto TEXT NOT NULL,
  UNIQUE (concurso_id, cargo, disciplina_rotulo, ordem)
);

CREATE TABLE edital_item_map (       -- mapeamento item do edital -> nós da taxonomia (n:n)
  edital_item_id INTEGER NOT NULL REFERENCES edital_item(id),
  taxonomy_node_id INTEGER NOT NULL REFERENCES taxonomy_node(id),
  PRIMARY KEY (edital_item_id, taxonomy_node_id)
);

-- ===== Questões (observado) =====
CREATE TABLE question (
  id INTEGER PRIMARY KEY,
  prova_id INTEGER NOT NULL REFERENCES prova(id),
  numero INTEGER NOT NULL,
  question_key TEXT NOT NULL UNIQUE,
  disciplina_rotulo TEXT,
  texto_base TEXT,
  enunciado TEXT NOT NULL,
  gabarito_preliminar TEXT,
  gabarito_definitivo TEXT,
  status TEXT NOT NULL DEFAULT 'valida' CHECK (status IN ('valida','anulada','alterada')),
  text_hash TEXT NOT NULL,
  extraction_method TEXT NOT NULL,
  verified_by_human INTEGER NOT NULL DEFAULT 0,
  UNIQUE (prova_id, numero)
);

CREATE TABLE alternative (
  question_id INTEGER NOT NULL REFERENCES question(id),
  letra TEXT NOT NULL,
  texto TEXT NOT NULL,
  PRIMARY KEY (question_id, letra)
);

-- ===== Derivado =====
CREATE TABLE question_feature (
  question_id INTEGER NOT NULL REFERENCES question(id),
  alternativa TEXT NOT NULL DEFAULT '',
  name TEXT NOT NULL,
  value_num REAL, value_text TEXT,
  extractor_version TEXT NOT NULL,
  PRIMARY KEY (question_id, alternativa, name)
);

-- ===== Classificação =====
CREATE TABLE annotation_run (
  id INTEGER PRIMARY KEY,
  annotator_type TEXT NOT NULL CHECK (annotator_type IN ('llm','human','rule')),
  annotator_id TEXT NOT NULL,           -- 'A:gemini-3.5-flash' etc.
  provider TEXT,
  model_reported TEXT,
  prompt_version TEXT,
  codebook_version TEXT NOT NULL,
  params_json TEXT,
  purpose TEXT,
  repeticao INTEGER,                    -- 1 ou 2 (estabilidade)
  blind INTEGER,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  notes TEXT
);

CREATE TABLE annotation (
  id INTEGER PRIMARY KEY,
  run_id INTEGER NOT NULL REFERENCES annotation_run(id),
  question_id INTEGER NOT NULL REFERENCES question(id),
  alternativa TEXT NOT NULL DEFAULT '',
  campo TEXT NOT NULL,
  valor TEXT NOT NULL,
  confianca REAL,
  evidencia TEXT,
  justificativa TEXT,
  created_at TEXT NOT NULL,
  UNIQUE (run_id, question_id, alternativa, campo, valor)
);

CREATE INDEX ix_question_prova ON question(prova_id);
CREATE INDEX ix_annotation_q ON annotation(question_id, campo);
