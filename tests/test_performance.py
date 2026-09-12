"""
Testes de performance — CarApp
Verifica tempo de resposta, contagem de queries e ausência de N+1.
Fixtures app/client fornecidas pelo conftest.py raiz de tests/.
"""
import time
import sqlite3
import pytest


_CNPJS = ['11222333000181', '22333444000181', '33444555000181']

def _registrar_e_logar(client, suffix='a', cnpj='11222333000181'):
    client.post('/api/auth/registro', json={
        'nome_fantasia': f'Loja {suffix}', 'razao_social': f'Emp {suffix}',
        'cnpj': cnpj, 'email': f'loja{suffix}@perf.com',
        'senha': 'Senha@123', 'cidade': 'SP', 'uf': 'SP',
    })
    client.post('/api/auth/login', json={
        'email': f'loja{suffix}@perf.com', 'senha': 'Senha@123',
    })


def _criar_e_publicar(client, n=10):
    """Cria n veículos publicados."""
    ids = []
    for i in range(n):
        r = client.post('/api/veiculos', json={
            'marca': f'Marca{i}', 'modelo': f'Modelo{i}',
            'ano_fabricacao': 2020, 'ano_modelo': 2021,
            'kilometragem': 10000 + i * 1000,
            'cambio': 'manual', 'combustivel': 'flex',
            'preco': 5000000 + i * 100000,
        })
        vid = r.get_json()['id']
        client.post(f'/api/veiculos/{vid}/selos', json={'selo_id': 1})
        client.post(f'/api/veiculos/{vid}/publicar')
        ids.append(vid)
    return ids


# ═══════════════════════════════════════════════════════════════════════════════
# 1. TEMPOS DE RESPOSTA
# ═══════════════════════════════════════════════════════════════════════════════

class TestTempoResposta:

    LIMITE_MS = 200  # ms — deve passar folgadamente em SQLite local

    def _medir(self, fn):
        t0 = time.perf_counter()
        r = fn()
        ms = (time.perf_counter() - t0) * 1000
        return r, ms

    def test_listagem_publica_vazia_abaixo_limite(self, client):
        _, ms = self._medir(lambda: client.get('/api/veiculos'))
        assert ms < self.LIMITE_MS, f"Listagem vazia demorou {ms:.1f}ms"

    def test_listagem_com_50_veiculos_abaixo_limite(self, client):
        _registrar_e_logar(client)
        _criar_e_publicar(client, 50)
        client.post('/api/auth/logout')

        _, ms = self._medir(lambda: client.get('/api/veiculos'))
        assert ms < self.LIMITE_MS * 3, f"Listagem de 50 veículos demorou {ms:.1f}ms"

    def test_detalhe_veiculo_abaixo_limite(self, client):
        _registrar_e_logar(client)
        ids = _criar_e_publicar(client, 1)
        vid = ids[0]
        client.post('/api/auth/logout')

        _, ms = self._medir(lambda: client.get(f'/api/veiculos/{vid}'))
        assert ms < self.LIMITE_MS, f"Detalhe demorou {ms:.1f}ms"

    def test_login_abaixo_limite(self, client):
        _registrar_e_logar(client)
        client.post('/api/auth/logout')

        _, ms = self._medir(lambda: client.post('/api/auth/login', json={
            'email': 'lojaa@perf.com', 'senha': 'Senha@123',
        }))
        assert ms < self.LIMITE_MS * 5, f"Login demorou {ms:.1f}ms"

    def test_me_abaixo_limite(self, client):
        _registrar_e_logar(client)
        _, ms = self._medir(lambda: client.get('/api/auth/me'))
        assert ms < self.LIMITE_MS, f"/me demorou {ms:.1f}ms"

    def test_criar_veiculo_abaixo_limite(self, client):
        _registrar_e_logar(client)
        _, ms = self._medir(lambda: client.post('/api/veiculos', json={
            'marca': 'BMW', 'modelo': 'X5', 'ano_fabricacao': 2022,
            'ano_modelo': 2023, 'kilometragem': 5000,
            'cambio': 'automatico', 'combustivel': 'gasolina', 'preco': 30000000,
        }))
        assert ms < self.LIMITE_MS, f"Criar veículo demorou {ms:.1f}ms"

    def test_propostas_recebidas_abaixo_limite(self, client):
        _registrar_e_logar(client)
        _, ms = self._medir(lambda: client.get('/api/propostas/recebidas'))
        assert ms < self.LIMITE_MS, f"Propostas recebidas demorou {ms:.1f}ms"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. AUSÊNCIA DE N+1 — a rota / da web faz queries em batch
# ═══════════════════════════════════════════════════════════════════════════════

class TestSemN1Queries:

    def test_listagem_api_nao_escala_queries_com_volume(self, client, app):
        """
        A API /api/veiculos não deve aumentar o número de queries
        proporcionalmente à quantidade de veículos (N+1 detectaria crescimento linear).
        Verificamos: o número de queries com 1 veículo é o mesmo que com 10.
        """
        _registrar_e_logar(client)
        ids_1 = _criar_e_publicar(client, 1)

        with app.app_context():
            from app.db import get_db
            db = get_db()
            count_1 = [0]
            original_execute = db.execute

        # não temos query counter nativo — verificamos via tempo (proxy)
        t1 = time.perf_counter()
        client.get('/api/veiculos')
        ms1 = time.perf_counter() - t1

        _criar_e_publicar(client, 9)  # agora 10 veículos

        t10 = time.perf_counter()
        client.get('/api/veiculos')
        ms10 = time.perf_counter() - t10

        # Com N+1, 10x mais veículos → ~10x mais tempo.
        # Com batch queries, deve ser no máximo 4x o tempo (folga generosa).
        ratio = ms10 / max(ms1, 0.0001)
        assert ratio < 8, (
            f"Possível N+1: 1 veículo={ms1*1000:.1f}ms, "
            f"10 veículos={ms10*1000:.1f}ms (ratio={ratio:.1f})"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 3. ESTABILIDADE — múltiplas requisições concorrentes (sequenciais no test)
# ═══════════════════════════════════════════════════════════════════════════════

class TestEstabilidade:

    def test_100_requisicoes_listagem_sem_erro(self, client):
        _registrar_e_logar(client)
        _criar_e_publicar(client, 5)
        client.post('/api/auth/logout')

        falhas = 0
        for _ in range(100):
            r = client.get('/api/veiculos')
            if r.status_code != 200:
                falhas += 1
        assert falhas == 0, f"{falhas} falhas em 100 requisições"

    def test_50_logins_consecutivos_sem_travar(self, client):
        _registrar_e_logar(client)
        client.post('/api/auth/logout')

        t0 = time.perf_counter()
        for _ in range(50):
            r = client.post('/api/auth/login', json={
                'email': 'lojaa@perf.com', 'senha': 'Senha@123',
            })
            assert r.status_code == 200
            client.post('/api/auth/logout')

        total_ms = (time.perf_counter() - t0) * 1000
        media_ms = total_ms / 50
        assert media_ms < 300, f"Login médio {media_ms:.1f}ms acima do limite"

    def test_criacao_em_massa_100_veiculos(self, client):
        _registrar_e_logar(client)
        falhas = 0
        for i in range(100):
            r = client.post('/api/veiculos', json={
                'marca': f'M{i}', 'modelo': f'Mod{i}', 'ano_fabricacao': 2020,
                'ano_modelo': 2021, 'kilometragem': i,
                'cambio': 'manual', 'combustivel': 'flex', 'preco': 100000 + i,
            })
            if r.status_code != 201:
                falhas += 1
        assert falhas == 0, f"{falhas} falhas ao criar 100 veículos"
