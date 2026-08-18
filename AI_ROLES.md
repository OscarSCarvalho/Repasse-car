# AI_ROLES.md — Repasse / CarApp

## Squad Alpha — Product & Architecture
- **Agent Software Architect:** Decisão de stack (Flask + sqlite3 puro), guardião da separação de camadas. Autoriza avanço de etapa.
- **Agent Product Manager:** Validação de escopo por etapa; garante que regras de negócio no `business_rules.py` refletem a `SPEC`.

## Squad Beta — Core Engineering
- **Agent Senior Backend Engineer:** Implementação de `models.py`, `business_rules.py`, rotas Flask (etapas futuras). Segue sqlite3 puro sem ORM.
- **Agent Senior Frontend Engineer:** Templates HTML/CSS e interações JS (etapas futuras).

## Squad Gamma — Quality & Assurance
- **Agent Senior SDET:** `tests/test_business_rules.py`; cobertura de casos de erro; validação contra regras da SPEC.

## Squad Delta — Platform & DevOps
- **Agent Senior DevOps/SRE:** Containerização e deploy (etapas futuras).

## Convenções do Projeto
- Nomenclatura: português, snake_case
- Banco: SQLite3 puro — proibido introduzir SQLAlchemy ou outro ORM
- Testes: sqlite3 in-memory (`:memory:`), schema carregado via `schema.sql`
- Preços: sempre em centavos (INTEGER)
- Senha: `werkzeug.security.generate_password_hash` / `check_password_hash`
