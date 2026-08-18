import json
from flask import Blueprint, request, abort
from app.db import get_db
from app.session import login_required, lojista_id_sessao
from app.models import (
    criar_veiculo, buscar_veiculo, atualizar_status_veiculo,
    adicionar_selo_veiculo, remover_selo_veiculo, listar_selos_veiculo,
    adicionar_foto, listar_fotos_veiculo, pesquisar_veiculos,
)
from app.business_rules import validar_transicao_status, validar_publicacao_veiculo

bp = Blueprint('veiculos', __name__)

_CAMPOS_OBRIGATORIOS = [
    'marca', 'modelo', 'ano_fabricacao', 'ano_modelo',
    'kilometragem', 'cambio', 'combustivel', 'preco',
]
_CAMPOS_EDITAVEIS = [
    'marca', 'modelo', 'ano_fabricacao', 'ano_modelo', 'versao', 'cor',
    'kilometragem', 'cambio', 'combustivel', 'placa',
    'preco', 'codigo_fipe', 'valor_fipe', 'descricao',
]


def _ou_404(conn, veiculo_id: int) -> dict:
    v = buscar_veiculo(conn, veiculo_id)
    if not v:
        abort(404)
    return v


def _exigir_dono(veiculo: dict) -> None:
    if veiculo['lojista_id'] != lojista_id_sessao():
        abort(403)


def _detalhe_completo(conn, veiculo: dict) -> dict:
    selos = listar_selos_veiculo(conn, veiculo['id'])
    for s in selos:
        s['campos_especificos'] = json.loads(s.get('campos_especificos') or '{}')
    return {**veiculo, 'selos': selos, 'fotos': listar_fotos_veiculo(conn, veiculo['id'])}


# ── Listagem pública ───────────────────────────────────────────────────────────

@bp.route('/veiculos', methods=['GET'])
def listar():
    conn = get_db()
    veiculos = pesquisar_veiculos(
        conn,
        status='ativo',
        marca=request.args.get('marca'),
        cidade_lojista=request.args.get('cidade'),
        categoria_defeito=request.args.get('categoria_defeito'),
        preco_min=request.args.get('preco_min', type=int),
        preco_max=request.args.get('preco_max', type=int),
    )
    return {'veiculos': veiculos, 'total': len(veiculos)}, 200


@bp.route('/veiculos/<int:veiculo_id>', methods=['GET'])
def detalhe(veiculo_id: int):
    conn = get_db()
    return _detalhe_completo(conn, _ou_404(conn, veiculo_id)), 200


# ── CRUD autenticado ───────────────────────────────────────────────────────────

@bp.route('/veiculos', methods=['POST'])
@login_required
def criar():
    dados = request.get_json(silent=True) or {}
    faltando = [c for c in _CAMPOS_OBRIGATORIOS if dados.get(c) is None]
    if faltando:
        return {'erro': f"Campos obrigatórios: {', '.join(faltando)}."}, 422

    conn = get_db()
    vid = criar_veiculo(conn, {**dados, 'lojista_id': lojista_id_sessao()})
    conn.commit()
    return {'id': vid, 'mensagem': 'Veículo criado em rascunho.'}, 201


@bp.route('/veiculos/<int:veiculo_id>', methods=['PATCH'])
@login_required
def atualizar(veiculo_id: int):
    conn = get_db()
    veiculo = _ou_404(conn, veiculo_id)
    _exigir_dono(veiculo)

    if veiculo['status'] != 'rascunho':
        return {'erro': 'Edição permitida apenas em rascunho.'}, 409

    dados = request.get_json(silent=True) or {}
    atualizacoes = {k: v for k, v in dados.items() if k in _CAMPOS_EDITAVEIS}
    if not atualizacoes:
        return {'erro': 'Nenhum campo editável enviado.'}, 422

    sets = ', '.join(f'{k} = ?' for k in atualizacoes)
    conn.execute(
        f"UPDATE veiculos SET {sets}, atualizado_em = CURRENT_TIMESTAMP WHERE id = ?",
        [*atualizacoes.values(), veiculo_id],
    )
    conn.commit()
    return buscar_veiculo(conn, veiculo_id), 200


@bp.route('/veiculos/<int:veiculo_id>/publicar', methods=['POST'])
@login_required
def publicar(veiculo_id: int):
    conn = get_db()
    veiculo = _ou_404(conn, veiculo_id)
    _exigir_dono(veiculo)

    try:
        validar_transicao_status(veiculo['status'], 'ativo')
        validar_publicacao_veiculo(conn, veiculo_id)
    except ValueError as e:
        return {'erro': str(e)}, 409

    atualizar_status_veiculo(conn, veiculo_id, 'ativo')
    conn.commit()
    return {'mensagem': 'Anúncio publicado.', 'status': 'ativo'}, 200


@bp.route('/veiculos/<int:veiculo_id>/cancelar', methods=['POST'])
@login_required
def cancelar(veiculo_id: int):
    conn = get_db()
    veiculo = _ou_404(conn, veiculo_id)
    _exigir_dono(veiculo)

    try:
        validar_transicao_status(veiculo['status'], 'cancelado')
    except ValueError as e:
        return {'erro': str(e)}, 409

    atualizar_status_veiculo(conn, veiculo_id, 'cancelado')
    conn.commit()
    return {'mensagem': 'Anúncio cancelado.', 'status': 'cancelado'}, 200


# ── Selos ──────────────────────────────────────────────────────────────────────

@bp.route('/veiculos/<int:veiculo_id>/selos', methods=['POST'])
@login_required
def adicionar_selo(veiculo_id: int):
    conn = get_db()
    _exigir_dono(_ou_404(conn, veiculo_id))

    dados = request.get_json(silent=True) or {}
    selo_id = dados.get('selo_id')
    if not selo_id:
        return {'erro': "'selo_id' é obrigatório."}, 422

    if not conn.execute("SELECT 1 FROM selos_defeito WHERE id = ?", (selo_id,)).fetchone():
        return {'erro': 'Selo não encontrado.'}, 404

    try:
        vs_id = adicionar_selo_veiculo(
            conn, veiculo_id, selo_id,
            dados.get('campos_especificos') or {},
        )
        conn.commit()
    except Exception as e:
        if 'UNIQUE constraint' in str(e):
            return {'erro': 'Selo já vinculado a este veículo.'}, 409
        raise

    return {'id': vs_id, 'mensagem': 'Selo adicionado.'}, 201


@bp.route('/veiculos/<int:veiculo_id>/selos/<int:selo_id>', methods=['DELETE'])
@login_required
def remover_selo(veiculo_id: int, selo_id: int):
    conn = get_db()
    _exigir_dono(_ou_404(conn, veiculo_id))
    remover_selo_veiculo(conn, veiculo_id, selo_id)
    conn.commit()
    return {'mensagem': 'Selo removido.'}, 200


# ── Fotos ──────────────────────────────────────────────────────────────────────

@bp.route('/veiculos/<int:veiculo_id>/fotos', methods=['POST'])
@login_required
def adicionar_foto_rota(veiculo_id: int):
    conn = get_db()
    _exigir_dono(_ou_404(conn, veiculo_id))

    dados = request.get_json(silent=True) or {}
    if not dados.get('tipo') or not dados.get('caminho'):
        return {'erro': "Campos obrigatórios: 'tipo', 'caminho'."}, 422
    if dados['tipo'] not in ('geral', 'avaria', 'laudo'):
        return {'erro': "'tipo' deve ser: geral, avaria ou laudo."}, 422

    foto_id = adicionar_foto(conn, {**dados, 'veiculo_id': veiculo_id})
    conn.commit()
    return {'id': foto_id, 'mensagem': 'Foto adicionada.'}, 201


@bp.route('/fotos/<int:foto_id>', methods=['DELETE'])
@login_required
def remover_foto(foto_id: int):
    conn = get_db()
    foto = conn.execute(
        """SELECT f.id, v.lojista_id FROM fotos_veiculo f
             JOIN veiculos v ON v.id = f.veiculo_id
            WHERE f.id = ?""",
        (foto_id,),
    ).fetchone()
    if not foto:
        abort(404)
    if foto['lojista_id'] != lojista_id_sessao():
        abort(403)
    conn.execute("DELETE FROM fotos_veiculo WHERE id = ?", (foto_id,))
    conn.commit()
    return {'mensagem': 'Foto removida.'}, 200


# ── Meus anúncios ──────────────────────────────────────────────────────────────

@bp.route('/meus-anuncios', methods=['GET'])
@login_required
def meus_anuncios():
    conn = get_db()
    status_filtro = request.args.get('status')
    query = "SELECT * FROM veiculos WHERE lojista_id = ?"
    params: list = [lojista_id_sessao()]
    if status_filtro:
        query += " AND status = ?"
        params.append(status_filtro)
    query += " ORDER BY criado_em DESC"
    veiculos = [dict(r) for r in conn.execute(query, params).fetchall()]
    return {'veiculos': veiculos, 'total': len(veiculos)}, 200
