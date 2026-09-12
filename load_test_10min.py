"""
Teste de performance de 10 minutos — CarApp
Gera trafego continuo e variado. Acompanhe em:
  - Grafana: http://localhost:3000/d/carapp-monitor-v1
  - Dashboard: http://localhost:5000/dashboard.html
  - Metricas: http://localhost:5000/metrics
Execute: python load_test_10min.py
"""
import time
import random
import threading
import urllib.request
import urllib.error
import json as _json
import sys

BASE = "http://localhost:5000"
DURACAO_SEGUNDOS = 600  # 10 minutos
THREADS = 6

_lock = threading.Lock()
_stats = {"ok": 0, "err": 0, "tempos": [], "inicio": 0.0}
_stop_event = threading.Event()


def _req(method, path, payload=None, cookies=None):
    url = BASE + path
    data = _json.dumps(payload).encode() if payload else None
    headers = {"Content-Type": "application/json"}
    if cookies:
        headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            resp.read()
            ms = (time.perf_counter() - t0) * 1000
            with _lock:
                _stats["ok"] += 1
                _stats["tempos"].append(ms)
            return resp.status, {}
    except urllib.error.HTTPError as e:
        ms = (time.perf_counter() - t0) * 1000
        e.read()
        with _lock:
            if e.code >= 500:
                _stats["err"] += 1
            else:
                _stats["ok"] += 1
            _stats["tempos"].append(ms)
        return e.code, {}
    except Exception:
        with _lock:
            _stats["err"] += 1
        return 0, {}


def _get_cookie(hdrs):
    for k, v in hdrs.items():
        if k.lower() == "set-cookie" and "session=" in v:
            for part in v.split(";"):
                if part.strip().startswith("session="):
                    return {"session": part.strip()[len("session="):]}
    return {}


# ── Cenarios ────────────────────────────────────────────────────────────────

def cenario_listagem():
    filtros = [
        "",
        "?marca=Honda",
        "?marca=Toyota",
        "?marca=VW",
        "?preco_min=1000000&preco_max=50000000",
        "?cidade=SP",
        "?cidade=RJ",
        "?combustivel=flex",
        "?cambio=automatico",
    ]
    for f in random.sample(filtros, 4):
        _req("GET", f"/api/veiculos{f}")
    _req("GET", "/api/veiculos/1")
    _req("GET", "/api/veiculos/2")
    _req("GET", "/")


def cenario_erros_esperados():
    _req("GET", "/api/auth/me")           # 401
    _req("POST", "/api/veiculos", {})     # 401
    _req("GET", "/api/veiculos/999999")   # 404
    _req("GET", "/rota-inexistente")      # 404


def cenario_auth(idx):
    cnpjs = [
        "11222333000181", "22333444000181", "33444555000181",
        "44555666000181", "55666777000181", "66777888000181",
        "77888999000181", "88999000000181",
    ]
    cnpj = cnpjs[idx % len(cnpjs)]
    email = f"perf10min{idx}@teste.com"

    url = BASE + "/api/auth/registro"
    payload = _json.dumps({
        "nome_fantasia": f"Loja Perf {idx}",
        "razao_social": f"Perf {idx} LTDA",
        "cnpj": cnpj, "email": email, "senha": "Senha@123",
        "cidade": "Sao Paulo", "uf": "SP",
    }).encode()
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"}, method="POST"
    )
    t0 = time.perf_counter()
    cookie = {}
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            ms = (time.perf_counter() - t0) * 1000
            cookie = _get_cookie(dict(r.headers))
            with _lock:
                _stats["ok"] += 1
                _stats["tempos"].append(ms)
    except urllib.error.HTTPError as e:
        ms = (time.perf_counter() - t0) * 1000
        e.read()
        with _lock:
            _stats["ok"] += 1
            _stats["tempos"].append(ms)

    if not cookie:
        url2 = BASE + "/api/auth/login"
        payload2 = _json.dumps({"email": email, "senha": "Senha@123"}).encode()
        req2 = urllib.request.Request(
            url2, data=payload2,
            headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(req2, timeout=5) as r:
                ms = (time.perf_counter() - t0) * 1000
                cookie = _get_cookie(dict(r.headers))
                with _lock:
                    _stats["ok"] += 1
                    _stats["tempos"].append(ms)
        except Exception:
            with _lock:
                _stats["err"] += 1

    if not cookie:
        return

    _req("GET", "/api/auth/me", cookies=cookie)
    _req("GET", "/api/meus-anuncios", cookies=cookie)
    _req("GET", "/api/propostas/recebidas", cookies=cookie)
    _req("GET", "/api/propostas/enviadas", cookies=cookie)
    _req("POST", "/api/auth/logout", cookies=cookie)


def cenario_crud_veiculo(idx):
    """Cria um veiculo como lojista existente."""
    email = f"perf10min{idx % 8}@teste.com"
    url2 = BASE + "/api/auth/login"
    payload2 = _json.dumps({"email": email, "senha": "Senha@123"}).encode()
    req2 = urllib.request.Request(
        url2, data=payload2,
        headers={"Content-Type": "application/json"}, method="POST"
    )
    cookie = {}
    try:
        with urllib.request.urlopen(req2, timeout=5) as r:
            cookie = _get_cookie(dict(r.headers))
            with _lock:
                _stats["ok"] += 1
    except Exception:
        return

    if not cookie:
        return

    marcas = ["Honda", "Toyota", "VW", "Ford", "Chevrolet", "Fiat", "Hyundai", "BMW"]
    _req("POST", "/api/veiculos", {
        "marca": random.choice(marcas),
        "modelo": f"Modelo{random.randint(1, 999)}",
        "ano_fabricacao": random.randint(2015, 2023),
        "ano_modelo": random.randint(2016, 2024),
        "kilometragem": random.randint(0, 200000),
        "cambio": random.choice(["manual", "automatico"]),
        "combustivel": random.choice(["flex", "gasolina", "diesel", "eletrico"]),
        "preco": random.randint(1500000, 50000000),
    }, cookies=cookie)
    _req("POST", "/api/auth/logout", cookies=cookie)


# ── Worker loop ──────────────────────────────────────────────────────────────

def worker(thread_id):
    iteration = 0
    while not _stop_event.is_set():
        idx = thread_id * 1000 + iteration

        roll = random.random()
        if roll < 0.50:
            cenario_listagem()
        elif roll < 0.70:
            cenario_erros_esperados()
        elif roll < 0.85:
            cenario_auth(idx)
        else:
            cenario_crud_veiculo(idx)

        time.sleep(random.uniform(0.1, 0.4))
        iteration += 1


# ── Monitor ──────────────────────────────────────────────────────────────────

def monitor():
    ultimo_ok = 0
    ultimo_err = 0
    ultimo_n = 0
    intervalo = 15  # segundos entre cada linha de status

    tempo_restante = DURACAO_SEGUNDOS
    inicio = time.time()

    # Barra de progresso simples
    COLS = 40

    while not _stop_event.is_set():
        time.sleep(intervalo)
        decorrido = time.time() - inicio
        restante = max(0, DURACAO_SEGUNDOS - decorrido)
        progresso = min(1.0, decorrido / DURACAO_SEGUNDOS)
        filled = int(COLS * progresso)
        bar = "#" * filled + "-" * (COLS - filled)

        with _lock:
            ok = _stats["ok"]
            err = _stats["err"]
            tempos = _stats["tempos"][:]

        delta_ok  = ok - ultimo_ok
        delta_err = err - ultimo_err
        rps = delta_ok / intervalo if intervalo > 0 else 0

        n = len(tempos)
        if n > ultimo_n:
            recentes = tempos[ultimo_n:]
            media = sum(recentes) / len(recentes)
            p95 = sorted(recentes)[int(len(recentes) * 0.95)] if recentes else 0
        else:
            media = p95 = 0

        ultimo_ok = ok
        ultimo_err = err
        ultimo_n = n

        min_rest = int(restante // 60)
        seg_rest = int(restante % 60)

        print(
            f"[{bar}] {int(progresso*100):3d}% | "
            f"Restante: {min_rest:02d}:{seg_rest:02d} | "
            f"+req={delta_ok:4d} +err={delta_err:3d} | "
            f"rps={rps:.1f} avg={media:.0f}ms p95={p95:.0f}ms | "
            f"Total: {ok} ok / {err} err",
            flush=True
        )

        if restante <= 0:
            break


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print(f"CarApp Load Test - 10 minutos")
    print(f"  Servidor  : {BASE}")
    print(f"  Threads   : {THREADS}")
    print(f"  Duracao   : {DURACAO_SEGUNDOS}s")
    print(f"  Grafana   : http://localhost:3000/d/carapp-monitor-v1")
    print(f"  Dashboard : http://localhost:5000/dashboard.html")
    print(f"  Metricas  : http://localhost:5000/metrics")
    print("=" * 70)
    print("Status a cada 15s: [progresso] restante | requisicoes | latencia | total")
    print("-" * 70)

    _stats["inicio"] = time.time()

    threads = []
    for i in range(THREADS):
        t = threading.Thread(target=worker, args=(i,), daemon=True)
        t.start()
        threads.append(t)

    mon = threading.Thread(target=monitor, daemon=True)
    mon.start()

    try:
        time.sleep(DURACAO_SEGUNDOS)
    except KeyboardInterrupt:
        print("\n[!] Interrompido pelo usuario.")

    _stop_event.set()
    mon.join(timeout=5)
    for t in threads:
        t.join(timeout=2)

    print("-" * 70)
    with _lock:
        total = len(_stats["tempos"])
        ok = _stats["ok"]
        err = _stats["err"]
        tempos = _stats["tempos"]

    print(f"\nRESULTADO FINAL - 10 minutos")
    print(f"  Total requisicoes : {total}")
    print(f"  Sucessos (2xx/4xx): {ok}")
    print(f"  Erros 5xx         : {err}")
    if tempos:
        media = sum(tempos) / len(tempos)
        maximo = max(tempos)
        p95 = sorted(tempos)[int(len(tempos) * 0.95)]
        p99 = sorted(tempos)[int(len(tempos) * 0.99)]
        print(f"  Tempo medio       : {media:.1f} ms")
        print(f"  Tempo maximo      : {maximo:.1f} ms")
        print(f"  P95               : {p95:.1f} ms")
        print(f"  P99               : {p99:.1f} ms")
        rps_total = total / DURACAO_SEGUNDOS
        print(f"  Throughput medio  : {rps_total:.1f} req/s")
        taxa_err = (err / total * 100) if total else 0
        print(f"  Taxa de erro 5xx  : {taxa_err:.2f}%")
    print(f"\nVeja metricas acumuladas: {BASE}/metrics")
    print("=" * 70)


if __name__ == "__main__":
    main()
