from tests.test_routes.conftest import (
    LOJISTA_1, LOJISTA_2, registrar_e_logar,
    criar_veiculo_pub, publicar_veiculo,
)


def _setup_proposta(client) -> tuple[int, int]:
    """Cria veículo (L1), publica, cria proposta (L2). Retorna (veiculo_id, proposta_id)."""
    registrar_e_logar(client, LOJISTA_1)
    vid = criar_veiculo_pub(client).json['id']
    publicar_veiculo(client, vid)
    client.post('/api/auth/logout')

    registrar_e_logar(client, LOJISTA_2)
    pid = client.post(f'/api/veiculos/{vid}/propostas', json={
        'valor': 3200000, 'mensagem': 'Oferta firme.',
    }).json['id']
    client.post('/api/auth/logout')

    return vid, pid


class TestCriarProposta:

    def test_proposta_valida(self, client):
        registrar_e_logar(client, LOJISTA_1)
        vid = criar_veiculo_pub(client).json['id']
        publicar_veiculo(client, vid)
        client.post('/api/auth/logout')
        registrar_e_logar(client, LOJISTA_2)
        r = client.post(f'/api/veiculos/{vid}/propostas', json={'valor': 3200000})
        assert r.status_code == 201
        assert r.json['id']

    def test_proposta_no_proprio_anuncio_falha_409(self, client):
        registrar_e_logar(client, LOJISTA_1)
        vid = criar_veiculo_pub(client).json['id']
        publicar_veiculo(client, vid)
        r = client.post(f'/api/veiculos/{vid}/propostas', json={'valor': 3200000})
        assert r.status_code == 409
        assert 'próprio' in r.json['erro']

    def test_proposta_sem_valor_422(self, client):
        registrar_e_logar(client, LOJISTA_1)
        vid = criar_veiculo_pub(client).json['id']
        publicar_veiculo(client, vid)
        client.post('/api/auth/logout')
        registrar_e_logar(client, LOJISTA_2)
        r = client.post(f'/api/veiculos/{vid}/propostas', json={'mensagem': 'só texto'})
        assert r.status_code == 422

    def test_proposta_sem_autenticacao_401(self, client):
        registrar_e_logar(client, LOJISTA_1)
        vid = criar_veiculo_pub(client).json['id']
        publicar_veiculo(client, vid)
        client.post('/api/auth/logout')
        r = client.post(f'/api/veiculos/{vid}/propostas', json={'valor': 3200000})
        assert r.status_code == 401


class TestAtualizarStatusProposta:

    def test_dono_aceita_proposta_e_veiculo_vai_para_em_negociacao(self, client):
        vid, pid = _setup_proposta(client)
        registrar_e_logar(client, LOJISTA_1)
        r = client.patch(f'/api/propostas/{pid}/status', json={'status': 'aceita'})
        assert r.status_code == 200
        assert client.get(f'/api/veiculos/{vid}').json['status'] == 'em_negociacao'

    def test_dono_recusa_proposta(self, client):
        _, pid = _setup_proposta(client)
        registrar_e_logar(client, LOJISTA_1)
        r = client.patch(f'/api/propostas/{pid}/status', json={'status': 'recusada'})
        assert r.status_code == 200
        assert r.json['status'] == 'recusada'

    def test_comprador_cancela_proposta(self, client):
        _, pid = _setup_proposta(client)
        registrar_e_logar(client, LOJISTA_2)
        r = client.patch(f'/api/propostas/{pid}/status', json={'status': 'cancelada'})
        assert r.status_code == 200

    def test_comprador_nao_pode_aceitar_proposta_403(self, client):
        _, pid = _setup_proposta(client)
        registrar_e_logar(client, LOJISTA_2)
        r = client.patch(f'/api/propostas/{pid}/status', json={'status': 'aceita'})
        assert r.status_code == 403

    def test_dono_nao_pode_cancelar_proposta_de_outro_403(self, client):
        _, pid = _setup_proposta(client)
        registrar_e_logar(client, LOJISTA_1)
        r = client.patch(f'/api/propostas/{pid}/status', json={'status': 'cancelada'})
        assert r.status_code == 403

    def test_alterar_proposta_ja_aceita_falha_409(self, client):
        _, pid = _setup_proposta(client)
        registrar_e_logar(client, LOJISTA_1)
        client.patch(f'/api/propostas/{pid}/status', json={'status': 'aceita'})
        r = client.patch(f'/api/propostas/{pid}/status', json={'status': 'aceita'})
        assert r.status_code == 409

    def test_status_invalido_422(self, client):
        _, pid = _setup_proposta(client)
        registrar_e_logar(client, LOJISTA_1)
        r = client.patch(f'/api/propostas/{pid}/status', json={'status': 'aprovada'})
        assert r.status_code == 422


class TestListagemPropostas:

    def test_recebidas_retorna_propostas_dos_meus_anuncios(self, client):
        _setup_proposta(client)
        registrar_e_logar(client, LOJISTA_1)
        r = client.get('/api/propostas/recebidas')
        assert r.status_code == 200
        assert len(r.json['propostas']) == 1

    def test_recebidas_nao_mostra_propostas_de_outros(self, client):
        _setup_proposta(client)
        registrar_e_logar(client, LOJISTA_2)
        r = client.get('/api/propostas/recebidas')
        assert len(r.json['propostas']) == 0

    def test_enviadas_retorna_minhas_propostas(self, client):
        _setup_proposta(client)
        registrar_e_logar(client, LOJISTA_2)
        r = client.get('/api/propostas/enviadas')
        assert r.status_code == 200
        assert len(r.json['propostas']) == 1

    def test_enviadas_sem_autenticacao_401(self, client):
        assert client.get('/api/propostas/enviadas').status_code == 401
