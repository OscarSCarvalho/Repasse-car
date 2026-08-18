import re
from flask import Blueprint, request, session
from werkzeug.security import check_password_hash, generate_password_hash
from app.db import get_db
from app.session import login_required, lojista_id_sessao
from app.models import (
    criar_lojista, buscar_lojista,
    buscar_lojista_por_email, buscar_lojista_por_cnpj,
)
from app.business_rules import validar_cnpj

bp = Blueprint('auth', __name__, url_prefix='/auth')

_CAMPOS_REGISTRO = ['nome_fantasia', 'razao_social', 'cnpj', 'email', 'senha', 'cidade', 'uf']


@bp.route('/registro', methods=['POST'])
def registro():
    dados = request.get_json(silent=True) or {}
    faltando = [c for c in _CAMPOS_REGISTRO if not dados.get(c)]
    if faltando:
        return {'erro': f"Campos obrigatórios ausentes: {', '.join(faltando)}."}, 422

    if not validar_cnpj(dados['cnpj']):
        return {'erro': 'CNPJ inválido.'}, 422

    cnpj = re.sub(r'\D', '', dados['cnpj'])
    email = dados['email'].strip().lower()
    conn = get_db()

    if buscar_lojista_por_cnpj(conn, cnpj):
        return {'erro': 'CNPJ já cadastrado.'}, 409

    if buscar_lojista_por_email(conn, email):
        return {'erro': 'E-mail já cadastrado.'}, 409

    lojista_id = criar_lojista(conn, {
        **dados,
        'cnpj': cnpj,
        'email': email,
        'senha_hash': generate_password_hash(dados['senha']),
    })
    conn.commit()
    session['lojista_id'] = lojista_id
    return {'id': lojista_id, 'mensagem': 'Conta criada com sucesso.'}, 201


@bp.route('/login', methods=['POST'])
def login():
    dados = request.get_json(silent=True) or {}
    email = (dados.get('email') or '').strip().lower()
    senha = dados.get('senha') or ''

    if not email or not senha:
        return {'erro': 'E-mail e senha são obrigatórios.'}, 422

    conn = get_db()
    lojista = buscar_lojista_por_email(conn, email)

    if not lojista or not check_password_hash(lojista['senha_hash'], senha):
        return {'erro': 'Credenciais inválidas.'}, 401

    if not lojista['ativo']:
        return {'erro': 'Conta desativada.'}, 403

    session['lojista_id'] = lojista['id']
    return {'id': lojista['id'], 'mensagem': 'Login realizado.'}, 200


@bp.route('/logout', methods=['POST'])
@login_required
def logout():
    session.clear()
    return {'mensagem': 'Logout realizado.'}, 200


@bp.route('/me', methods=['GET'])
@login_required
def me():
    conn = get_db()
    lojista = buscar_lojista(conn, lojista_id_sessao())
    lojista.pop('senha_hash', None)
    return lojista, 200
