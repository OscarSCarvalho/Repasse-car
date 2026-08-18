import json
import os
import uuid
from functools import wraps

from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash, abort, current_app,
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from app.db import get_db
from app.session import lojista_id_sessao
from app.models import (
    criar_lojista, buscar_lojista, buscar_lojista_por_email,
    buscar_lojista_por_cnpj, criar_veiculo, buscar_veiculo,
    atualizar_status_veiculo, adicionar_selo_veiculo, remover_selo_veiculo,
    listar_selos_veiculo, listar_selos_disponiveis, adicionar_foto,
    listar_fotos_veiculo, criar_proposta, buscar_proposta,
    atualizar_status_proposta, pesquisar_veiculos,
)
from app.business_rules import (
    validar_cnpj, validar_transicao_status,
    validar_publicacao_veiculo, validar_criacao_proposta,
    validar_transicao_status,
)

bp = Blueprint('web', __name__)

_UFS = [
    'AC','AL','AM','AP','BA','CE','DF','ES','GO','MA','MG','MS','MT',
    'PA','PB','PE','PI','PR','RJ','RN','RO','RR','RS','SC','SE','SP','TO',
]
_CAMPOS_OBRIGATORIOS = [
    'marca', 'modelo', 'ano_fabricacao', 'ano_modelo',
    'kilometragem', 'cambio', 'combustivel', 'preco',
]
_EXTENSOES_PERMITIDAS = {'jpg', 'jpeg', 'png', 'webp'}


def _web_login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'lojista_id' not in session:
            flash('Faça login para continuar.', 'warning')
            return redirect(url_for('web.login'))
        return f(*args, **kwargs)
    return decorated


def _extensao_ok(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in _EXTENSOES_PERMITIDAS


def _salvar_arquivo(arquivo) -> str | None:
    if not arquivo or not arquivo.filename:
        return None
    if not _extensao_ok(arquivo.filename):
        return None
    ext = arquivo.filename.rsplit('.', 1)[1].lower()
    nome = f"{uuid.uuid4().hex}.{ext}"
    pasta = current_app.config.get('UPLOAD_FOLDER', 'static/uploads')
    os.makedirs(pasta, exist_ok=True)
    arquivo.save(os.path.join(pasta, nome))
    return f"uploads/{nome}"


def _lojista_atual(conn) -> dict | None:
    lid = session.get('lojista_id')
    return buscar_lojista(conn, lid) if lid else None


# ── Auth ──────────────────────────────────────────────────────────────────────

@bp.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        dados = request.form
        campos = ['nome_fantasia', 'razao_social', 'cnpj', 'email',
                  'senha', 'confirmar_senha', 'cidade', 'uf']
        faltando = [c for c in campos if not dados.get(c)]
        if faltando:
            flash('Preencha todos os campos obrigatórios.', 'danger')
            return render_template('auth/cadastro.html', ufs=_UFS, form=dados)

        if dados['senha'] != dados['confirmar_senha']:
            flash('As senhas não conferem.', 'danger')
            return render_template('auth/cadastro.html', ufs=_UFS, form=dados)

        cnpj = ''.join(filter(str.isdigit, dados['cnpj']))
        if not validar_cnpj(cnpj):
            flash('CNPJ inválido.', 'danger')
            return render_template('auth/cadastro.html', ufs=_UFS, form=dados)

        conn = get_db()
        if buscar_lojista_por_cnpj(conn, cnpj):
            flash('CNPJ já cadastrado.', 'danger')
            return render_template('auth/cadastro.html', ufs=_UFS, form=dados)

        email = dados['email'].lower().strip()
        if buscar_lojista_por_email(conn, email):
            flash('E-mail já cadastrado.', 'danger')
            return render_template('auth/cadastro.html', ufs=_UFS, form=dados)

        lid = criar_lojista(conn, {
            'nome_fantasia': dados['nome_fantasia'],
            'razao_social': dados['razao_social'],
            'cnpj': cnpj,
            'email': email,
            'senha_hash': generate_password_hash(dados['senha']),
            'telefone_whatsapp': dados.get('telefone_whatsapp') or None,
            'cidade': dados['cidade'],
            'uf': dados['uf'],
        })
        conn.commit()
        session.clear()
        session['lojista_id'] = lid
        flash('Conta criada com sucesso!', 'success')
        return redirect(url_for('web.index'))

    return render_template('auth/cadastro.html', ufs=_UFS, form={})


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = (request.form.get('email') or '').lower().strip()
        senha = request.form.get('senha') or ''
        conn = get_db()
        lojista = buscar_lojista_por_email(conn, email)
        if not lojista or not check_password_hash(lojista['senha_hash'], senha):
            flash('E-mail ou senha incorretos.', 'danger')
            return render_template('auth/login.html')
        session.clear()
        session['lojista_id'] = lojista['id']
        return redirect(url_for('web.index'))

    return render_template('auth/login.html')


@bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    flash('Você saiu da conta.', 'info')
    return redirect(url_for('web.login'))


# ── Listagem pública ──────────────────────────────────────────────────────────

@bp.route('/')
def index():
    conn = get_db()
    marca = request.args.get('marca', '').strip() or None
    cidade = request.args.get('cidade', '').strip() or None
    categoria = request.args.get('categoria') or None
    preco_min = request.args.get('preco_min', type=int)
    preco_max = request.args.get('preco_max', type=int)

    meu_id = session.get('lojista_id')
    veiculos_raw = pesquisar_veiculos(
        conn, status='ativo',
        marca=marca, cidade_lojista=cidade,
        categoria_defeito=categoria,
        preco_min=preco_min, preco_max=preco_max,
    )
    # esconde anúncios do próprio lojista logado
    veiculos = [v for v in veiculos_raw if v['lojista_id'] != meu_id]

    # anexa primeira foto de cada veículo
    for v in veiculos:
        row = conn.execute(
            "SELECT caminho FROM fotos_veiculo WHERE veiculo_id = ? ORDER BY ordem, id LIMIT 1",
            (v['id'],)
        ).fetchone()
        v['foto_capa'] = row['caminho'] if row else None

    categorias = conn.execute("SELECT * FROM categorias_defeito ORDER BY id").fetchall()
    return render_template('veiculos/listagem.html',
                           veiculos=veiculos, categorias=categorias,
                           filtros={'marca': marca, 'cidade': cidade,
                                    'categoria': categoria,
                                    'preco_min': preco_min, 'preco_max': preco_max})


@bp.route('/veiculo/<int:veiculo_id>')
def detalhe_veiculo(veiculo_id: int):
    conn = get_db()
    veiculo = buscar_veiculo(conn, veiculo_id)
    if not veiculo:
        abort(404)

    selos = listar_selos_veiculo(conn, veiculo_id)
    for s in selos:
        s['campos_especificos'] = json.loads(s.get('campos_especificos') or '{}')
    fotos = listar_fotos_veiculo(conn, veiculo_id)
    lojista = buscar_lojista(conn, veiculo['lojista_id'])

    meu_id = session.get('lojista_id')
    sou_dono = meu_id == veiculo['lojista_id']

    proposta_aceita = None
    if sou_dono and veiculo['status'] in ('em_negociacao', 'vendido'):
        proposta_aceita = conn.execute(
            """SELECT p.*, l.telefone_whatsapp, l.nome_fantasia AS comprador_nome
                 FROM propostas p
                 JOIN lojistas l ON l.id = p.lojista_comprador_id
                WHERE p.veiculo_id = ? AND p.status = 'aceita'
                ORDER BY p.atualizado_em DESC LIMIT 1""",
            (veiculo_id,)
        ).fetchone()

    return render_template('veiculos/detalhe.html',
                           veiculo=veiculo, selos=selos, fotos=fotos,
                           lojista=lojista, sou_dono=sou_dono,
                           meu_id=meu_id, proposta_aceita=proposta_aceita)


# ── Novo anúncio (fluxo único) ────────────────────────────────────────────────

@bp.route('/novo-anuncio', methods=['GET', 'POST'])
@_web_login_required
def novo_anuncio():
    conn = get_db()
    selos_disponiveis = listar_selos_disponiveis(conn)

    if request.method == 'POST':
        form = request.form
        faltando = [c for c in _CAMPOS_OBRIGATORIOS if not form.get(c)]
        if faltando:
            flash(f"Campos obrigatórios: {', '.join(faltando)}.", 'danger')
            return render_template('veiculos/form_veiculo.html',
                                   selos=selos_disponiveis, form=form)

        try:
            preco = int(float(form['preco'].replace(',', '.')) * 100)
        except (ValueError, TypeError):
            flash('Preço inválido.', 'danger')
            return render_template('veiculos/form_veiculo.html',
                                   selos=selos_disponiveis, form=form)

        vid = criar_veiculo(conn, {
            'lojista_id': lojista_id_sessao(),
            'marca': form['marca'],
            'modelo': form['modelo'],
            'ano_fabricacao': int(form['ano_fabricacao']),
            'ano_modelo': int(form['ano_modelo']),
            'versao': form.get('versao') or None,
            'cor': form.get('cor') or None,
            'kilometragem': int(form['kilometragem']),
            'cambio': form['cambio'],
            'combustivel': form['combustivel'],
            'placa': form.get('placa') or None,
            'preco': preco,
            'descricao': form.get('descricao') or None,
        })

        # selos marcados
        for s in selos_disponiveis:
            sid = str(s['id'])
            if form.get(f'selo_{sid}'):
                campos = {}
                obrig = json.loads(s['campos_obrigatorios'] or '[]')
                for campo in obrig:
                    campos[campo] = form.get(f'campo_{sid}_{campo}', '')
                adicionar_selo_veiculo(conn, vid, s['id'], campos)

                # foto de avaria vinculada ao selo
                arquivo_avaria = request.files.get(f'foto_avaria_{sid}')
                if arquivo_avaria and arquivo_avaria.filename:
                    caminho = _salvar_arquivo(arquivo_avaria)
                    if caminho:
                        vs = conn.execute(
                            "SELECT id FROM veiculo_selos WHERE veiculo_id=? AND selo_id=?",
                            (vid, s['id'])
                        ).fetchone()
                        adicionar_foto(conn, {
                            'veiculo_id': vid,
                            'veiculo_selo_id': vs['id'] if vs else None,
                            'tipo': 'avaria',
                            'caminho': caminho,
                        })

        # fotos gerais
        for arquivo in request.files.getlist('fotos_gerais'):
            caminho = _salvar_arquivo(arquivo)
            if caminho:
                adicionar_foto(conn, {'veiculo_id': vid, 'tipo': 'geral', 'caminho': caminho})

        conn.commit()
        flash('Anúncio criado em rascunho. Adicione selos e publique quando estiver pronto.', 'success')
        return redirect(url_for('web.meus_anuncios'))

    return render_template('veiculos/form_veiculo.html',
                           selos=selos_disponiveis, form={})


# ── Meus anúncios ─────────────────────────────────────────────────────────────

@bp.route('/meus-anuncios')
@_web_login_required
def meus_anuncios():
    conn = get_db()
    status_filtro = request.args.get('status') or None
    query = "SELECT * FROM veiculos WHERE lojista_id = ?"
    params: list = [lojista_id_sessao()]
    if status_filtro:
        query += " AND status = ?"
        params.append(status_filtro)
    query += " ORDER BY criado_em DESC"
    veiculos = [dict(r) for r in conn.execute(query, params).fetchall()]
    return render_template('veiculos/meus_anuncios.html',
                           veiculos=veiculos, status_filtro=status_filtro)


@bp.route('/veiculo/<int:veiculo_id>/publicar', methods=['POST'])
@_web_login_required
def publicar(veiculo_id: int):
    conn = get_db()
    veiculo = buscar_veiculo(conn, veiculo_id)
    if not veiculo or veiculo['lojista_id'] != lojista_id_sessao():
        abort(403)
    try:
        validar_transicao_status(veiculo['status'], 'ativo')
        validar_publicacao_veiculo(conn, veiculo_id)
    except ValueError as e:
        flash(str(e), 'danger')
        return redirect(url_for('web.meus_anuncios'))
    atualizar_status_veiculo(conn, veiculo_id, 'ativo')
    conn.commit()
    flash('Anúncio publicado com sucesso!', 'success')
    return redirect(url_for('web.meus_anuncios'))


@bp.route('/veiculo/<int:veiculo_id>/cancelar', methods=['POST'])
@_web_login_required
def cancelar(veiculo_id: int):
    conn = get_db()
    veiculo = buscar_veiculo(conn, veiculo_id)
    if not veiculo or veiculo['lojista_id'] != lojista_id_sessao():
        abort(403)
    try:
        validar_transicao_status(veiculo['status'], 'cancelado')
    except ValueError as e:
        flash(str(e), 'danger')
        return redirect(url_for('web.meus_anuncios'))
    atualizar_status_veiculo(conn, veiculo_id, 'cancelado')
    conn.commit()
    flash('Anúncio cancelado.', 'info')
    return redirect(url_for('web.meus_anuncios'))


@bp.route('/veiculo/<int:veiculo_id>/concluir', methods=['POST'])
@_web_login_required
def concluir_venda(veiculo_id: int):
    conn = get_db()
    veiculo = buscar_veiculo(conn, veiculo_id)
    if not veiculo or veiculo['lojista_id'] != lojista_id_sessao():
        abort(403)
    try:
        validar_transicao_status(veiculo['status'], 'vendido')
    except ValueError as e:
        flash(str(e), 'danger')
        return redirect(url_for('web.meus_anuncios'))
    atualizar_status_veiculo(conn, veiculo_id, 'vendido')
    conn.commit()
    flash('Venda concluída! Parabéns.', 'success')
    return redirect(url_for('web.meus_anuncios'))


# ── Propostas ─────────────────────────────────────────────────────────────────

@bp.route('/propostas')
@_web_login_required
def propostas():
    conn = get_db()
    meu_id = lojista_id_sessao()
    recebidas = conn.execute(
        """SELECT p.*, v.marca, v.modelo, v.ano_modelo,
                  l.nome_fantasia AS comprador_nome
             FROM propostas p
             JOIN veiculos v ON v.id = p.veiculo_id
             JOIN lojistas l ON l.id = p.lojista_comprador_id
            WHERE v.lojista_id = ?
            ORDER BY p.criado_em DESC""",
        (meu_id,)
    ).fetchall()
    enviadas = conn.execute(
        """SELECT p.*, v.marca, v.modelo, v.ano_modelo,
                  l.nome_fantasia AS vendedor_nome
             FROM propostas p
             JOIN veiculos v ON v.id = p.veiculo_id
             JOIN lojistas l ON l.id = v.lojista_id
            WHERE p.lojista_comprador_id = ?
            ORDER BY p.criado_em DESC""",
        (meu_id,)
    ).fetchall()
    return render_template('propostas/painel.html',
                           recebidas=[dict(r) for r in recebidas],
                           enviadas=[dict(r) for r in enviadas])


@bp.route('/veiculo/<int:veiculo_id>/proposta', methods=['POST'])
@_web_login_required
def enviar_proposta(veiculo_id: int):
    conn = get_db()
    try:
        validar_criacao_proposta(conn, veiculo_id, lojista_id_sessao())
    except ValueError as e:
        flash(str(e), 'danger')
        return redirect(url_for('web.detalhe_veiculo', veiculo_id=veiculo_id))

    valor_str = request.form.get('valor', '').replace(',', '.').replace(' ', '')
    try:
        valor = int(float(valor_str) * 100)
    except (ValueError, TypeError):
        flash('Valor inválido.', 'danger')
        return redirect(url_for('web.detalhe_veiculo', veiculo_id=veiculo_id))

    criar_proposta(conn, {
        'veiculo_id': veiculo_id,
        'lojista_comprador_id': lojista_id_sessao(),
        'valor': valor,
        'mensagem': request.form.get('mensagem') or None,
    })
    conn.commit()
    flash('Proposta enviada com sucesso!', 'success')
    return redirect(url_for('web.detalhe_veiculo', veiculo_id=veiculo_id))


@bp.route('/proposta/<int:proposta_id>/aceitar', methods=['POST'])
@_web_login_required
def aceitar_proposta(proposta_id: int):
    conn = get_db()
    proposta = buscar_proposta(conn, proposta_id)
    if not proposta:
        abort(404)
    veiculo = buscar_veiculo(conn, proposta['veiculo_id'])
    if veiculo['lojista_id'] != lojista_id_sessao():
        abort(403)
    if proposta['status'] != 'pendente':
        flash('Proposta não está mais pendente.', 'warning')
        return redirect(url_for('web.propostas'))
    atualizar_status_proposta(conn, proposta_id, 'aceita')
    try:
        validar_transicao_status(veiculo['status'], 'em_negociacao')
        atualizar_status_veiculo(conn, veiculo['id'], 'em_negociacao')
    except ValueError:
        pass
    conn.commit()
    flash('Proposta aceita! Veículo em negociação.', 'success')
    return redirect(url_for('web.propostas'))


@bp.route('/proposta/<int:proposta_id>/recusar', methods=['POST'])
@_web_login_required
def recusar_proposta(proposta_id: int):
    conn = get_db()
    proposta = buscar_proposta(conn, proposta_id)
    if not proposta:
        abort(404)
    veiculo = buscar_veiculo(conn, proposta['veiculo_id'])
    if veiculo['lojista_id'] != lojista_id_sessao():
        abort(403)
    if proposta['status'] != 'pendente':
        flash('Proposta não está mais pendente.', 'warning')
        return redirect(url_for('web.propostas'))
    atualizar_status_proposta(conn, proposta_id, 'recusada')
    conn.commit()
    flash('Proposta recusada.', 'info')
    return redirect(url_for('web.propostas'))


@bp.route('/proposta/<int:proposta_id>/cancelar', methods=['POST'])
@_web_login_required
def cancelar_proposta(proposta_id: int):
    conn = get_db()
    proposta = buscar_proposta(conn, proposta_id)
    if not proposta:
        abort(404)
    if proposta['lojista_comprador_id'] != lojista_id_sessao():
        abort(403)
    if proposta['status'] != 'pendente':
        flash('Proposta não está mais pendente.', 'warning')
        return redirect(url_for('web.propostas'))
    atualizar_status_proposta(conn, proposta_id, 'cancelada')
    conn.commit()
    flash('Proposta cancelada.', 'info')
    return redirect(url_for('web.propostas'))
