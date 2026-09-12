"""
Endpoint /metrics no formato Prometheus text (exposition format 0.0.4).
Grafana consome via data source Prometheus apontando para este servidor.
Não requer biblioteca externa — usa apenas stdlib.
"""
import sqlite3
import time
from pathlib import Path

from flask import Blueprint, current_app, Response, jsonify

bp = Blueprint('metrics', __name__)

_start_time = time.time()
_request_counts: dict[str, int] = {}
_request_errors: dict[str, int] = {}


def record_request(endpoint: str, status: int) -> None:
    _request_counts[endpoint] = _request_counts.get(endpoint, 0) + 1
    if status >= 400:
        _request_errors[endpoint] = _request_errors.get(endpoint, 0) + 1


def _db_stats() -> dict:
    try:
        db_path = current_app.config.get('DATABASE', '')
        if not db_path or not Path(db_path).exists():
            return {}
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        stats = {}
        for table in ('lojistas', 'veiculos', 'propostas', 'mensagens', 'fotos_veiculo'):
            row = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
            stats[table] = row['n']
        for status in ('rascunho', 'ativo', 'em_negociacao', 'vendido', 'cancelado'):
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM veiculos WHERE status=?", (status,)
            ).fetchone()
            stats[f'veiculos_{status}'] = row['n']
        conn.close()
        return stats
    except Exception:
        return {}


def _gauge(name: str, value, help_text: str, labels: str = '') -> str:
    label_str = f'{{{labels}}}' if labels else ''
    return (
        f'# HELP {name} {help_text}\n'
        f'# TYPE {name} gauge\n'
        f'{name}{label_str} {value}\n'
    )


def _counter(name: str, items: dict, help_text: str, label_key: str) -> str:
    lines = [f'# HELP {name} {help_text}', f'# TYPE {name} counter']
    for k, v in items.items():
        lines.append(f'{name}{{{label_key}="{k}"}} {v}')
    return '\n'.join(lines) + '\n'


@bp.route('/metrics')
def metrics():
    uptime = time.time() - _start_time
    db = _db_stats()

    parts = [
        _gauge('carapp_uptime_seconds', f'{uptime:.2f}', 'Tempo de atividade do servidor em segundos'),
        _gauge('carapp_lojistas_total', db.get('lojistas', 0), 'Total de lojistas cadastrados'),
        _gauge('carapp_veiculos_total', db.get('veiculos', 0), 'Total de veículos'),
        _gauge('carapp_propostas_total', db.get('propostas', 0), 'Total de propostas'),
        _gauge('carapp_mensagens_total', db.get('mensagens', 0), 'Total de mensagens de chat'),
        _gauge('carapp_fotos_total', db.get('fotos_veiculo', 0), 'Total de fotos de veículos'),
    ]

    for status in ('rascunho', 'ativo', 'em_negociacao', 'vendido', 'cancelado'):
        parts.append(
            _gauge(
                'carapp_veiculos_por_status',
                db.get(f'veiculos_{status}', 0),
                f'Veículos com status {status}',
                f'status="{status}"',
            )
        )

    if _request_counts:
        parts.append(_counter(
            'carapp_requests_total', _request_counts,
            'Total de requisições por endpoint', 'endpoint',
        ))
    if _request_errors:
        parts.append(_counter(
            'carapp_errors_total', _request_errors,
            'Total de erros (4xx/5xx) por endpoint', 'endpoint',
        ))

    body = '\n'.join(parts)
    return Response(body, mimetype='text/plain; version=0.0.4; charset=utf-8')


@bp.route('/metrics/json')
def metrics_json():
    uptime = time.time() - _start_time
    db = _db_stats()

    total_req = sum(_request_counts.values())
    total_err = sum(_request_errors.values())
    taxa = round((total_err / total_req * 100), 2) if total_req else 0.0

    requests_by_endpoint = [
        {"endpoint": ep or "/", "count": cnt}
        for ep, cnt in sorted(_request_counts.items(), key=lambda x: -x[1])
    ]
    errors_by_endpoint = [
        {"endpoint": ep or "/", "errors": cnt}
        for ep, cnt in sorted(_request_errors.items(), key=lambda x: -x[1])
    ]

    data = {
        "uptime_seconds": round(uptime, 1),
        "lojistas": db.get('lojistas', 0),
        "veiculos": db.get('veiculos', 0),
        "propostas": db.get('propostas', 0),
        "mensagens": db.get('mensagens', 0),
        "fotos": db.get('fotos_veiculo', 0),
        "total_requests": total_req,
        "total_errors": total_err,
        "taxa_erro_pct": taxa,
        "veiculos_por_status": {
            s: db.get(f'veiculos_{s}', 0)
            for s in ('rascunho', 'ativo', 'em_negociacao', 'vendido', 'cancelado')
        },
        "requests_by_endpoint": requests_by_endpoint,
        "errors_by_endpoint": errors_by_endpoint,
    }
    resp = jsonify(data)
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp
