import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

DB_PATH = str(Path(__file__).parent.parent / "database" / "repasse.db")


@contextmanager
def get_db(db_path: str = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _row(row) -> Optional[dict]:
    return dict(row) if row else None


# ── Lojistas ──────────────────────────────────────────────────────────────────

def criar_lojista(conn: sqlite3.Connection, dados: dict) -> int:
    cur = conn.execute(
        """
        INSERT INTO lojistas
            (nome_fantasia, razao_social, cnpj, email, senha_hash,
             telefone_whatsapp, cidade, uf)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            dados['nome_fantasia'], dados['razao_social'], dados['cnpj'],
            dados['email'], dados['senha_hash'],
            dados.get('telefone_whatsapp'), dados['cidade'], dados['uf'],
        ),
    )
    return cur.lastrowid


def buscar_lojista(conn: sqlite3.Connection, lojista_id: int) -> Optional[dict]:
    return _row(conn.execute(
        "SELECT * FROM lojistas WHERE id = ?", (lojista_id,)
    ).fetchone())


def buscar_lojista_por_cnpj(conn: sqlite3.Connection, cnpj: str) -> Optional[dict]:
    return _row(conn.execute(
        "SELECT * FROM lojistas WHERE cnpj = ?", (cnpj,)
    ).fetchone())


def buscar_lojista_por_email(conn: sqlite3.Connection, email: str) -> Optional[dict]:
    return _row(conn.execute(
        "SELECT * FROM lojistas WHERE email = ?", (email,)
    ).fetchone())


# ── Veículos ──────────────────────────────────────────────────────────────────

def criar_veiculo(conn: sqlite3.Connection, dados: dict) -> int:
    cur = conn.execute(
        """
        INSERT INTO veiculos
            (lojista_id, marca, modelo, ano_fabricacao, ano_modelo,
             versao, cor, kilometragem, cambio, combustivel,
             placa, preco, codigo_fipe, valor_fipe, descricao)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            dados['lojista_id'], dados['marca'], dados['modelo'],
            dados['ano_fabricacao'], dados['ano_modelo'],
            dados.get('versao'), dados.get('cor'), dados['kilometragem'],
            dados['cambio'], dados['combustivel'], dados.get('placa'),
            dados['preco'], dados.get('codigo_fipe'), dados.get('valor_fipe'),
            dados.get('descricao'),
        ),
    )
    return cur.lastrowid


def buscar_veiculo(conn: sqlite3.Connection, veiculo_id: int) -> Optional[dict]:
    return _row(conn.execute(
        "SELECT * FROM veiculos WHERE id = ?", (veiculo_id,)
    ).fetchone())


def listar_veiculos(
    conn: sqlite3.Connection,
    status: str = None,
    lojista_id: int = None,
) -> list[dict]:
    query = "SELECT * FROM veiculos WHERE 1=1"
    params: list = []
    if status:
        query += " AND status = ?"
        params.append(status)
    if lojista_id:
        query += " AND lojista_id = ?"
        params.append(lojista_id)
    query += " ORDER BY criado_em DESC"
    return [dict(r) for r in conn.execute(query, params).fetchall()]


def atualizar_status_veiculo(
    conn: sqlite3.Connection, veiculo_id: int, novo_status: str
) -> None:
    conn.execute(
        "UPDATE veiculos SET status = ?, atualizado_em = CURRENT_TIMESTAMP WHERE id = ?",
        (novo_status, veiculo_id),
    )


# ── Selos ─────────────────────────────────────────────────────────────────────

def adicionar_selo_veiculo(
    conn: sqlite3.Connection,
    veiculo_id: int,
    selo_id: int,
    campos_especificos: dict = None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO veiculo_selos (veiculo_id, selo_id, campos_especificos)
        VALUES (?, ?, ?)
        """,
        (veiculo_id, selo_id, json.dumps(campos_especificos or {})),
    )
    return cur.lastrowid


def remover_selo_veiculo(
    conn: sqlite3.Connection, veiculo_id: int, selo_id: int
) -> None:
    conn.execute(
        "DELETE FROM veiculo_selos WHERE veiculo_id = ? AND selo_id = ?",
        (veiculo_id, selo_id),
    )


def listar_selos_veiculo(conn: sqlite3.Connection, veiculo_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT vs.*, sd.nome AS nome_selo, cd.nome AS categoria
          FROM veiculo_selos vs
          JOIN selos_defeito sd       ON sd.id = vs.selo_id
          JOIN categorias_defeito cd  ON cd.id = sd.categoria_id
         WHERE vs.veiculo_id = ?
        """,
        (veiculo_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def listar_selos_disponiveis(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT sd.*, cd.nome AS categoria
          FROM selos_defeito sd
          JOIN categorias_defeito cd ON cd.id = sd.categoria_id
         ORDER BY cd.id, sd.id
        """
    ).fetchall()
    return [dict(r) for r in rows]


# ── Fotos ─────────────────────────────────────────────────────────────────────

def adicionar_foto(conn: sqlite3.Connection, dados: dict) -> int:
    cur = conn.execute(
        """
        INSERT INTO fotos_veiculo
            (veiculo_id, veiculo_selo_id, tipo, caminho, descricao, ordem)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            dados['veiculo_id'], dados.get('veiculo_selo_id'),
            dados['tipo'], dados['caminho'],
            dados.get('descricao'), dados.get('ordem', 0),
        ),
    )
    return cur.lastrowid


def listar_fotos_veiculo(conn: sqlite3.Connection, veiculo_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM fotos_veiculo WHERE veiculo_id = ? ORDER BY ordem, id",
        (veiculo_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ── Propostas ─────────────────────────────────────────────────────────────────

def criar_proposta(conn: sqlite3.Connection, dados: dict) -> int:
    cur = conn.execute(
        """
        INSERT INTO propostas (veiculo_id, lojista_comprador_id, valor, mensagem)
        VALUES (?, ?, ?, ?)
        """,
        (
            dados['veiculo_id'], dados['lojista_comprador_id'],
            dados['valor'], dados.get('mensagem'),
        ),
    )
    return cur.lastrowid


def atualizar_status_proposta(
    conn: sqlite3.Connection, proposta_id: int, novo_status: str
) -> None:
    conn.execute(
        "UPDATE propostas SET status = ?, atualizado_em = CURRENT_TIMESTAMP WHERE id = ?",
        (novo_status, proposta_id),
    )


def buscar_proposta(conn: sqlite3.Connection, proposta_id: int) -> Optional[dict]:
    return _row(conn.execute(
        "SELECT * FROM propostas WHERE id = ?", (proposta_id,)
    ).fetchone())


def listar_propostas_veiculo(conn: sqlite3.Connection, veiculo_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM propostas WHERE veiculo_id = ? ORDER BY criado_em DESC",
        (veiculo_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ── Pesquisa pública ──────────────────────────────────────────────────────────

def pesquisar_veiculos(
    conn: sqlite3.Connection,
    status: str = 'ativo',
    marca: str = None,
    cidade_lojista: str = None,
    categoria_defeito: str = None,
    preco_min: int = None,
    preco_max: int = None,
) -> list[dict]:
    query = """
        SELECT DISTINCT v.*
          FROM veiculos v
          JOIN lojistas l ON l.id = v.lojista_id
         WHERE 1=1
    """
    params: list = []

    if status:
        query += " AND v.status = ?"
        params.append(status)

    if marca:
        query += " AND lower(v.marca) LIKE ?"
        params.append(f'%{marca.lower()}%')

    if cidade_lojista:
        query += " AND lower(l.cidade) LIKE ?"
        params.append(f'%{cidade_lojista.lower()}%')

    if categoria_defeito:
        query += """
            AND EXISTS (
                SELECT 1 FROM veiculo_selos vs
                  JOIN selos_defeito sd      ON sd.id = vs.selo_id
                  JOIN categorias_defeito cd ON cd.id = sd.categoria_id
                 WHERE vs.veiculo_id = v.id AND cd.nome = ?
            )
        """
        params.append(categoria_defeito)

    if preco_min is not None:
        query += " AND v.preco >= ?"
        params.append(preco_min)

    if preco_max is not None:
        query += " AND v.preco <= ?"
        params.append(preco_max)

    query += " ORDER BY v.criado_em DESC"
    return [dict(r) for r in conn.execute(query, params).fetchall()]
