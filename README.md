# CarApp Repasse

Marketplace B2B para compra e venda de veículos com defeito declarado entre lojistas (PJ/CNPJ). Cada anúncio exige pelo menos um **selo de defeito ou procedência**, garantindo transparência total na negociação.

---

## Sumário

- [Visão Geral](#visão-geral)
- [Tecnologias](#tecnologias)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Instalação e Execução](#instalação-e-execução)
- [Banco de Dados](#banco-de-dados)
- [API REST](#api-rest)
- [Interface Web](#interface-web)
- [Regras de Negócio](#regras-de-negócio)
- [Testes](#testes)
- [Decisões de Arquitetura](#decisões-de-arquitetura)

---

## Visão Geral

O CarApp Repasse conecta lojistas de veículos que desejam comprar ou vender carros com histórico — sinistros, defeitos mecânicos, estéticos, pendências documentais ou oriundos de leilão. O diferencial é a **obrigatoriedade de selos de defeito** em cada anúncio, com campos específicos e fotos vinculadas, eliminando surpresas na negociação.

**Fluxo principal:**

```
Lojista A cria anúncio → adiciona selos + fotos → publica
Lojista B encontra o anúncio → envia proposta com valor
Lojista A aceita → veículo vai para "em negociação"
Contato WhatsApp do comprador é liberado para o vendedor
Lojista A conclui a venda → status "vendido"
```

---

## Tecnologias

| Camada | Tecnologia |
|---|---|
| Backend | Python 3.12 + Flask |
| Banco de dados | SQLite 3 (sqlite3 puro, sem ORM) |
| Autenticação | Werkzeug sessions + `pbkdf2:sha256` |
| Frontend | Jinja2 templates + Bootstrap 5.3 + Bootstrap Icons |
| Testes | pytest + pytest-flask |

---

## Estrutura do Projeto

```
CarApp/
├── app/
│   ├── __init__.py          # Factory create_app(), filtros Jinja2
│   ├── db.py                # Conexão SQLite, init_db()
│   ├── session.py           # Decorator login_required, lojista_id_sessao()
│   ├── models.py            # CRUD: lojistas, veículos, selos, fotos, propostas
│   ├── business_rules.py    # Validações: CNPJ, status, publicação, proposta
│   └── routes/
│       ├── auth.py          # API JSON: /api/auth/* (registro, login, logout, me)
│       ├── veiculos.py      # API JSON: /api/veiculos/* (CRUD, selos, fotos)
│       ├── propostas.py     # API JSON: /api/propostas/*
│       └── web.py           # Blueprint HTML: todas as rotas da interface
├── database/
│   ├── schema.sql           # DDL completo (7 tabelas)
│   └── seed.py              # 4 lojistas, 14 selos, 10 veículos de exemplo
├── templates/
│   ├── base.html            # Layout com sidebar vertical
│   ├── auth/
│   │   ├── login.html       # Tela split-screen
│   │   └── cadastro.html    # Tela split-screen
│   ├── veiculos/
│   │   ├── listagem.html    # Cards + filtros
│   │   ├── detalhe.html     # Carousel + selos + proposta
│   │   ├── form_veiculo.html # Novo anúncio (fluxo único)
│   │   └── meus_anuncios.html
│   └── propostas/
│       └── painel.html      # Tabs Recebidas / Enviadas
├── static/
│   └── uploads/             # Fotos enviadas (ignoradas pelo git)
├── tests/
│   ├── test_business_rules.py  # 31 testes unitários
│   └── test_routes/
│       ├── conftest.py
│       ├── test_auth.py
│       ├── test_veiculos.py
│       └── test_propostas.py   # 53 testes de integração
├── config.py                # Config e TestConfig
├── run.py                   # Entrypoint Flask
└── .gitignore
```

---

## Instalação e Execução

### Pré-requisitos

- Python 3.10+
- pip

### 1. Clonar o repositório

```bash
git clone https://github.com/OscarSCarvalho/Repasse-car.git
cd Repasse-car
```

### 2. Criar ambiente virtual e instalar dependências

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

pip install flask werkzeug pytest pytest-flask
```

### 3. Inicializar o banco de dados

```bash
python -c "
from app import create_app
from app.db import init_db
app = create_app()
with app.app_context():
    init_db()
"
```

### 4. Popular com dados de exemplo

```bash
python database/seed.py
```

### 5. Rodar o servidor

```bash
python run.py
```

Acesse **http://127.0.0.1:5000**

### Credenciais do seed

Todos os lojistas usam a senha `Senha@123`:

| Lojista | E-mail |
|---|---|
| Pinheiro Multimarcas (SP) | `contato@pinheiro.com.br` |
| Auto Center Gomes (RJ) | `vendas@gomes.com.br` |
| Veículos Express (BH) | `compras@express.com.br` |
| Supercar Multimarcas (CWB) | `vendas@supercar.com.br` |

---

## Banco de Dados

### Diagrama de tabelas

```
lojistas
  └── veiculos (lojista_id)
        └── veiculo_selos (veiculo_id, selo_id) ──► selos_defeito
              └── fotos_veiculo (veiculo_id, veiculo_selo_id?)
        └── propostas (veiculo_id, lojista_comprador_id)

selos_defeito
  └── categorias_defeito (categoria_id)
```

### Tabelas principais

| Tabela | Descrição |
|---|---|
| `lojistas` | Cadastro de lojistas PJ com CNPJ, e-mail, cidade, WhatsApp |
| `veiculos` | Anúncios com status, preço em centavos, dados técnicos |
| `categorias_defeito` | 4 categorias: origem_leilao, defeito_mecanico, defeito_estetico, documentacao |
| `selos_defeito` | 14 selos com `campos_obrigatorios` (JSON) e flag `exige_foto` |
| `veiculo_selos` | N:N entre veículos e selos, com `campos_especificos` (JSON) |
| `fotos_veiculo` | Fotos gerais, de avaria ou laudo vinculadas ao veículo/selo |
| `propostas` | Ofertas entre lojistas com status e mensagem |

### Status do veículo

```
rascunho → ativo → em_negociacao → vendido
                ↘               ↘
               cancelado       cancelado
```

### Status da proposta

```
pendente → aceita
         → recusada
         → cancelada
```

---

## API REST

Todos os endpoints JSON estão prefixados com `/api`.

### Autenticação — `/api/auth`

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/api/auth/registro` | Cadastra novo lojista |
| `POST` | `/api/auth/login` | Autentica e inicia sessão |
| `POST` | `/api/auth/logout` | Encerra sessão |
| `GET` | `/api/auth/me` | Retorna dados do lojista logado |

**Exemplo — registro:**
```json
POST /api/auth/registro
{
  "nome_fantasia": "Minha Loja",
  "razao_social": "Minha Loja Ltda",
  "cnpj": "11222333000181",
  "email": "contato@minhaloja.com",
  "senha": "Senha@123",
  "cidade": "São Paulo",
  "uf": "SP"
}
```

### Veículos — `/api/veiculos`

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| `GET` | `/api/veiculos` | — | Lista anúncios ativos (com filtros) |
| `GET` | `/api/veiculos/<id>` | — | Detalhe com selos e fotos |
| `POST` | `/api/veiculos` | ✓ | Cria veículo em rascunho |
| `PATCH` | `/api/veiculos/<id>` | ✓ | Edita campos (só em rascunho) |
| `POST` | `/api/veiculos/<id>/publicar` | ✓ | Publica anúncio |
| `POST` | `/api/veiculos/<id>/cancelar` | ✓ | Cancela anúncio |
| `POST` | `/api/veiculos/<id>/selos` | ✓ | Adiciona selo ao veículo |
| `DELETE` | `/api/veiculos/<id>/selos/<selo_id>` | ✓ | Remove selo |
| `POST` | `/api/veiculos/<id>/fotos` | ✓ | Registra foto |
| `DELETE` | `/api/fotos/<foto_id>` | ✓ | Remove foto |
| `GET` | `/api/meus-anuncios` | ✓ | Lista anúncios do lojista logado |

**Filtros disponíveis em `GET /api/veiculos`:**

| Parâmetro | Tipo | Exemplo |
|---|---|---|
| `marca` | string | `?marca=toyota` |
| `cidade` | string | `?cidade=sao paulo` |
| `categoria_defeito` | string | `?categoria_defeito=defeito_mecanico` |
| `preco_min` | integer (centavos) | `?preco_min=2000000` |
| `preco_max` | integer (centavos) | `?preco_max=8000000` |

### Propostas — `/api/propostas`

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| `POST` | `/api/veiculos/<id>/propostas` | ✓ | Envia proposta |
| `PATCH` | `/api/propostas/<id>/status` | ✓ | Aceita, recusa ou cancela |
| `GET` | `/api/propostas/recebidas` | ✓ | Propostas nos meus anúncios |
| `GET` | `/api/propostas/enviadas` | ✓ | Propostas que enviei |

**Transições de status válidas:**

| Quem | Status permitido |
|---|---|
| Dono do anúncio | `aceita`, `recusada` |
| Comprador | `cancelada` |

---

## Interface Web

### Rotas HTML

| Rota | Descrição |
|---|---|
| `/` | Listagem pública com filtros e cards |
| `/veiculo/<id>` | Detalhe com galeria, selos e proposta |
| `/novo-anuncio` | Formulário único: dados + selos + fotos |
| `/meus-anuncios` | Dashboard do lojista com filtro de status |
| `/propostas` | Painel com tabs Recebidas/Enviadas |
| `/cadastro` | Criação de conta (layout split-screen) |
| `/login` | Autenticação (layout split-screen) |

### Design System

- **Cores primárias:** `#0d1b3e` (navy), `#4ea8ff` (accent), `#f0f2f7` (background)
- **Sidebar:** fixa à esquerda, 240px, com seções contextuais por estado de autenticação
- **Cards de veículo:** foto + preço em destaque + especificações + badge de status
- **Badges de status:** cores semânticas (verde=ativo, azul=negociação, vermelho=cancelado)
- **Responsivo:** sidebar recolhe em mobile com botão hambúrguer e backdrop

---

## Regras de Negócio

| Código | Regra |
|---|---|
| RN-01 | CNPJ validado com algoritmo módulo-11 |
| RN-02 | Veículo precisa de ao menos 1 selo para ser publicado |
| RN-03 | Selos das categorias `defeito_mecanico` e `defeito_estetico` exigem foto vinculada |
| RN-04 | Transições de status seguem a máquina de estados — transições inválidas retornam 409 |
| RN-05 | Lojista não pode enviar proposta no próprio anúncio |
| RN-06 | Propostas só podem ser enviadas para veículos `ativo` ou `em_negociacao` |
| RN-07 | Somente o dono do anúncio pode aceitar ou recusar propostas |
| RN-08 | Somente o comprador pode cancelar a própria proposta |
| RN-09 | Proposta já aceita/recusada/cancelada não pode ser alterada |
| RN-10 | Ao aceitar uma proposta, o veículo passa automaticamente para `em_negociacao` |

---

## Testes

```bash
# Rodar todos os testes
python -m pytest tests/ -v

# Apenas testes unitários
python -m pytest tests/test_business_rules.py -v

# Apenas testes de rotas
python -m pytest tests/test_routes/ -v
```

**Cobertura atual: 84 testes — 100% passando**

| Módulo | Testes |
|---|---|
| `test_business_rules.py` | 31 — CNPJ, transições de status, publicação, criação de proposta |
| `test_auth.py` | 13 — Registro, login, logout, /me |
| `test_veiculos.py` | 27 — CRUD, selos, fotos, meus anúncios, filtros |
| `test_propostas.py` | 13 — Criar, aceitar, recusar, cancelar, listagem |

Cada teste usa banco SQLite isolado via `tmp_path` — sem estado compartilhado entre testes.

---

## Decisões de Arquitetura

### N:N entre veículo e selo

Um veículo pode ter múltiplos selos de categorias distintas (ex: leilão judicial + dano estético). A tabela `veiculo_selos` com `UNIQUE(veiculo_id, selo_id)` resolve isso com flexibilidade e integridade referencial, em vez de colunas nullable múltiplas.

### `campos_especificos` como JSON TEXT

Cada selo tem campos obrigatórios diferentes. 4 tabelas separadas por categoria adicionariam um JOIN extra por query e os campos são sempre lidos em conjunto com o selo. O JSON TEXT em `campos_obrigatorios` (schema) + `campos_especificos` (instância) mantém a validação em `business_rules.py` sem sobrecarga estrutural.

### Preços em centavos (INTEGER)

Evita erros de ponto flutuante em operações com percentuais (ex: desconto vs. FIPE). Convertidos para exibição com o filtro Jinja2 `| brl`.

### SQLite puro sem ORM

Adequado ao volume do MVP. Permite controle total do SQL, sem camada de abstração desnecessária. A função `get_db()` gerencia a conexão por request via Flask `g`.

### Blueprints separados para JSON e HTML

Os blueprints `auth`, `veiculos` e `propostas` servem JSON com prefixo `/api`. O blueprint `web` serve HTML sem prefixo. Isso evita conflito de rotas (ex: `GET /veiculos` API vs. `GET /` listagem web) e permite que a API seja consumida futuramente por um frontend desacoplado.

### Status `rascunho` como estado inicial

Permite que o lojista monte o anúncio em etapas (dados → selos → fotos) sem publicar prematuramente. A publicação exige pelo menos 1 selo (RN-02) e foto para selos que exigem evidência visual (RN-03).
