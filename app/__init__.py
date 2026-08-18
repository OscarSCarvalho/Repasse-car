from flask import Flask, g, redirect, url_for, request
from config import Config


import json as _json


def _brl(centavos: int) -> str:
    return f"R$ {centavos / 100:_.2f}".replace('.', ',').replace('_', '.')


def create_app(config=None):
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    app.config.from_object(config or Config)

    app.jinja_env.filters['brl'] = _brl
    app.jinja_env.filters['fromjson'] = _json.loads

    @app.teardown_appcontext
    def _fechar_db(exc):
        db = g.pop('db', None)
        if db is not None:
            db.close()

    from app.routes.auth import bp as auth_bp
    from app.routes.veiculos import bp as veiculos_bp
    from app.routes.propostas import bp as propostas_bp
    from app.routes.web import bp as web_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(veiculos_bp, url_prefix='/api')
    app.register_blueprint(propostas_bp, url_prefix='/api')
    app.register_blueprint(web_bp)

    @app.errorhandler(401)
    def _nao_autenticado(e):
        if request.path.startswith('/api/'):
            return {'erro': 'Autenticação necessária.'}, 401
        return redirect(url_for('web.login'))

    @app.errorhandler(403)
    def _proibido(e):
        if request.path.startswith('/api/'):
            return {'erro': 'Acesso não autorizado.'}, 403
        return redirect(url_for('web.index'))

    @app.errorhandler(404)
    def _nao_encontrado(e):
        if request.path.startswith('/api/'):
            return {'erro': 'Recurso não encontrado.'}, 404
        return redirect(url_for('web.index'))

    return app
