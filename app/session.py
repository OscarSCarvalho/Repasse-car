from functools import wraps
from flask import session, abort


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'lojista_id' not in session:
            abort(401)
        return f(*args, **kwargs)
    return decorated


def lojista_id_sessao() -> int:
    return session['lojista_id']
