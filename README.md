# Repasse CarApp — Etapa 1: Modelo de Dados

Marketplace B2B para compra e venda de veículos de repasse com defeito declarado entre lojistas (PJ/CNPJ).

## Estrutura

```
database/schema.sql            Schema SQLite completo
database/seed.py               Seed com 10 veículos e 4 lojistas de exemplo
app/models.py                  Acesso a dados (sqlite3 puro, sem ORM)
app/business_rules.py          Validações e regras de negócio
tests/test_business_rules.py   Testes unitários
```

## Como rodar

```bash
# Dependência mínima
pip install werkzeug pytest

# Criar banco e popular com seed
python database/seed.py

# Rodar testes
python -m pytest tests/ -v
```

## Decisões de modelagem

### N:N entre veículo e selo em vez de campo fixo

A taxonomia tem 14 subtipos em 4 categorias e um veículo pode acumular selos de categorias distintas (ex: leilão judicial com dano estético). Um campo ENUM fixo forçaria colunas nullable múltiplas ou inviabilizaria combinações. A tabela `veiculo_selos` com `UNIQUE(veiculo_id, selo_id)` resolve isso com flexibilidade e integridade referencial, sem custo extra de leitura além de um JOIN.

### `campos_especificos` como JSON TEXT em vez de tabelas de extensão por categoria

**Trade-off considerado:** 4 tabelas separadas (`detalhes_leilao`, `detalhes_mecanico`, etc.) dariam tipagem nativa, mas adicionariam um JOIN extra por categoria a toda query de anúncio completo, e os campos específicos são sempre lidos/escritos em conjunto com o selo — nunca consultados individualmente em SQL. O JSON TEXT em `campos_obrigatorios` (schema de validação) + `campos_especificos` (instância) mantém a validação em `business_rules.py` sem sobrecarga estrutural. Aceitável no MVP; revisar se surgirem queries de busca por campo específico.

### Preços em centavos (INTEGER)

Evita erros de ponto flutuante acumulados em operações com percentuais (ex: desconto FIPE). Exibe-se dividindo por 100 na camada de apresentação.

### Status `rascunho` como estado inicial

Permite que o lojista monte o anúncio em etapas — adicionar selos, fazer upload de fotos — sem publicar prematuramente. A regra RN-02 garante que a transição para `ativo` só ocorre com ao menos 1 selo, e RN-03 exige foto para selos de defeito mecânico/estético. Sem `rascunho`, tudo precisaria ser enviado de uma vez, conflitando com o fluxo incremental de uploads.

### `senha_hash` com Werkzeug (pbkdf2:sha256)

Estrutura de tabela já pronta para autenticação via `check_password_hash`. Login funcional será implementado em etapa futura.
