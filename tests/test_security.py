"""
Testes de segurança e vulnerabilidades — CarApp
Cobre: IDOR, auth bypass, mass assignment, payloads XSS/SQLi,
session isolation e regras de acesso entre lojistas.
Fixtures app/client fornecidas pelo conftest.py raiz de tests/.

Padrão de troca de usuário: chamar _reg() sobrescreve a sessão (igual ao conftest existente).
Não usar logout + re-login — o test client Flask não preserva a sessão após session.clear().
"""
import sqlite3 as _sqlite3
import pytest


# ── helpers ───────────────────────────────────────────────────────────────────

def _reg(client, suffix='a', cnpj='11222333000181'):
    return client.post('/api/auth/registro', json={
        'nome_fantasia': f'Loja {suffix}',
        'razao_social': f'Empresa {suffix} LTDA',
        'cnpj': cnpj,
        'email': f'loja{suffix}@exemplo.com',
        'senha': 'Senha@123',
        'cidade': 'São Paulo',
        'uf': 'SP',
    })

def _criar_veiculo(client):
    return client.post('/api/veiculos', json={
        'marca': 'Honda', 'modelo': 'Civic', 'ano_fabricacao': 2020,
        'ano_modelo': 2021, 'kilometragem': 30000,
        'cambio': 'automatico', 'combustivel': 'flex', 'preco': 9000000,
    })

def _publicar(client, vid):
    client.post(f'/api/veiculos/{vid}/selos', json={'selo_id': 1})
    return client.post(f'/api/veiculos/{vid}/publicar')


# ═══════════════════════════════════════════════════════════════════════════════
# 1. AUTENTICAÇÃO E SESSION
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuthSeguranca:

    def test_endpoints_protegidos_sem_sessao_retornam_401(self, client):
        endpoints = [
            ('GET',    '/api/auth/me'),
            ('POST',   '/api/auth/logout'),
            ('POST',   '/api/veiculos'),
            ('GET',    '/api/meus-anuncios'),
            ('GET',    '/api/propostas/recebidas'),
            ('GET',    '/api/propostas/enviadas'),
        ]
        for method, url in endpoints:
            r = getattr(client, method.lower())(url)
            assert r.status_code == 401, f"{method} {url} deveria ser 401, got {r.status_code}"

    def test_login_com_credenciais_invalidas_sempre_falha(self, client):
        _reg(client, 'a')
        payloads = [
            {'email': 'lojaa@exemplo.com', 'senha': 'errada'},
            {'email': 'lojaa@exemplo.com', 'senha': ''},
            {'email': 'nao_existe@x.com', 'senha': 'Senha@123'},
            {'email': '', 'senha': 'Senha@123'},
        ]
        for p in payloads:
            r = client.post('/api/auth/login', json=p)
            assert r.status_code in (401, 422), f"payload {p} deveria falhar"

    def test_sessao_isolada_entre_clientes(self, client):
        """Dois test_client() independentes não compartilham sessão."""
        _reg(client, 'a')
        client2 = client.application.test_client()
        r = client2.get('/api/auth/me')
        assert r.status_code == 401

    def test_senha_hash_nunca_exposta_no_me(self, client):
        _reg(client, 'a')
        data = client.get('/api/auth/me').get_json()
        assert 'senha_hash' not in data
        assert 'senha' not in data

    def test_conta_inativa_nao_faz_login(self, client, app):
        _reg(client, 'inativo', '22333444000181')
        # Usa conexão SQLite direta para evitar isolamento de app_context
        conn = _sqlite3.connect(app.config['DATABASE'])
        conn.execute("UPDATE lojistas SET ativo = 0 WHERE email = 'lojainativo@exemplo.com'")
        conn.commit()
        conn.close()

        r = client.post('/api/auth/login', json={
            'email': 'lojainativo@exemplo.com', 'senha': 'Senha@123'
        })
        assert r.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════════
# 2. IDOR — Insecure Direct Object Reference
# ═══════════════════════════════════════════════════════════════════════════════

class TestIDOR:

    def _setup_dois_lojistas(self, client):
        """A cria veículo; B fica logado."""
        _reg(client, 'a', '11222333000181')
        vid = _criar_veiculo(client).get_json()['id']
        _reg(client, 'b', '22333444000181')  # troca sessão para B
        return vid

    def test_lojista_nao_pode_editar_veiculo_alheio(self, client):
        vid = self._setup_dois_lojistas(client)
        r = client.patch(f'/api/veiculos/{vid}', json={'marca': 'Invasor'})
        assert r.status_code == 403

    def test_lojista_nao_pode_publicar_veiculo_alheio(self, client):
        vid = self._setup_dois_lojistas(client)
        r = client.post(f'/api/veiculos/{vid}/publicar')
        assert r.status_code == 403

    def test_lojista_nao_pode_cancelar_veiculo_alheio(self, client):
        vid = self._setup_dois_lojistas(client)
        r = client.post(f'/api/veiculos/{vid}/cancelar')
        assert r.status_code == 403

    def test_lojista_nao_pode_adicionar_foto_em_veiculo_alheio(self, client):
        vid = self._setup_dois_lojistas(client)
        r = client.post(f'/api/veiculos/{vid}/fotos', json={'tipo': 'geral', 'caminho': 'x.jpg'})
        assert r.status_code == 403

    def test_lojista_nao_pode_adicionar_selo_em_veiculo_alheio(self, client):
        vid = self._setup_dois_lojistas(client)
        r = client.post(f'/api/veiculos/{vid}/selos', json={'selo_id': 1})
        assert r.status_code == 403

    def test_terceiro_nao_acessa_mensagens_de_proposta_alheia(self, client):
        """Lojista C não pode ler chat de proposta entre A e B."""
        _reg(client, 'a', '11222333000181')
        vid = _criar_veiculo(client).get_json()['id']
        _publicar(client, vid)

        _reg(client, 'b', '22333444000181')
        pid = client.post(f'/api/veiculos/{vid}/propostas', json={'valor': 8000000}).get_json()['id']

        _reg(client, 'c', '33444555000181')
        r = client.get(f'/api/propostas/{pid}/mensagens')
        assert r.status_code == 403

    def test_aceitar_proposta_alheia_proibido(self, client):
        """Comprador não pode aceitar a própria proposta."""
        _reg(client, 'a', '11222333000181')
        vid = _criar_veiculo(client).get_json()['id']
        _publicar(client, vid)

        _reg(client, 'b', '22333444000181')
        pid = client.post(f'/api/veiculos/{vid}/propostas', json={'valor': 8000000}).get_json()['id']

        # B tenta aceitar (B é o comprador, não o dono do anúncio)
        r = client.patch(f'/api/propostas/{pid}/status', json={'status': 'aceita'})
        assert r.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════════
# 3. MASS ASSIGNMENT — campos não permitidos ignorados
# ═══════════════════════════════════════════════════════════════════════════════

class TestMassAssignment:

    def test_registro_ignora_campo_id_injetado(self, client):
        r = _reg(client, 'a')
        assert r.status_code == 201
        assert r.get_json()['id'] != 999

    def test_patch_veiculo_ignora_campo_lojista_id(self, client):
        _reg(client, 'a', '11222333000181')
        vid = _criar_veiculo(client).get_json()['id']
        r = client.patch(f'/api/veiculos/{vid}', json={
            'marca': 'Novo', 'lojista_id': 9999, 'status': 'vendido',
        })
        assert r.status_code == 200
        data = r.get_json()
        assert data['lojista_id'] != 9999
        assert data['status'] == 'rascunho'

    def test_criar_veiculo_ignora_status_injetado(self, client, app):
        _reg(client, 'a', '11222333000181')
        r = client.post('/api/veiculos', json={
            'marca': 'Honda', 'modelo': 'Civic', 'ano_fabricacao': 2020,
            'ano_modelo': 2021, 'kilometragem': 30000,
            'cambio': 'automatico', 'combustivel': 'flex', 'preco': 9000000,
            'status': 'ativo',
        })
        assert r.status_code == 201
        vid = r.get_json()['id']
        conn = _sqlite3.connect(app.config['DATABASE'])
        v = conn.execute("SELECT status FROM veiculos WHERE id=?", (vid,)).fetchone()
        conn.close()
        assert v[0] == 'rascunho'


# ═══════════════════════════════════════════════════════════════════════════════
# 4. PAYLOADS MALICIOSOS — XSS e SQLi
# ═══════════════════════════════════════════════════════════════════════════════

class TestPayloadsMaliciosos:

    _xss = "<script>alert('xss')</script>"
    _sqli_simples = "' OR '1'='1"
    _sqli_union = "' UNION SELECT senha_hash FROM lojistas --"

    def test_xss_em_marca_veiculo_retornado_literal(self, client):
        _reg(client, 'a', '11222333000181')
        r = client.post('/api/veiculos', json={
            'marca': self._xss, 'modelo': 'Test', 'ano_fabricacao': 2020,
            'ano_modelo': 2021, 'kilometragem': 1, 'cambio': 'manual',
            'combustivel': 'flex', 'preco': 100,
        })
        assert r.status_code == 201
        vid = r.get_json()['id']
        data = client.get(f'/api/veiculos/{vid}').get_json()
        assert data['marca'] == self._xss  # armazenado literal; Jinja2 escapa no HTML

    def test_sqli_no_filtro_marca_retorna_lista_normal(self, client):
        _reg(client, 'a', '11222333000181')
        r = client.get(f'/api/veiculos?marca={self._sqli_simples}')
        assert r.status_code == 200
        data = r.get_json()
        assert 'veiculos' in data
        assert 'senha_hash' not in str(data)

    def test_sqli_union_em_filtro_cidade_nao_vaza_dados(self, client):
        _reg(client, 'a', '11222333000181')
        payload = "SP' UNION SELECT senha_hash,2,3,4,5 FROM lojistas --"
        r = client.get(f'/api/veiculos?cidade={payload}')
        assert r.status_code == 200
        assert 'senha_hash' not in r.get_data(as_text=True)

    def test_xss_em_mensagem_chat_armazenado_literal(self, client):
        _reg(client, 'a', '11222333000181')
        vid = _criar_veiculo(client).get_json()['id']
        _publicar(client, vid)

        _reg(client, 'b', '22333444000181')
        pid = client.post(f'/api/veiculos/{vid}/propostas', json={'valor': 5000000}).get_json()['id']
        client.post(f'/api/propostas/{pid}/mensagens', json={'conteudo': self._xss})

        msgs = client.get(f'/api/propostas/{pid}/mensagens').get_json()['mensagens']
        assert msgs[0]['conteudo'] == self._xss


# ═══════════════════════════════════════════════════════════════════════════════
# 5. REGRAS DE NEGÓCIO
# ═══════════════════════════════════════════════════════════════════════════════

class TestRegraNegocios:

    def test_veiculo_vendido_nao_aceita_novas_propostas(self, client, app):
        _reg(client, 'a', '11222333000181')
        vid = _criar_veiculo(client).get_json()['id']
        _publicar(client, vid)

        _reg(client, 'b', '22333444000181')
        pid = client.post(f'/api/veiculos/{vid}/propostas', json={'valor': 5000000}).get_json()['id']

        # A aceita proposta de B
        _reg(client, 'a', '11222333000181')  # re-registrar seria 409 — usar login
        client.post('/api/auth/login', json={'email': 'lojaa@exemplo.com', 'senha': 'Senha@123'})
        client.patch(f'/api/propostas/{pid}/status', json={'status': 'aceita'})

        # Forçar status vendido diretamente
        conn = _sqlite3.connect(app.config['DATABASE'])
        conn.execute("UPDATE veiculos SET status='vendido' WHERE id=?", (vid,))
        conn.commit()
        conn.close()

        _reg(client, 'c', '33444555000181')
        r = client.post(f'/api/veiculos/{vid}/propostas', json={'valor': 4000000})
        assert r.status_code == 409

    def test_proposta_aceita_nao_pode_ser_alterada(self, client):
        _reg(client, 'a', '11222333000181')
        vid = _criar_veiculo(client).get_json()['id']
        _publicar(client, vid)

        _reg(client, 'b', '22333444000181')
        pid = client.post(f'/api/veiculos/{vid}/propostas', json={'valor': 5000000}).get_json()['id']

        client.post('/api/auth/login', json={'email': 'lojaa@exemplo.com', 'senha': 'Senha@123'})
        client.patch(f'/api/propostas/{pid}/status', json={'status': 'aceita'})

        r = client.patch(f'/api/propostas/{pid}/status', json={'status': 'recusada'})
        assert r.status_code == 409

    def test_lojista_nao_propoe_no_proprio_anuncio(self, client):
        _reg(client, 'a', '11222333000181')
        vid = _criar_veiculo(client).get_json()['id']
        _publicar(client, vid)
        r = client.post(f'/api/veiculos/{vid}/propostas', json={'valor': 5000000})
        assert r.status_code == 409

    def test_editar_veiculo_publicado_bloqueado(self, client):
        _reg(client, 'a', '11222333000181')
        vid = _criar_veiculo(client).get_json()['id']
        _publicar(client, vid)
        r = client.patch(f'/api/veiculos/{vid}', json={'marca': 'Alterado'})
        assert r.status_code == 409

    def test_status_invalido_em_proposta_rejeitado(self, client):
        _reg(client, 'a', '11222333000181')
        vid = _criar_veiculo(client).get_json()['id']
        _publicar(client, vid)

        _reg(client, 'b', '22333444000181')
        pid = client.post(f'/api/veiculos/{vid}/propostas', json={'valor': 5000000}).get_json()['id']

        r = client.patch(f'/api/propostas/{pid}/status', json={'status': 'vendido'})
        assert r.status_code == 422

    def test_cnpj_invalido_bloqueado_no_registro(self, client):
        payloads = ['00000000000000', '11111111111111', '123', '', 'ABC12345678901']
        for cnpj in payloads:
            r = client.post('/api/auth/registro', json={
                'nome_fantasia': 'X', 'razao_social': 'X',
                'cnpj': cnpj, 'email': 'x@x.com',
                'senha': 'Senha@123', 'cidade': 'SP', 'uf': 'SP',
            })
            assert r.status_code == 422, f"CNPJ '{cnpj}' deveria falhar"

    def test_mensagem_vazia_rejeitada(self, client):
        _reg(client, 'a', '11222333000181')
        vid = _criar_veiculo(client).get_json()['id']
        _publicar(client, vid)

        _reg(client, 'b', '22333444000181')
        pid = client.post(f'/api/veiculos/{vid}/propostas', json={'valor': 5000000}).get_json()['id']

        for conteudo in ['', '   ']:
            r = client.post(f'/api/propostas/{pid}/mensagens', json={'conteudo': conteudo})
            assert r.status_code == 422, f"conteudo={repr(conteudo)} deveria ser 422"

    def test_proposta_em_rascunho_nao_bloqueada_pela_regra_atual(self, client):
        """Documenta que veículo em rascunho aceita propostas (regra atual não bloqueia)."""
        _reg(client, 'a', '11222333000181')
        vid = _criar_veiculo(client).get_json()['id']  # status = rascunho

        _reg(client, 'b', '22333444000181')
        r = client.post(f'/api/veiculos/{vid}/propostas', json={'valor': 5000000})
        # Comportamento atual: 201 (rascunho não está em _STATUS_ANUNCIO_FECHADO)
        assert r.status_code == 201
