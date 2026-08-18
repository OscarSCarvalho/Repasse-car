import sqlite3
import pytest
from app import create_app
from app.db import init_db

_TAXONOMY_SQL = """
INSERT INTO categorias_defeito (id, nome) VALUES
    (1,'origem_leilao'),(2,'defeito_mecanico'),
    (3,'defeito_estetico'),(4,'documentacao');
INSERT INTO selos_defeito (id, categoria_id, nome, campos_obrigatorios, exige_foto) VALUES
    (1,1,'Sinistro recuperável','["numero_laudo","orgao_leilao","percentual_perda"]',0),
    (2,2,'Motor','["diagnostico","orcamento_reparo"]',1),
    (3,3,'Lataria/pintura','["localizacao_avaria"]',1),
    (4,4,'Financiamento em aberto','["situacao_resolver","prazo_estimado"]',0);
"""

LOJISTA_1 = {
    'nome_fantasia': 'Loja Um',
    'razao_social':  'Loja Um Ltda',
    'cnpj':          '11222333000181',
    'email':         'um@teste.com',
    'senha':         'Senha@123',
    'cidade':        'São Paulo',
    'uf':            'SP',
}
LOJISTA_2 = {
    'nome_fantasia': 'Loja Dois',
    'razao_social':  'Loja Dois Ltda',
    'cnpj':          '22333444000181',
    'email':         'dois@teste.com',
    'senha':         'Senha@123',
    'cidade':        'Rio de Janeiro',
    'uf':            'RJ',
}
VEICULO_BASE = {
    'marca': 'Fiat', 'modelo': 'Siena',
    'ano_fabricacao': 2018, 'ano_modelo': 2019,
    'kilometragem': 80000, 'cambio': 'manual',
    'combustivel': 'flex', 'preco': 3500000,
}


@pytest.fixture(scope='function')
def app(tmp_path):
    db_file = str(tmp_path / 'test.db')

    class _Cfg:
        TESTING = True
        DATABASE = db_file
        SECRET_KEY = 'test-secret'

    application = create_app(_Cfg)
    init_db(db_file)

    conn = sqlite3.connect(db_file)
    conn.executescript(_TAXONOMY_SQL)
    conn.commit()
    conn.close()

    yield application


@pytest.fixture
def client(app):
    return app.test_client()


# ── helpers ────────────────────────────────────────────────────────────────────

def registrar(client, dados):
    return client.post('/api/auth/registro', json=dados)


def fazer_login(client, email, senha):
    return client.post('/api/auth/login', json={'email': email, 'senha': senha})


def registrar_e_logar(client, dados):
    registrar(client, dados)
    return fazer_login(client, dados['email'], dados['senha'])


def criar_veiculo_pub(client, dados=None):
    return client.post('/api/veiculos', json=dados or VEICULO_BASE)


def publicar_veiculo(client, veiculo_id: int):
    """Adiciona um selo sem exigência de foto e publica."""
    client.post(f'/api/veiculos/{veiculo_id}/selos', json={
        'selo_id': 1,
        'campos_especificos': {
            'numero_laudo': 'L001', 'orgao_leilao': 'Biasi', 'percentual_perda': 30,
        },
    })
    return client.post(f'/api/veiculos/{veiculo_id}/publicar')
