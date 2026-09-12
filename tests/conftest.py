"""
Conftest raiz de tests/ — compartilha fixtures com test_security, test_performance e test_web_routes.
"""
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


@pytest.fixture(scope='function')
def app(tmp_path):
    db_file = str(tmp_path / 'test.db')

    class _Cfg:
        TESTING = True
        DATABASE = db_file
        SECRET_KEY = 'test-secret'
        UPLOAD_FOLDER = str(tmp_path / 'uploads')

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
