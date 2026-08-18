"""
Seed de dados para desenvolvimento.
Execute após criar o banco:
    python database/seed.py
"""
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from werkzeug.security import generate_password_hash

DB_PATH    = Path(__file__).parent / "repasse.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text(encoding='utf-8'))

    # ── Categorias de Defeito ──────────────────────────────────────────────────
    conn.executemany(
        "INSERT OR IGNORE INTO categorias_defeito (id, nome, descricao) VALUES (?,?,?)",
        [
            (1, 'origem_leilao',    'Veículos provenientes de leilão ou situação equivalente'),
            (2, 'defeito_mecanico', 'Componentes mecânicos com falha ou desgaste severo'),
            (3, 'defeito_estetico', 'Danos visíveis à carroceria, interior ou vidros'),
            (4, 'documentacao',     'Pendências documentais que complicam a transferência'),
        ],
    )

    # ── Selos de Defeito ───────────────────────────────────────────────────────
    conn.executemany(
        """INSERT OR IGNORE INTO selos_defeito
           (id, categoria_id, nome, descricao, campos_obrigatorios, exige_foto)
           VALUES (?,?,?,?,?,?)""",
        [
            # origem_leilao
            (1,  1, 'Sinistro recuperável',
             'Veículo com perda parcial indenizada por seguradora',
             json.dumps(['numero_laudo', 'orgao_leilao', 'percentual_perda']), 0),
            (2,  1, 'Roubo/furto recuperado',
             'Veículo recuperado após registro de BO',
             json.dumps(['numero_laudo', 'orgao_leilao']), 0),
            (3,  1, 'Fim de frota/locadora',
             'Veículo descontinuado de frota corporativa ou locadora',
             json.dumps(['orgao_leilao']), 0),
            (4,  1, 'Judicial',
             'Veículo leiloado por determinação judicial',
             json.dumps(['numero_laudo', 'orgao_leilao']), 0),
            # defeito_mecanico
            (5,  2, 'Motor',     'Falha ou desgaste no motor',
             json.dumps(['diagnostico', 'orcamento_reparo']), 1),
            (6,  2, 'Câmbio',    'Falha no câmbio manual ou automático',
             json.dumps(['diagnostico', 'orcamento_reparo']), 1),
            (7,  2, 'Suspensão', 'Componentes de suspensão danificados',
             json.dumps(['diagnostico', 'orcamento_reparo']), 1),
            (8,  2, 'Elétrica',  'Falha no sistema elétrico/eletrônico',
             json.dumps(['diagnostico', 'orcamento_reparo']), 1),
            # defeito_estetico
            (9,  3, 'Lataria/pintura', 'Amassados, riscos ou ferrugem na carroceria',
             json.dumps(['localizacao_avaria']), 1),
            (10, 3, 'Interior',        'Danos em bancos, painel ou revestimentos',
             json.dumps(['localizacao_avaria']), 1),
            (11, 3, 'Vidros',          'Trincas, quebras ou arranhões em vidros',
             json.dumps(['localizacao_avaria']), 1),
            # documentacao
            (12, 4, 'Financiamento em aberto',
             'Veículo com alienação fiduciária ativa',
             json.dumps(['situacao_resolver', 'prazo_estimado']), 0),
            (13, 4, 'IPVA atrasado',
             'Débitos de IPVA pendentes',
             json.dumps(['situacao_resolver', 'prazo_estimado']), 0),
            (14, 4, 'Restrição judicial',
             'Bloqueio ou penhora por decisão judicial',
             json.dumps(['situacao_resolver', 'prazo_estimado']), 0),
        ],
    )

    # ── Lojistas ───────────────────────────────────────────────────────────────
    senha = generate_password_hash('Senha@123')
    conn.executemany(
        """INSERT OR IGNORE INTO lojistas
           (id, nome_fantasia, razao_social, cnpj, email, senha_hash,
            telefone_whatsapp, cidade, uf)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        [
            (1, 'Pinheiro Multimarcas',  'Pinheiro Veículos Ltda',    '11222333000181',
             'contato@pinheiro.com.br',  senha, '11998887766', 'São Paulo',      'SP'),
            (2, 'Auto Center Gomes',     'Gomes Automóveis Eireli',   '22333444000181',
             'vendas@gomes.com.br',      senha, '21997776655', 'Rio de Janeiro', 'RJ'),
            (3, 'Veículos Express',      'Express Trading Ltda',      '33444555000181',
             'compras@express.com.br',   senha, '31996665544', 'Belo Horizonte', 'MG'),
            (4, 'Supercar Multimarcas',  'Supercar Importados Ltda',  '44555666000181',
             'vendas@supercar.com.br',   senha, '41995554433', 'Curitiba',       'PR'),
        ],
    )

    # ── Veículos ───────────────────────────────────────────────────────────────
    conn.executemany(
        """INSERT OR IGNORE INTO veiculos
           (id, lojista_id, marca, modelo, ano_fabricacao, ano_modelo,
            versao, cor, kilometragem, cambio, combustivel,
            preco, codigo_fipe, valor_fipe, descricao, status)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        [
            # 1 — Sinistro recuperável
            (1,  1, 'Fiat',      'Siena',    2016, 2017, 'EL 1.4',          'Prata',
             85000,  'manual',    'flex', 2800000,  '001004-3', 3200000,
             'Sinistro parcial, laudo aprovado, pronto para transferência.', 'ativo'),
            # 2 — Roubo recuperado + lataria
            (2,  2, 'Chevrolet', 'Cruze',    2019, 2020, 'LT 1.4 Turbo',    'Branco',
             62000,  'automatico','flex', 5200000,  '003021-1', 6800000,
             'Recuperado de roubo + amassado lateral esquerdo.', 'ativo'),
            # 3 — Defeito motor
            (3,  1, 'Toyota',    'Corolla',  2020, 2021, 'XEi 2.0',         'Preto',
             41000,  'automatico','flex', 8700000,  '005012-0', 10200000,
             'Motor com consumo excessivo de óleo, diagnóstico de junta de cabeçote.', 'ativo'),
            # 4 — Lataria/pintura
            (4,  3, 'Honda',     'Fit',      2018, 2018, 'EX 1.5',          'Azul',
             73000,  'automatico','flex', 4900000,  '007005-2', 5800000,
             'Amassado em porta traseira direita e lateral.', 'ativo'),
            # 5 — Financiamento em aberto
            (5,  4, 'Ford',      'Ka',       2019, 2020, 'SE 1.0',          'Vermelho',
             98000,  'manual',    'flex', 2400000,  '010003-5', 2900000,
             'Financiamento ativo no nome do dono anterior.', 'ativo'),
            # 6 — Defeito câmbio
            (6,  2, 'Volkswagen','Polo',     2021, 2021, 'Comfortline 1.0', 'Cinza',
             35000,  'automatico','flex', 7200000,  '014008-4', 8100000,
             'Câmbio DSG com falha no solenóide, orçamento em mão.', 'ativo'),
            # 7 — Interior danificado
            (7,  3, 'Hyundai',   'HB20',     2020, 2021, 'Vision 1.0',      'Branco',
             67000,  'manual',    'flex', 3800000,  '019002-1', 4300000,
             'Interior com bancos dianteiros danificados por incêndio parcial.', 'ativo'),
            # 8 — Fim de frota/locadora
            (8,  1, 'Renault',   'Sandero',  2018, 2019, 'Stepway 1.6',     'Laranja',
             110000, 'manual',    'flex', 2900000,  '020005-7', 3500000,
             'Leilão de frota Localiza, com desgaste normal de uso intenso.', 'ativo'),
            # 9 — Elétrica + IPVA atrasado
            (9,  4, 'Jeep',      'Renegade', 2019, 2020, 'Sport 1.8',       'Verde',
             88000,  'automatico','flex', 6100000,  '022010-3', 7200000,
             'Falha no módulo de injeção + IPVA 2022-2023 em aberto.', 'ativo'),
            # 10 — Judicial + vidro trincado
            (10, 2, 'Nissan',    'Versa',    2021, 2022, 'Advance 1.6',     'Prata',
             29000,  'automatico','flex', 6800000,  '025003-9', 7500000,
             'Leilão judicial + parabrisa trincado no canto inferior.', 'ativo'),
        ],
    )

    # ── Veiculo Selos ──────────────────────────────────────────────────────────
    # IDs explícitos para referenciar em fotos_veiculo
    conn.executemany(
        """INSERT OR IGNORE INTO veiculo_selos
           (id, veiculo_id, selo_id, campos_especificos)
           VALUES (?,?,?,?)""",
        [
            (1,  1,  1, json.dumps({'numero_laudo': 'LAU-2024-0391', 'orgao_leilao': 'Biasi Leilões', 'percentual_perda': 42})),
            (2,  2,  2, json.dumps({'numero_laudo': 'BO-2024-12345', 'orgao_leilao': 'Sodré Santoro'})),
            (3,  2,  9, json.dumps({'localizacao_avaria': 'Lateral esquerda — porta dianteira e traseira amassadas'})),
            (4,  3,  5, json.dumps({'diagnostico': 'Junta de cabeçote comprometida, consumo 1L/300km', 'orcamento_reparo': 420000})),
            (5,  4,  9, json.dumps({'localizacao_avaria': 'Porta traseira direita + lateral traseira direita'})),
            (6,  5, 12, json.dumps({'situacao_resolver': 'Financiamento Santander ref. contrato #2019-447821', 'prazo_estimado': '30 dias após quitação'})),
            (7,  6,  6, json.dumps({'diagnostico': 'Solenóide do câmbio DSG com falha em marcha 3-4', 'orcamento_reparo': 380000})),
            (8,  7, 10, json.dumps({'localizacao_avaria': 'Bancos dianteiros queimados, painel com fuligem'})),
            (9,  8,  3, json.dumps({'orgao_leilao': 'Leilões Localiza — Lote MG-2024-07'})),
            (10, 9,  8, json.dumps({'diagnostico': 'Módulo ECU com falha P0606, entra em modo de emergência', 'orcamento_reparo': 290000})),
            (11, 9, 13, json.dumps({'situacao_resolver': 'IPVA 2022 e 2023 em aberto — total estimado R$ 1.800', 'prazo_estimado': '15 dias'})),
            (12, 10, 4, json.dumps({'numero_laudo': 'PROC-2023-44981-SP', 'orgao_leilao': 'TJ-SP — 3ª Vara Cível'})),
            (13, 10,11, json.dumps({'localizacao_avaria': 'Parabrisa — trinca diagonal no canto inferior direito, 22cm'})),
        ],
    )

    # ── Fotos dos Veículos ────────────────────────────────────────────────────
    # Selos de defeito_mecanico (ids 5-8) e defeito_estetico (ids 9-11)
    # exigem ao menos 1 foto vinculada — incluídas abaixo.
    conn.executemany(
        """INSERT OR IGNORE INTO fotos_veiculo
           (id, veiculo_id, veiculo_selo_id, tipo, caminho, descricao, ordem)
           VALUES (?,?,?,?,?,?,?)""",
        [
            (1,  1,  None, 'geral',  'uploads/v1/frente.jpg',          'Vista frontal', 1),
            (2,  2,  None, 'geral',  'uploads/v2/frente.jpg',          None, 1),
            (3,  2,  3,   'avaria', 'uploads/v2/lateral.jpg',          'Amassado lateral esquerdo', 2),
            (4,  3,  4,   'avaria', 'uploads/v3/motor.jpg',            'Motor aberto — junta comprometida', 1),
            (5,  3,  4,   'laudo',  'uploads/v3/laudo.jpg',            'Laudo da oficina', 2),
            (6,  4,  5,   'avaria', 'uploads/v4/porta.jpg',            'Porta traseira direita', 1),
            (7,  5,  None, 'geral', 'uploads/v5/frente.jpg',           None, 1),
            (8,  6,  7,   'avaria', 'uploads/v6/cambio.jpg',           'Câmbio DSG aberto', 1),
            (9,  7,  8,   'avaria', 'uploads/v7/bancos.jpg',           'Bancos dianteiros queimados', 1),
            (10, 7,  8,   'avaria', 'uploads/v7/painel.jpg',           'Fuligem no painel', 2),
            (11, 8,  None, 'geral', 'uploads/v8/frente.jpg',           None, 1),
            (12, 9,  10,  'avaria', 'uploads/v9/ecu.jpg',              'Módulo ECU removido', 1),
            (13, 10, 13,  'avaria', 'uploads/v10/parabrisa.jpg',       'Trinca diagonal no parabrisa', 1),
            (14, 10, 12,  'laudo',  'uploads/v10/laudo_judicial.jpg',  'Documento TJ-SP', 2),
        ],
    )

    # ── Propostas de exemplo ──────────────────────────────────────────────────
    conn.executemany(
        """INSERT OR IGNORE INTO propostas
           (id, veiculo_id, lojista_comprador_id, valor, mensagem, status)
           VALUES (?,?,?,?,?,?)""",
        [
            (1, 1, 2, 2600000, 'Tenho interesse, faço 26k à vista.',           'pendente'),
            (2, 3, 4, 8200000, 'Proposta: 82k. Posso buscar essa semana.',      'pendente'),
            (3, 4, 2, 4700000, 'Ofereço 47k com retirada imediata.',            'aceita'),
        ],
    )

    conn.commit()
    conn.close()
    print(f"Seed concluído — banco em: {DB_PATH}")


if __name__ == '__main__':
    main()
