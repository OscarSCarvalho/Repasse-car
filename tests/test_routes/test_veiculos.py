from tests.test_routes.conftest import (
    LOJISTA_1, LOJISTA_2, VEICULO_BASE,
    registrar_e_logar, criar_veiculo_pub, publicar_veiculo,
)


def _criar_e_publicar(client) -> int:
    vid = criar_veiculo_pub(client).json['id']
    publicar_veiculo(client, vid)
    return vid


class TestCriarVeiculo:

    def test_criar_valido(self, client):
        registrar_e_logar(client, LOJISTA_1)
        r = criar_veiculo_pub(client)
        assert r.status_code == 201
        assert r.json['id']

    def test_criar_sem_autenticacao_401(self, client):
        assert criar_veiculo_pub(client).status_code == 401

    def test_criar_campos_faltando_422(self, client):
        registrar_e_logar(client, LOJISTA_1)
        r = client.post('/api/veiculos', json={'marca': 'Fiat'})
        assert r.status_code == 422


class TestListagem:

    def test_listagem_publica_retorna_apenas_ativos(self, client):
        registrar_e_logar(client, LOJISTA_1)
        criar_veiculo_pub(client)          # fica em rascunho
        _criar_e_publicar(client)          # fica ativo
        r = client.get('/api/veiculos')
        assert r.status_code == 200
        assert r.json['total'] == 1
        assert r.json['veiculos'][0]['status'] == 'ativo'

    def test_filtro_por_marca(self, client):
        registrar_e_logar(client, LOJISTA_1)
        _criar_e_publicar(client)
        r = client.get('/api/veiculos?marca=fiat')
        assert r.json['total'] == 1
        r2 = client.get('/api/veiculos?marca=honda')
        assert r2.json['total'] == 0

    def test_filtro_por_preco_min(self, client):
        registrar_e_logar(client, LOJISTA_1)
        _criar_e_publicar(client)
        r = client.get('/api/veiculos?preco_min=5000000')
        assert r.json['total'] == 0
        r2 = client.get('/api/veiculos?preco_min=1000000')
        assert r2.json['total'] == 1

    def test_detalhe_inclui_selos_e_fotos(self, client):
        registrar_e_logar(client, LOJISTA_1)
        vid = _criar_e_publicar(client)
        r = client.get(f'/api/veiculos/{vid}')
        assert r.status_code == 200
        assert 'selos' in r.json
        assert 'fotos' in r.json
        assert len(r.json['selos']) == 1

    def test_detalhe_nao_encontrado_404(self, client):
        assert client.get('/api/veiculos/9999').status_code == 404


class TestPublicarCancelar:

    def test_publicar_sem_selos_falha_409(self, client):
        registrar_e_logar(client, LOJISTA_1)
        vid = criar_veiculo_pub(client).json['id']
        r = client.post(f'/api/veiculos/{vid}/publicar')
        assert r.status_code == 409
        assert 'nenhum selo' in r.json['erro']

    def test_publicar_com_selo_mecanico_sem_foto_falha_409(self, client):
        registrar_e_logar(client, LOJISTA_1)
        vid = criar_veiculo_pub(client).json['id']
        client.post(f'/api/veiculos/{vid}/selos', json={
            'selo_id': 2,
            'campos_especificos': {'diagnostico': 'Motor ruim', 'orcamento_reparo': 500000},
        })
        r = client.post(f'/api/veiculos/{vid}/publicar')
        assert r.status_code == 409
        assert 'foto' in r.json['erro'].lower()

    def test_publicar_com_selo_leilao_ok(self, client):
        registrar_e_logar(client, LOJISTA_1)
        vid = criar_veiculo_pub(client).json['id']
        r = publicar_veiculo(client, vid)
        assert r.status_code == 200
        assert r.json['status'] == 'ativo'

    def test_publicar_veiculo_de_outro_lojista_403(self, client):
        registrar_e_logar(client, LOJISTA_1)
        vid = criar_veiculo_pub(client).json['id']
        client.post('/api/auth/logout')
        registrar_e_logar(client, LOJISTA_2)
        assert client.post(f'/api/veiculos/{vid}/publicar').status_code == 403

    def test_cancelar_proprio_anuncio(self, client):
        registrar_e_logar(client, LOJISTA_1)
        vid = _criar_e_publicar(client)
        r = client.post(f'/api/veiculos/{vid}/cancelar')
        assert r.status_code == 200
        assert r.json['status'] == 'cancelado'

    def test_cancelar_anuncio_vendido_falha_409(self, client):
        registrar_e_logar(client, LOJISTA_1)
        vid = _criar_e_publicar(client)
        client.post('/api/auth/logout')
        registrar_e_logar(client, LOJISTA_2)
        client.post(f'/api/veiculos/{vid}/propostas', json={'valor': 3000000})
        pid = client.get('/api/propostas/enviadas').json['propostas'][0]['id']
        client.post('/api/auth/logout')
        registrar_e_logar(client, LOJISTA_1)
        client.patch(f'/api/propostas/{pid}/status', json={'status': 'aceita'})
        # status agora é em_negociacao; cancelar de em_negociacao deve funcionar
        r = client.post(f'/api/veiculos/{vid}/cancelar')
        assert r.status_code == 200


class TestSelos:

    def test_adicionar_selo_valido(self, client):
        registrar_e_logar(client, LOJISTA_1)
        vid = criar_veiculo_pub(client).json['id']
        r = client.post(f'/api/veiculos/{vid}/selos', json={'selo_id': 4, 'campos_especificos': {}})
        assert r.status_code == 201

    def test_adicionar_selo_duplicado_409(self, client):
        registrar_e_logar(client, LOJISTA_1)
        vid = criar_veiculo_pub(client).json['id']
        client.post(f'/api/veiculos/{vid}/selos', json={'selo_id': 4, 'campos_especificos': {}})
        r = client.post(f'/api/veiculos/{vid}/selos', json={'selo_id': 4, 'campos_especificos': {}})
        assert r.status_code == 409

    def test_adicionar_selo_inexistente_404(self, client):
        registrar_e_logar(client, LOJISTA_1)
        vid = criar_veiculo_pub(client).json['id']
        r = client.post(f'/api/veiculos/{vid}/selos', json={'selo_id': 999})
        assert r.status_code == 404

    def test_remover_selo(self, client):
        registrar_e_logar(client, LOJISTA_1)
        vid = criar_veiculo_pub(client).json['id']
        client.post(f'/api/veiculos/{vid}/selos', json={'selo_id': 4, 'campos_especificos': {}})
        r = client.delete(f'/api/veiculos/{vid}/selos/4')
        assert r.status_code == 200


class TestFotos:

    def test_adicionar_foto_geral(self, client):
        registrar_e_logar(client, LOJISTA_1)
        vid = criar_veiculo_pub(client).json['id']
        r = client.post(f'/api/veiculos/{vid}/fotos', json={'tipo': 'geral', 'caminho': 'uploads/f.jpg'})
        assert r.status_code == 201

    def test_tipo_invalido_422(self, client):
        registrar_e_logar(client, LOJISTA_1)
        vid = criar_veiculo_pub(client).json['id']
        r = client.post(f'/api/veiculos/{vid}/fotos', json={'tipo': 'selfie', 'caminho': 'x.jpg'})
        assert r.status_code == 422

    def test_remover_foto(self, client):
        registrar_e_logar(client, LOJISTA_1)
        vid = criar_veiculo_pub(client).json['id']
        foto_id = client.post(f'/api/veiculos/{vid}/fotos', json={
            'tipo': 'geral', 'caminho': 'uploads/f.jpg'
        }).json['id']
        assert client.delete(f'/api/fotos/{foto_id}').status_code == 200

    def test_remover_foto_de_outro_lojista_403(self, client):
        registrar_e_logar(client, LOJISTA_1)
        vid = criar_veiculo_pub(client).json['id']
        foto_id = client.post(f'/api/veiculos/{vid}/fotos', json={
            'tipo': 'geral', 'caminho': 'uploads/f.jpg'
        }).json['id']
        client.post('/api/auth/logout')
        registrar_e_logar(client, LOJISTA_2)
        assert client.delete(f'/api/fotos/{foto_id}').status_code == 403


class TestMeusAnuncios:

    def test_lista_todos_os_status_proprios(self, client):
        registrar_e_logar(client, LOJISTA_1)
        criar_veiculo_pub(client)      # rascunho
        _criar_e_publicar(client)      # ativo
        r = client.get('/api/meus-anuncios')
        assert r.status_code == 200
        assert r.json['total'] == 2

    def test_filtra_por_status(self, client):
        registrar_e_logar(client, LOJISTA_1)
        criar_veiculo_pub(client)
        _criar_e_publicar(client)
        r = client.get('/api/meus-anuncios?status=rascunho')
        assert r.json['total'] == 1

    def test_nao_mostra_veiculos_de_outros(self, client):
        registrar_e_logar(client, LOJISTA_1)
        _criar_e_publicar(client)
        client.post('/api/auth/logout')
        registrar_e_logar(client, LOJISTA_2)
        assert client.get('/api/meus-anuncios').json['total'] == 0
