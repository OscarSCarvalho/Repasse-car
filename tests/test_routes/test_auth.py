from tests.test_routes.conftest import LOJISTA_1, LOJISTA_2, registrar, fazer_login, registrar_e_logar


class TestRegistro:

    def test_registro_valido(self, client):
        r = registrar(client, LOJISTA_1)
        assert r.status_code == 201
        assert 'id' in r.json

    def test_registro_cnpj_invalido(self, client):
        r = registrar(client, {**LOJISTA_1, 'cnpj': '12345678901234'})
        assert r.status_code == 422
        assert 'CNPJ' in r.json['erro']

    def test_registro_cnpj_duplicado(self, client):
        registrar(client, LOJISTA_1)
        r = registrar(client, {**LOJISTA_1, 'email': 'outro@teste.com'})
        assert r.status_code == 409
        assert 'CNPJ' in r.json['erro']

    def test_registro_email_duplicado(self, client):
        registrar(client, LOJISTA_1)
        r = registrar(client, {**LOJISTA_1, 'cnpj': '22333444000181'})
        assert r.status_code == 409
        assert 'E-mail' in r.json['erro']

    def test_registro_campos_faltando(self, client):
        r = client.post('/api/auth/registro', json={'email': 'x@x.com'})
        assert r.status_code == 422
        assert 'obrigatórios' in r.json['erro']


class TestLogin:

    def test_login_valido(self, client):
        registrar(client, LOJISTA_1)
        client.post('/api/auth/logout')
        r = fazer_login(client, LOJISTA_1['email'], LOJISTA_1['senha'])
        assert r.status_code == 200
        assert r.json['id']

    def test_login_senha_errada(self, client):
        registrar(client, LOJISTA_1)
        r = fazer_login(client, LOJISTA_1['email'], 'senha_errada')
        assert r.status_code == 401

    def test_login_email_inexistente(self, client):
        r = fazer_login(client, 'nao@existe.com', '123')
        assert r.status_code == 401

    def test_login_campos_faltando(self, client):
        r = client.post('/api/auth/login', json={'email': 'x@x.com'})
        assert r.status_code == 422


class TestLogoutEMe:

    def test_logout_encerra_sessao(self, client):
        registrar_e_logar(client, LOJISTA_1)
        assert client.post('/api/auth/logout').status_code == 200
        assert client.get('/api/auth/me').status_code == 401

    def test_logout_sem_sessao_retorna_401(self, client):
        assert client.post('/api/auth/logout').status_code == 401

    def test_me_retorna_dados_sem_senha_hash(self, client):
        registrar_e_logar(client, LOJISTA_1)
        r = client.get('/api/auth/me')
        assert r.status_code == 200
        assert r.json['email'] == LOJISTA_1['email'].lower()
        assert 'senha_hash' not in r.json

    def test_me_sem_sessao_retorna_401(self, client):
        assert client.get('/api/auth/me').status_code == 401
