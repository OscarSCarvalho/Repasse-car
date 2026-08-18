import re
import sqlite3


# ── CNPJ ──────────────────────────────────────────────────────────────────────

def validar_cnpj(cnpj: str) -> bool:
    cnpj = re.sub(r'\D', '', cnpj)
    if len(cnpj) != 14 or len(set(cnpj)) == 1:
        return False

    def _digito(digits, weights):
        total = sum(int(d) * w for d, w in zip(digits, weights))
        remainder = total % 11
        return 0 if remainder < 2 else 11 - remainder

    weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    weights2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]

    return (
        int(cnpj[12]) == _digito(cnpj[:12], weights1) and
        int(cnpj[13]) == _digito(cnpj[:13], weights2)
    )


# ── Transição de status ────────────────────────────────────────────────────────

TRANSICOES_VALIDAS: dict[str, set] = {
    'rascunho':      {'ativo', 'cancelado'},
    'ativo':         {'em_negociacao', 'cancelado'},
    'em_negociacao': {'vendido', 'ativo', 'cancelado'},
    'vendido':       set(),
    'cancelado':     set(),
}


def validar_transicao_status(status_atual: str, novo_status: str) -> None:
    if status_atual not in TRANSICOES_VALIDAS:
        raise ValueError(f"Status desconhecido: '{status_atual}'.")
    permitidas = TRANSICOES_VALIDAS[status_atual]
    if novo_status not in permitidas:
        destinos = ', '.join(f"'{s}'" for s in sorted(permitidas)) or 'nenhuma'
        raise ValueError(
            f"Transição inválida: '{status_atual}' → '{novo_status}'. "
            f"Destinos permitidos: {destinos}."
        )


# ── Publicação ─────────────────────────────────────────────────────────────────

_CATEGORIAS_EXIGEM_FOTO = {'defeito_estetico', 'defeito_mecanico'}


def validar_publicacao_veiculo(conn: sqlite3.Connection, veiculo_id: int) -> None:
    selos = conn.execute(
        """
        SELECT vs.id, sd.nome AS nome_selo, cd.nome AS categoria
          FROM veiculo_selos vs
          JOIN selos_defeito sd       ON sd.id = vs.selo_id
          JOIN categorias_defeito cd  ON cd.id = sd.categoria_id
         WHERE vs.veiculo_id = ?
        """,
        (veiculo_id,),
    ).fetchall()

    if not selos:
        raise ValueError(
            "Veículo não pode ser publicado: nenhum selo de defeito cadastrado."
        )

    for selo in selos:
        if selo['categoria'] not in _CATEGORIAS_EXIGEM_FOTO:
            continue
        foto = conn.execute(
            "SELECT 1 FROM fotos_veiculo WHERE veiculo_selo_id = ? LIMIT 1",
            (selo['id'],),
        ).fetchone()
        if not foto:
            raise ValueError(
                f"Selo '{selo['nome_selo']}' (categoria: {selo['categoria']}) "
                f"exige pelo menos 1 foto vinculada."
            )


# ── Propostas ──────────────────────────────────────────────────────────────────

_STATUS_ANUNCIO_FECHADO = {'vendido', 'cancelado'}


def validar_criacao_proposta(
    conn: sqlite3.Connection, veiculo_id: int, lojista_comprador_id: int
) -> None:
    veiculo = conn.execute(
        "SELECT lojista_id, status FROM veiculos WHERE id = ?", (veiculo_id,)
    ).fetchone()

    if veiculo is None:
        raise ValueError(f"Veículo {veiculo_id} não encontrado.")

    if veiculo['lojista_id'] == lojista_comprador_id:
        raise ValueError("Lojista não pode propor compra no próprio anúncio.")

    if veiculo['status'] in _STATUS_ANUNCIO_FECHADO:
        raise ValueError(
            f"Proposta não permitida: anúncio está '{veiculo['status']}'."
        )
