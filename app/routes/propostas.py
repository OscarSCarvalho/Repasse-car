from flask import Blueprint, request, abort
from app.db import get_db
from app.session import login_required, lojista_id_sessao
from app.models import (
    criar_proposta, buscar_proposta, atualizar_status_proposta,
    buscar_veiculo, atualizar_status_veiculo,
)
from app.business_rules import validar_criacao_proposta, validar_transicao_status

bp = Blueprint('propostas', __name__)


@bp.route('/veiculos/<int:veiculo_id>/propostas', methods=['POST'])
@login_required
def criar(veiculo_id: int):
    conn = get_db()
    dados = request.get_json(silent=True) or {}

    if not dados.get('valor'):
        return {'erro': "'valor' é obrigatório."}, 422

    try:
        validar_criacao_proposta(conn, veiculo_id, lojista_id_sessao())
    except ValueError as e:
        return {'erro': str(e)}, 409

    pid = criar_proposta(conn, {
        'veiculo_id': veiculo_id,
        'lojista_comprador_id': lojista_id_sessao(),
        'valor': dados['valor'],
        'mensagem': dados.get('mensagem'),
    })
    conn.commit()
    return {'id': pid, 'mensagem': 'Proposta enviada.'}, 201


@bp.route('/propostas/<int:proposta_id>/status', methods=['PATCH'])
@login_required
def atualizar_status(proposta_id: int):
    conn = get_db()
    meu_id = lojista_id_sessao()

    proposta = buscar_proposta(conn, proposta_id)
    if not proposta:
        abort(404)

    veiculo = buscar_veiculo(conn, proposta['veiculo_id'])
    novo_status = (request.get_json(silent=True) or {}).get('status')

    if not novo_status:
        return {'erro': "'status' é obrigatório."}, 422

    if novo_status in ('aceita', 'recusada'):
        if veiculo['lojista_id'] != meu_id:
            abort(403)
    elif novo_status == 'cancelada':
        if proposta['lojista_comprador_id'] != meu_id:
            abort(403)
    else:
        return {'erro': f"Status inválido: '{novo_status}'. Use: aceita, recusada, cancelada."}, 422

    if proposta['status'] != 'pendente':
        return {'erro': 'Apenas propostas pendentes podem ser alteradas.'}, 409

    atualizar_status_proposta(conn, proposta_id, novo_status)

    if novo_status == 'aceita':
        try:
            validar_transicao_status(veiculo['status'], 'em_negociacao')
            atualizar_status_veiculo(conn, veiculo['id'], 'em_negociacao')
        except ValueError:
            pass  # veículo já pode estar em outro estado terminal

    conn.commit()
    return {'mensagem': f"Proposta {novo_status}.", 'status': novo_status}, 200


@bp.route('/propostas/recebidas', methods=['GET'])
@login_required
def recebidas():
    conn = get_db()
    rows = conn.execute(
        """
        SELECT p.*, v.marca, v.modelo, v.ano_modelo
          FROM propostas p
          JOIN veiculos v ON v.id = p.veiculo_id
         WHERE v.lojista_id = ?
         ORDER BY p.criado_em DESC
        """,
        (lojista_id_sessao(),),
    ).fetchall()
    return {'propostas': [dict(r) for r in rows]}, 200


@bp.route('/propostas/enviadas', methods=['GET'])
@login_required
def enviadas():
    conn = get_db()
    rows = conn.execute(
        """
        SELECT p.*, v.marca, v.modelo, v.ano_modelo
          FROM propostas p
          JOIN veiculos v ON v.id = p.veiculo_id
         WHERE p.lojista_comprador_id = ?
         ORDER BY p.criado_em DESC
        """,
        (lojista_id_sessao(),),
    ).fetchall()
    return {'propostas': [dict(r) for r in rows]}, 200
