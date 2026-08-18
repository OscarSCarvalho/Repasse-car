-- Repasse CarApp — Schema v1
-- IMPORTANTE: ativar foreign keys em cada conexão: PRAGMA foreign_keys = ON

CREATE TABLE IF NOT EXISTS lojistas (
    id                INTEGER  PRIMARY KEY AUTOINCREMENT,
    nome_fantasia     TEXT     NOT NULL,
    razao_social      TEXT     NOT NULL,
    cnpj              TEXT     NOT NULL UNIQUE,
    email             TEXT     NOT NULL UNIQUE,
    senha_hash        TEXT     NOT NULL,
    telefone_whatsapp TEXT,
    cidade            TEXT     NOT NULL,
    uf                TEXT     NOT NULL CHECK(length(uf) = 2),
    ativo             INTEGER  NOT NULL DEFAULT 1 CHECK(ativo IN (0, 1)),
    criado_em         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS categorias_defeito (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    nome      TEXT    NOT NULL UNIQUE,
    descricao TEXT
);

CREATE TABLE IF NOT EXISTS selos_defeito (
    id                  INTEGER  PRIMARY KEY AUTOINCREMENT,
    categoria_id        INTEGER  NOT NULL REFERENCES categorias_defeito(id),
    nome                TEXT     NOT NULL,
    descricao           TEXT,
    campos_obrigatorios TEXT     NOT NULL DEFAULT '[]',  -- JSON array de nomes de campo
    exige_foto          INTEGER  NOT NULL DEFAULT 0 CHECK(exige_foto IN (0, 1))
);

CREATE TABLE IF NOT EXISTS veiculos (
    id             INTEGER  PRIMARY KEY AUTOINCREMENT,
    lojista_id     INTEGER  NOT NULL REFERENCES lojistas(id) ON DELETE CASCADE,
    marca          TEXT     NOT NULL,
    modelo         TEXT     NOT NULL,
    ano_fabricacao INTEGER  NOT NULL,
    ano_modelo     INTEGER  NOT NULL,
    versao         TEXT,
    cor            TEXT,
    kilometragem   INTEGER  NOT NULL CHECK(kilometragem >= 0),
    cambio         TEXT     NOT NULL CHECK(cambio IN ('manual','automatico','cvt')),
    combustivel    TEXT     NOT NULL CHECK(combustivel IN ('flex','gasolina','diesel','etanol','eletrico','hibrido')),
    placa          TEXT,
    preco          INTEGER  NOT NULL CHECK(preco > 0),      -- em centavos
    codigo_fipe    TEXT,
    valor_fipe     INTEGER,                                  -- em centavos
    descricao      TEXT,
    status         TEXT     NOT NULL DEFAULT 'rascunho'
                   CHECK(status IN ('rascunho','ativo','em_negociacao','vendido','cancelado')),
    criado_em      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS veiculo_selos (
    id                 INTEGER  PRIMARY KEY AUTOINCREMENT,
    veiculo_id         INTEGER  NOT NULL REFERENCES veiculos(id) ON DELETE CASCADE,
    selo_id            INTEGER  NOT NULL REFERENCES selos_defeito(id),
    campos_especificos TEXT     NOT NULL DEFAULT '{}',  -- JSON com os valores dos campos do selo
    criado_em          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(veiculo_id, selo_id)
);

CREATE TABLE IF NOT EXISTS fotos_veiculo (
    id              INTEGER  PRIMARY KEY AUTOINCREMENT,
    veiculo_id      INTEGER  NOT NULL REFERENCES veiculos(id) ON DELETE CASCADE,
    veiculo_selo_id INTEGER  REFERENCES veiculo_selos(id) ON DELETE SET NULL,  -- NULL = foto geral
    tipo            TEXT     NOT NULL CHECK(tipo IN ('geral','avaria','laudo')),
    caminho         TEXT     NOT NULL,
    descricao       TEXT,
    ordem           INTEGER  NOT NULL DEFAULT 0,
    criado_em       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS propostas (
    id                   INTEGER  PRIMARY KEY AUTOINCREMENT,
    veiculo_id           INTEGER  NOT NULL REFERENCES veiculos(id),
    lojista_comprador_id INTEGER  NOT NULL REFERENCES lojistas(id),
    valor                INTEGER  NOT NULL CHECK(valor > 0),  -- em centavos
    mensagem             TEXT,
    status               TEXT     NOT NULL DEFAULT 'pendente'
                         CHECK(status IN ('pendente','aceita','recusada','cancelada')),
    criado_em            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_veiculos_status     ON veiculos(status);
CREATE INDEX IF NOT EXISTS idx_veiculos_lojista    ON veiculos(lojista_id);
CREATE INDEX IF NOT EXISTS idx_veiculo_selos_vid   ON veiculo_selos(veiculo_id);
CREATE INDEX IF NOT EXISTS idx_fotos_veiculo_vid   ON fotos_veiculo(veiculo_id);
CREATE INDEX IF NOT EXISTS idx_fotos_selo          ON fotos_veiculo(veiculo_selo_id);
CREATE INDEX IF NOT EXISTS idx_propostas_veiculo   ON propostas(veiculo_id);
CREATE INDEX IF NOT EXISTS idx_propostas_comprador ON propostas(lojista_comprador_id);
