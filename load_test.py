"""
Teste de carga real contra localhost:5000
Gera tráfego variado para visualização no Grafana.
Execute: python load_test.py
"""
import time
import random
import threading
import urllib.request
import urllib.error
import json as _json

BASE = "http://localhost:5000"
RESULTADOS = {"ok": 0, "erro": 0, "tempos": []}
_lock = threading.Lock()


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
            body = resp.read()
            ms = (time.perf_counter() - t0) * 1000
            with _lock:
                RESULTADOS["ok"] += 1
                RESULTADOS["tempos"].append(ms)
            return resp.status, body, dict(resp.headers)
    except urllib.error.HTTPError as e:
        ms = (time.perf_counter() - t0) * 1000
        body = e.read()
        with _lock:
            if e.code >= 500:
                RESULTADOS["erro"] += 1
            else:
                RESULTADOS["ok"] += 1
            RESULTADOS["tempos"].append(ms)
        return e.code, body, dict(e.headers)
    except Exception as e:
        with _lock:
            RESULTADOS["erro"] += 1
        return 0, b"", {}


def _get_session_cookie(headers):
    for k, v in headers.items():
        if k.lower() == "set-cookie" and "session=" in v:
            for part in v.split(";"):
                if part.strip().startswith("session="):
                    return {"session": part.strip()[len("session="):]}
    return {}


def cenario_publico():
    """Leitura pública — listagem e detalhe."""
    _req("GET", "/api/veiculos")
    _req("GET", "/api/veiculos?marca=Honda")
    _req("GET", "/api/veiculos?preco_min=1000000&preco_max=50000000")
    _req("GET", "/api/veiculos?cidade=SP")
    _req("GET", "/api/veiculos/1")
    _req("GET", "/api/veiculos/2")
    _req("GET", "/api/veiculos/99999")  # 404 intencional
    _req("GET", "/")
    _req("GET", "/?marca=Toyota")


def cenario_auth(idx):
    """Registra, loga, cria veículo, publica e faz logout."""
    from app.business_rules import validar_cnpj
    # CNPJs válidos pré-calculados para o load test
    cnpjs = [
        "11222333000181", "22333444000181", "33444555000181",
        "44555666000181", "55666777000181", "66777888000181",
    ]
    cnpj = cnpjs[idx % len(cnpjs)]
    email = f"load{idx}@teste.com"

    status, body, hdrs = _req("POST", "/api/auth/registro", {
        "nome_fantasia": f"Load Loja {idx}", "razao_social": f"Load {idx} LTDA",
        "cnpj": cnpj, "email": email, "senha": "Senha@123",
        "cidade": "São Paulo", "uf": "SP",
    })
    cookie = _get_session_cookie(hdrs)

    if not cookie:
        status, body, hdrs = _req("POST", "/api/auth/login",
                                  {"email": email, "senha": "Senha@123"})
        cookie = _get_session_cookie(hdrs)

    if not cookie:
        return

    _req("GET", "/api/auth/me", cookies=cookie)
    _req("GET", "/api/meus-anuncios", cookies=cookie)
    _req("GET", "/api/propostas/recebidas", cookies=cookie)
    _req("GET", "/api/propostas/enviadas", cookies=cookie)
    _req("POST", "/api/auth/logout", cookies=cookie)


def cenario_erros():
    """Gera erros 401 e 404 intencionais para aparecerem no Grafana."""
    _req("GET", "/api/auth/me")            # 401
    _req("POST", "/api/veiculos", {})      # 401
    _req("GET", "/api/veiculos/999999")    # 404
    _req("GET", "/rota-inexistente")       # 404


def worker(n):
    for _ in range(n):
        cenario_publico()
        cenario_erros()
        time.sleep(random.uniform(0.05, 0.2))


def main():
    ROUNDS = 5
    THREADS = 4
    total_req_por_round = (9 + 4) * THREADS  # aprox

    print(f"CarApp Load Test — {BASE}")
    print(f"Threads: {THREADS} | Rounds por thread: {ROUNDS}")
    print(f"Acompanhe em: {BASE}/metrics  |  Grafana: http://localhost:3000")
    print("=" * 55)

    for round_n in range(1, ROUNDS + 1):
        print(f"\n[Round {round_n}/{ROUNDS}]", end=" ", flush=True)
        threads = []

        # Cenários públicos em paralelo
        for _ in range(THREADS):
            t = threading.Thread(target=worker, args=(3,))
            threads.append(t)
            t.start()

        # Cenário auth sequencial por índice
        for idx in range(THREADS):
            cenario_auth(round_n * 10 + idx)

        for t in threads:
            t.join()

        with _lock:
            ok = RESULTADOS["ok"]
            err = RESULTADOS["erro"]
            tempos = RESULTADOS["tempos"]
            media = sum(tempos) / len(tempos) if tempos else 0
            p95 = sorted(tempos)[int(len(tempos) * 0.95)] if tempos else 0

        print(f"OK={ok} ERR={err} avg={media:.1f}ms p95={p95:.1f}ms")
        time.sleep(1)

    print("\n" + "=" * 55)
    with _lock:
        tempos = RESULTADOS["tempos"]
        if tempos:
            print(f"Total requisições : {len(tempos)}")
            print(f"Sucessos          : {RESULTADOS['ok']}")
            print(f"Erros 5xx         : {RESULTADOS['erro']}")
            print(f"Tempo médio       : {sum(tempos)/len(tempos):.1f} ms")
            print(f"Tempo máximo      : {max(tempos):.1f} ms")
            print(f"P95               : {sorted(tempos)[int(len(tempos)*0.95)]:.1f} ms")
    print(f"\nVeja métricas finais: {BASE}/metrics")


if __name__ == "__main__":
    main()
