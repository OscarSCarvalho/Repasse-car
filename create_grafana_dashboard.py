"""
Cria o dashboard CarApp Monitor no Grafana via REST API.
Usa /metrics/json (JSON puro) em vez de Prometheus text para compatibilidade.
Execute: python create_grafana_dashboard.py
"""
import json
import urllib.request
import urllib.error
import base64

GRAFANA_URL = "http://localhost:3000"
GRAFANA_USER = "admin"
GRAFANA_PASS = "Pablo@060711"
DS_UID = "dfxzddg2wkbnke"
JSON_URL = "http://localhost:5000/metrics/json"

def _auth_header():
    creds = base64.b64encode(f"{GRAFANA_USER}:{GRAFANA_PASS}".encode()).decode()
    return {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}

def _post(path, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        GRAFANA_URL + path, data=data, headers=_auth_header(), method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

def _get(path):
    req = urllib.request.Request(GRAFANA_URL + path, headers=_auth_header())
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())

def ds():
    return {"type": "yesoreyeram-infinity-datasource", "uid": DS_UID}

def json_target(ref, root_selector, columns):
    return {
        "refId": ref,
        "datasource": ds(),
        "type": "json",
        "source": "url",
        "format": "table",
        "url": JSON_URL,
        "url_options": {"method": "GET", "data": ""},
        "root_selector": root_selector,
        "columns": columns,
        "filters": [],
    }

def scalar_target(ref, field, label=None):
    """Target para um campo escalar do JSON raiz."""
    return json_target(ref, "", [{
        "selector": field,
        "text": label or field,
        "type": "number",
    }])

def stat_card(pid, title, field, gx, gy, w=4, h=4,
              color="blue", unit="short", label=None):
    return {
        "id": pid,
        "type": "stat",
        "title": title,
        "gridPos": {"x": gx, "y": gy, "w": w, "h": h},
        "datasource": ds(),
        "targets": [scalar_target("A", field, label or title)],
        "options": {
            "colorMode": "background",
            "graphMode": "none",
            "textMode": "value",
            "justifyMode": "center",
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
        },
        "fieldConfig": {
            "defaults": {
                "color": {"fixedColor": color, "mode": "fixed"},
                "unit": unit,
                "mappings": [],
            },
            "overrides": [],
        },
    }

def table_panel(pid, title, root, columns, gx, gy, w, h):
    return {
        "id": pid,
        "type": "table",
        "title": title,
        "gridPos": {"x": gx, "y": gy, "w": w, "h": h},
        "datasource": ds(),
        "targets": [json_target("A", root, columns)],
        "options": {
            "cellHeight": "sm",
            "footer": {"show": False},
            "showHeader": True,
        },
        "fieldConfig": {"defaults": {"custom": {"align": "auto"}}, "overrides": []},
    }

def bar_gauge_panel(pid, title, root, columns, gx, gy, w, h, color="blue"):
    return {
        "id": pid,
        "type": "bargauge",
        "title": title,
        "gridPos": {"x": gx, "y": gy, "w": w, "h": h},
        "datasource": ds(),
        "targets": [json_target("A", root, columns)],
        "options": {
            "orientation": "horizontal",
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "/^(count|errors)$/"},
            "displayMode": "gradient",
            "valueMode": "color",
            "text": {},
        },
        "fieldConfig": {
            "defaults": {
                "color": {"fixedColor": color, "mode": "fixed"},
                "custom": {"fillOpacity": 80},
            },
            "overrides": [],
        },
    }


def build_dashboard():
    panels = []

    # ── Linha 1 (y=0) — Contadores do banco ─────────────────────────────────
    panels.append(stat_card(1,  "Lojistas",     "lojistas",       0,  0, color="green"))
    panels.append(stat_card(2,  "Veiculos",     "veiculos",       4,  0, color="orange"))
    panels.append(stat_card(3,  "Propostas",    "propostas",      8,  0, color="blue"))
    panels.append(stat_card(4,  "Mensagens",    "mensagens",      12, 0, color="yellow"))
    panels.append(stat_card(5,  "Fotos",        "fotos",          16, 0, color="purple"))
    panels.append(stat_card(6,  "Uptime (s)",   "uptime_seconds", 20, 0, color="grey", unit="s"))

    # ── Linha 2 (y=4) — Metricas HTTP ───────────────────────────────────────
    panels.append(stat_card(10, "Total Requisicoes", "total_requests", 0,  4, w=6, color="blue"))
    panels.append(stat_card(11, "Total Erros 4/5xx", "total_errors",   6,  4, w=6, color="red"))
    panels.append(stat_card(12, "Taxa de Erro %",    "taxa_erro_pct",  12, 4, w=6, color="orange", unit="percent"))

    # ── Linha 3 (y=8) — Veiculos por status ─────────────────────────────────
    status_fields = [
        ("veiculos_por_status.rascunho",    "Rascunho",   "grey"),
        ("veiculos_por_status.ativo",       "Ativo",      "green"),
        ("veiculos_por_status.em_negociacao","Negociacao", "yellow"),
        ("veiculos_por_status.vendido",     "Vendido",    "blue"),
        ("veiculos_por_status.cancelado",   "Cancelado",  "red"),
    ]
    for i, (field, label, color) in enumerate(status_fields):
        panels.append(stat_card(20 + i, label, field, i * 4, 8, w=4, h=4, color=color))

    # Padding para alinhar (ocupa ate col 20, deixa 4 livres)
    # ── Linha 4 (y=12) — Bar gauge requisicoes por endpoint ─────────────────
    panels.append(bar_gauge_panel(
        30,
        "Requisicoes por Endpoint (Top 10)",
        "requests_by_endpoint",
        [
            {"selector": "endpoint", "text": "Endpoint", "type": "string"},
            {"selector": "count",    "text": "count",    "type": "number"},
        ],
        0, 12, 12, 10,
        color="blue",
    ))

    panels.append(bar_gauge_panel(
        31,
        "Erros por Endpoint",
        "errors_by_endpoint",
        [
            {"selector": "endpoint", "text": "Endpoint", "type": "string"},
            {"selector": "errors",   "text": "errors",   "type": "number"},
        ],
        12, 12, 12, 10,
        color="red",
    ))

    # ── Linha 5 (y=22) — Tabelas detalhadas ─────────────────────────────────
    panels.append(table_panel(
        40,
        "Tabela — Requisicoes por Endpoint",
        "requests_by_endpoint",
        [
            {"selector": "endpoint", "text": "Endpoint", "type": "string"},
            {"selector": "count",    "text": "Requisicoes", "type": "number"},
        ],
        0, 22, 12, 8,
    ))

    panels.append(table_panel(
        41,
        "Tabela — Erros por Endpoint",
        "errors_by_endpoint",
        [
            {"selector": "endpoint", "text": "Endpoint", "type": "string"},
            {"selector": "errors",   "text": "Erros",    "type": "number"},
        ],
        12, 22, 12, 8,
    ))

    return {
        "dashboard": {
            "id": None,
            "uid": "carapp-monitor-v2",
            "title": "CarApp - Monitor de Producao",
            "tags": ["carapp", "flask"],
            "timezone": "browser",
            "schemaVersion": 38,
            "version": 1,
            "refresh": "5s",
            "time": {"from": "now-1h", "to": "now"},
            "panels": panels,
        },
        "folderId": 0,
        "overwrite": True,
        "message": "v2 - JSON puro sem UQL",
    }


def main():
    print("CarApp - Recriando dashboard (v2 JSON)")
    print("=" * 50)

    try:
        org = _get("/api/org")
        print(f"[OK] Grafana conectado - org: {org.get('name')}")
    except Exception as e:
        print(f"[ERRO] Nao conectou ao Grafana: {e}")
        return

    payload = build_dashboard()
    with open("grafana_dashboard_v2.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print("[OK] JSON salvo em grafana_dashboard_v2.json")

    status, resp = _post("/api/dashboards/db", payload)
    if status in (200, 201):
        slug = resp.get("url", "")
        print(f"[OK] Dashboard criado!")
        print(f"  URL: http://localhost:3000{slug}")
    else:
        print(f"[ERRO] HTTP {status}: {resp}")


if __name__ == "__main__":
    main()
