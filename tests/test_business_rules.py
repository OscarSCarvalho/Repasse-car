import json
import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.business_rules import (
    validar_cnpj,
    validar_criacao_proposta,
    validar_publicacao_veiculo,
    validar_transicao_status,
)
from app.models import (
    adicionar_foto,
    adicionar_selo_veiculo,
    atualizar_status_veiculo,
    criar_lojista,
    criar_veiculo,
)

SCHEMA_PATH = Path(__file__).parent.parent / "database" / "schema.sql"

_TAXONOMY_SQL = """
INSERT INTO categorias_defeito (id, nome) VALUES
    (1, 'origem_leilao'),
    (2, 'defeito_mecanico'),
    (3, 'defeito_estetico'),
    (4, 'documentacao');

INSERT INTO selos_defeito (id, categoria_id, nome, campos_obrigatorios, exige_foto) VALUES
    (1, 1, 'Sinistro recuperável',   '["numero_laudo","orgao_leilao","percentual_perda"]', 0),
    (2, 2, 'Motor',                  '["diagnostico","orcamento_reparo"]', 1),
    (3, 3, 'Lataria/pintura',        '["localizacao_avaria"]', 1),
    (4, 4, 'Financiamento em aberto','["situacao_resolver","prazo_estimado"]', 0);
"""


def _criar_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text(encoding='utf-8'))
    conn.executescript(_TAXONOMY_SQL)
    conn.commit()
    return conn


def _lojista(conn, sufixo="1") -> int:
    return criar_lojista(conn, {
        'nome_fantasia': f'Loja {sufixo}',
        'razao_social':  f'Loja {sufixo} Ltda',
        'cnpj':          '11222333000181' if sufixo == "1" else '22333444000181',
        'email':         f'loja{sufixo}@teste.com',
        'senha_hash':    'hash',
        'cidade':        'São Paulo',
        'uf':            'SP',
    })


def _veiculo(conn, lojista_id: int) -> int:
    return criar_veiculo(conn, {
        'lojista_id':    lojista_id,
        'marca':         'Fiat',
        'modelo':        'Siena',
        'ano_fabricacao': 2018,
        'ano_modelo':    2019,
        'kilometragem':  80000,
        'cambio':        'manual',
        'combustivel':   'flex',
        'preco':         3500000,
    })


# ── Validação de CNPJ ──────────────────────────────────────────────────────────

class TestValidarCNPJ(unittest.TestCase):

    def test_cnpj_valido(self):
        self.assertTrue(validar_cnpj('11222333000181'))

    def test_cnpj_valido_com_mascara(self):
        self.assertTrue(validar_cnpj('11.222.333/0001-81'))

    def test_cnpj_digito_verificador_errado(self):
        self.assertFalse(validar_cnpj('11222333000199'))

    def test_cnpj_tamanho_insuficiente(self):
        self.assertFalse(validar_cnpj('1122233300018'))

    def test_cnpj_todos_digitos_iguais(self):
        self.assertFalse(validar_cnpj('11111111111111'))

    def test_cnpj_vazio(self):
        self.assertFalse(validar_cnpj(''))

    def test_cnpj_com_letras(self):
        self.assertFalse(validar_cnpj('ABCDEFGHIJKLMN'))

    def test_segundo_cnpj_valido(self):
        self.assertTrue(validar_cnpj('22333444000181'))


# ── Transição de Status ────────────────────────────────────────────────────────

class TestTransicaoStatus(unittest.TestCase):

    def test_rascunho_para_ativo(self):
        validar_transicao_status('rascunho', 'ativo')

    def test_rascunho_para_cancelado(self):
        validar_transicao_status('rascunho', 'cancelado')

    def test_ativo_para_em_negociacao(self):
        validar_transicao_status('ativo', 'em_negociacao')

    def test_ativo_para_cancelado(self):
        validar_transicao_status('ativo', 'cancelado')

    def test_em_negociacao_para_vendido(self):
        validar_transicao_status('em_negociacao', 'vendido')

    def test_em_negociacao_pode_voltar_para_ativo(self):
        validar_transicao_status('em_negociacao', 'ativo')

    def test_vendido_para_ativo_invalido(self):
        with self.assertRaises(ValueError) as ctx:
            validar_transicao_status('vendido', 'ativo')
        self.assertIn('vendido', str(ctx.exception))

    def test_vendido_para_rascunho_invalido(self):
        with self.assertRaises(ValueError):
            validar_transicao_status('vendido', 'rascunho')

    def test_cancelado_para_qualquer_status_invalido(self):
        for destino in ('ativo', 'rascunho', 'em_negociacao', 'vendido'):
            with self.subTest(destino=destino):
                with self.assertRaises(ValueError):
                    validar_transicao_status('cancelado', destino)

    def test_status_desconhecido_levanta_erro(self):
        with self.assertRaises(ValueError):
            validar_transicao_status('inexistente', 'ativo')


# ── Publicação de Veículo ──────────────────────────────────────────────────────

class TestPublicacaoVeiculo(unittest.TestCase):

    def setUp(self):
        self.conn = _criar_db()
        self.lojista_id = _lojista(self.conn)
        self.veiculo_id = _veiculo(self.conn, self.lojista_id)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_sem_selos_nao_pode_publicar(self):
        with self.assertRaises(ValueError) as ctx:
            validar_publicacao_veiculo(self.conn, self.veiculo_id)
        self.assertIn('nenhum selo', str(ctx.exception))

    def test_com_selo_leilao_pode_publicar(self):
        adicionar_selo_veiculo(self.conn, self.veiculo_id, 1, {
            'numero_laudo': 'L001', 'orgao_leilao': 'Biasi', 'percentual_perda': 30
        })
        self.conn.commit()
        validar_publicacao_veiculo(self.conn, self.veiculo_id)  # sem exceção

    def test_com_selo_documentacao_pode_publicar(self):
        adicionar_selo_veiculo(self.conn, self.veiculo_id, 4, {
            'situacao_resolver': 'Financiamento ativo', 'prazo_estimado': '30 dias'
        })
        self.conn.commit()
        validar_publicacao_veiculo(self.conn, self.veiculo_id)  # sem exceção

    def test_selo_mecanico_sem_foto_bloqueia_publicacao(self):
        adicionar_selo_veiculo(self.conn, self.veiculo_id, 2, {
            'diagnostico': 'Motor fundido', 'orcamento_reparo': 500000
        })
        self.conn.commit()
        with self.assertRaises(ValueError) as ctx:
            validar_publicacao_veiculo(self.conn, self.veiculo_id)
        self.assertIn('foto', str(ctx.exception).lower())

    def test_selo_mecanico_com_foto_permite_publicacao(self):
        vs_id = adicionar_selo_veiculo(self.conn, self.veiculo_id, 2, {
            'diagnostico': 'Motor fundido', 'orcamento_reparo': 500000
        })
        adicionar_foto(self.conn, {
            'veiculo_id': self.veiculo_id,
            'veiculo_selo_id': vs_id,
            'tipo': 'avaria',
            'caminho': '/fotos/motor.jpg',
        })
        self.conn.commit()
        validar_publicacao_veiculo(self.conn, self.veiculo_id)  # sem exceção

    def test_selo_estetico_sem_foto_bloqueia_publicacao(self):
        adicionar_selo_veiculo(self.conn, self.veiculo_id, 3, {
            'localizacao_avaria': 'Porta dianteira esquerda'
        })
        self.conn.commit()
        with self.assertRaises(ValueError) as ctx:
            validar_publicacao_veiculo(self.conn, self.veiculo_id)
        self.assertIn('foto', str(ctx.exception).lower())

    def test_misto_leilao_mecanico_exige_foto_apenas_no_mecanico(self):
        # Leilão não exige foto, mecânico sim — basta a foto do mecânico
        adicionar_selo_veiculo(self.conn, self.veiculo_id, 1, {
            'numero_laudo': 'L001', 'orgao_leilao': 'Biasi', 'percentual_perda': 40
        })
        vs_id = adicionar_selo_veiculo(self.conn, self.veiculo_id, 2, {
            'diagnostico': 'Câmbio com desgaste', 'orcamento_reparo': 200000
        })
        adicionar_foto(self.conn, {
            'veiculo_id': self.veiculo_id,
            'veiculo_selo_id': vs_id,
            'tipo': 'avaria',
            'caminho': '/fotos/cambio.jpg',
        })
        self.conn.commit()
        validar_publicacao_veiculo(self.conn, self.veiculo_id)  # sem exceção


# ── Criação de Proposta ────────────────────────────────────────────────────────

class TestCriacaoProposta(unittest.TestCase):

    def setUp(self):
        self.conn = _criar_db()
        self.dono_id     = _lojista(self.conn, '1')
        self.comprador_id = _lojista(self.conn, '2')
        self.veiculo_id  = _veiculo(self.conn, self.dono_id)
        atualizar_status_veiculo(self.conn, self.veiculo_id, 'ativo')
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_proposta_valida(self):
        validar_criacao_proposta(self.conn, self.veiculo_id, self.comprador_id)

    def test_proposta_no_proprio_anuncio_falha(self):
        with self.assertRaises(ValueError) as ctx:
            validar_criacao_proposta(self.conn, self.veiculo_id, self.dono_id)
        self.assertIn('próprio', str(ctx.exception))

    def test_proposta_em_veiculo_vendido_falha(self):
        atualizar_status_veiculo(self.conn, self.veiculo_id, 'em_negociacao')
        atualizar_status_veiculo(self.conn, self.veiculo_id, 'vendido')
        self.conn.commit()
        with self.assertRaises(ValueError) as ctx:
            validar_criacao_proposta(self.conn, self.veiculo_id, self.comprador_id)
        self.assertIn('vendido', str(ctx.exception))

    def test_proposta_em_veiculo_cancelado_falha(self):
        atualizar_status_veiculo(self.conn, self.veiculo_id, 'cancelado')
        self.conn.commit()
        with self.assertRaises(ValueError) as ctx:
            validar_criacao_proposta(self.conn, self.veiculo_id, self.comprador_id)
        self.assertIn('cancelado', str(ctx.exception))

    def test_proposta_em_veiculo_em_negociacao_permitida(self):
        atualizar_status_veiculo(self.conn, self.veiculo_id, 'em_negociacao')
        self.conn.commit()
        validar_criacao_proposta(self.conn, self.veiculo_id, self.comprador_id)

    def test_proposta_em_veiculo_inexistente_falha(self):
        with self.assertRaises(ValueError) as ctx:
            validar_criacao_proposta(self.conn, 9999, self.comprador_id)
        self.assertIn('não encontrado', str(ctx.exception))


if __name__ == '__main__':
    unittest.main(verbosity=2)
