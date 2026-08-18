# CONTEXT.md — Repasse / CarApp

## Identificação
- **Cliente:** Repasse
- **Projeto:** CarApp
- **Fase atual:** Etapa 1 — Modelo de Dados e Regras de Negócio

## Análise de Demanda (Fase 0)

### Problema de Negócio
Marketplace B2B onde lojistas de veículos (CNPJ) compram e vendem entre si carros de repasse com defeito declarado — leilão, sinistro, mecânico ou estético. O diferencial é a transparência estruturada sobre o defeito: cada anúncio deixa claro, com dados e fotos, exatamente qual é o problema do veículo.

### Natureza Técnica
- Aplicação web CRUD com regras de negócio claras
- Upload de mídia (etapa futura)
- Autenticação por sessão (etapa futura)
- Escala inicial pequena (MVP), crescimento gradual

## Justificativa da Stack

| Componente | Escolha | Justificativa |
|---|---|---|
| Backend | Flask | Pedido explícito do cliente; leve, sem boilerplate, ideal para MVP incremental |
| Banco | SQLite3 puro (sem SQLAlchemy) | Pedido explícito; elimina ORM overhead no MVP, facilita deploy sem servidor de banco |
| Autenticação | Werkzeug (sessão) | Padrão Flask, sem dependências externas pesadas |
| Testes | unittest + pytest | Sem dependências extras além de pytest para execução |

## Restrições do Cliente
- Stack: Flask + sqlite3 puro, sem SQLAlchemy ou ORM
- Autenticação: sessão com Werkzeug
- Nomenclatura: português, snake_case
- Sem dependências pesadas — soluções minimalistas e pragmáticas

## Padrão Arquitetural (Clean Architecture adaptada ao Flask)
- `/database` — schema, migrations, seed
- `/app` — lógica de aplicação (models + business_rules); sem dependência de framework
- `/tests` — testes unitários 100% sem banco de dados externo (in-memory SQLite)
- Rotas Flask e templates serão adicionados em etapas futuras sem alterar a camada de domínio

## Etapas Planejadas
1. **Etapa 1** (concluída): Modelo de dados + regras de negócio + testes
2. **Etapa 2+**: Rotas Flask, autenticação por sessão, templates HTML, upload real de fotos
