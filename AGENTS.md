# HookLog: contexto para agentes de código

Este arquivo é lido em toda sessão. Ele diz **o que o projeto é, onde está a especificação e quais regras nunca podem ser quebradas**.

## O que é

HookLog é um sistema de monitoramento de encomendas, feito como projeto final da disciplina de Sistemas Distribuídos (tema: API REST com FastAPI e Webhooks). Apresentação em **12/12/2026**.

O usuário (`USER`) faz login, cadastra as encomendas que está esperando e acompanha o andamento por três abas: **Não encaminhadas**, **A caminho** e **Entregues**. Um segundo serviço, que **simula uma transportadora**, muda o status da remessa e avisa o sistema de monitoramento por **webhook assinado com HMAC**.

### Os dois tipos de usuário (e só eles)

| Papel | Quem é | O que pode |
|---|---|---|
| `USER` | Cadastra-se pela tela de registro e fica salvo no banco | **CRUD das próprias encomendas** (criar, ler, editar, excluir). Nada além disso |
| `ADMIN` | Usuário **mockado**, definido no arquivo `.env`; **não existe no banco** | **Ver as encomendas de todos os usuários** (somente leitura) e **único acesso à tela da transportadora**, por login |

**O sistema não executa sem um ADMIN configurado.** `ADMIN_EMAIL` e `ADMIN_SENHA` são obrigatórios nos dois serviços; se faltarem ou forem inválidos, o processo encerra na inicialização com uma mensagem clara. O `docker-compose.yml` também recusa subir sem eles.

### Peças

| Pasta | Papel | Tecnologia |
|---|---|---|
| `monitoramento/` | API principal: login, controle de acesso, encomendas, recebe webhooks | FastAPI + PostgreSQL |
| `transportadora/` | Simulador: remessas, status, envio de webhooks, tela do ADMIN | FastAPI + PostgreSQL (outro banco) |
| `frontend/` | Interface do usuário e do ADMIN (lista de todas as encomendas) | React + Vite + TypeScript + react-bootstrap |
| `gateway/` | Porta de entrada única | nginx |

## Fonte da verdade (leia antes de codar)

1. `docs/spec.md`: requisitos, regras de negócio, máquina de estados, fluxos, variáveis de ambiente.
2. `docs/api.md`: rotas, corpos, status codes, contrato do webhook e da assinatura.
3. `docs/data-model.md`: tabelas, colunas, restrições e transações.
4. `docs/tasks.md`: as fatias de trabalho, na ordem, com critérios de aceite.

Se algo estiver ambíguo ou parecer contraditório entre os documentos, **pare e pergunte**. Não invente contrato e não altere os documentos sem pedir.

## Fluxo de trabalho

1. Faça **uma tarefa de `docs/tasks.md` por sessão**. Não antecipe tarefas seguintes.
2. **Planeje antes de codar**: liste os arquivos que vai criar ou alterar e espere confirmação.
3. Tarefas marcadas **(TDD)**: escreva os testes primeiro, rode e veja falhar, mostre os testes e espere minha revisão, depois implemente. Siga as **Regras para testes**.
4. Rode testes e lint do serviço afetado antes de encerrar.
5. Encerre com um resumo curto: o que foi feito, o que ficou pendente e qualquer decisão que você precisou tomar.
6. Um commit por tarefa, no formato `feat(monitoramento): T04 segurança e autenticação`.

## Idioma dos nomes (regra do projeto)

**Tudo o que nós escrevemos tem nome em português**: tabelas, colunas, campos JSON, classes, métodos, funções, variáveis, parâmetros, constantes, arquivos de módulo, rotas, cabeçalhos, códigos de erro, variáveis de ambiente, componentes e funções do frontend, e nomes de testes. Comentários, docstrings e mensagens também em português.

Exemplos: `gerar_hash_senha`, `criar_token_acesso`, `obter_usuario_atual`, `class Encomenda`, `codigo_rastreio`, `ServicoEncomenda`, `processar_pendentes`, `test_login_com_senha_errada_retorna_401`.

**Exceções (permanecem em inglês porque são impostas por ferramentas ou protocolos):**

- Nomes de frameworks e bibliotecas: `Depends`, `APIRouter`, `BaseModel`, `Mapped`, `mapped_column`, `lifespan`, `AsyncSession`, `AsyncClient`, `fixture`, e arquivos como `main.py`, `conftest.py`, `pyproject.toml`.
- Prefixos de convenção: `test_` (pytest) e `use` (hooks do React, como `useEncomendas`).
- Campos do protocolo OAuth2: o formulário de login usa `username` e `password`, e a resposta usa `access_token` e `token_type` (o botão *Authorize* do Swagger depende disso).
- Rotas de infraestrutura: `/health` e `/docs`.
- Nomes das **pastas de camada**: `core/`, `api/`, `schemas/`, `services/`, `repositories/`, `models/`, `clients/`, `workers/`.
- Termos técnicos sem tradução usual: `webhook`, `token`, `JWT`, `HMAC`, `backoff`, `payload` (nos comentários).

## Stack e versões

| Item | Escolha |
|---|---|
| Python | 3.12, gerenciado com **uv** (um ambiente `.venv` por serviço) |
| Web | FastAPI + Uvicorn, **tudo assíncrono**: endpoints e dependências `async def` |
| Validação | Pydantic v2 + pydantic-settings |
| ORM | SQLAlchemy **2.0 assíncrono** (`create_async_engine`, `AsyncSession`, estilo `select()`, `Mapped[]`, `mapped_column`) |
| Banco | PostgreSQL 16, driver assíncrono **`asyncpg`** (URL `postgresql+asyncpg://...`) |
| Migrações | Alembic com o template **async** (`alembic init -t async`), nos dois serviços |
| HTTP client | httpx **`AsyncClient`** |
| Hash de senha | `argon2-cffi` |
| JWT | `PyJWT` (HS256) |
| Testes | pytest + `pytest-asyncio` (`asyncio_mode = "auto"`) + `httpx.AsyncClient` com `ASGITransport` |
| Lint e formato | ruff (line-length 100) |
| Frontend | Node 22 LTS, Vite, React, TypeScript (strict), react-bootstrap + Bootstrap 5, React Router, TanStack Query |
| Infra | Docker Compose, nginx |

Instale dependências com `uv add` (o `uv.lock` trava as versões). **Não adicione dependências fora desta lista sem justificar.** Se uma API mudou entre versões, consulte a documentação da versão instalada, não a memória.

## Estrutura de pastas

```
hooklog/
├── AGENTS.md
├── README.md
├── docker-compose.yml
├── docker-compose.override.yml      # só dev: publica as portas dos bancos e dos serviços
├── .env.example                     # o .env real fica fora do git
├── docs/                            # spec.md, api.md, data-model.md, tasks.md
├── scripts/                         # e2e.py
├── gateway/                         # Dockerfile (build do React + nginx) e nginx.conf
├── frontend/
│   ├── public/                      # logos e favicon (SVG)
│   └── src/
│       ├── api/                     # cliente HTTP (base /api) e chamadas
│       ├── auth/                    # ContextoAutenticacao, RotaProtegida, RotaAdmin
│       ├── pages/                   # PaginaLogin, PaginaRegistro, PaginaEncomendas,
│       │                            # PaginaDetalheEncomenda, PaginaAdmin
│       ├── components/              # AbasEncomendas, ModalEncomenda, SeloStatus
│       ├── hooks/                   # useEncomendas (TanStack Query, polling de 5 s)
│       ├── types/
│       └── utils/                   # datas (UTC -> Brasília), rótulos de status
├── monitoramento/
│   ├── pyproject.toml, uv.lock, alembic.ini, Dockerfile
│   ├── alembic/versions/
│   ├── app/
│   │   ├── main.py                  # app + lifespan (inicia a rotina de registro pendente)
│   │   ├── core/                    # configuracao.py, banco_dados.py, seguranca.py,
│   │   │                            # dependencias.py, erros.py
│   │   ├── api/                     # autenticacao.py, encomendas.py, admin.py,
│   │   │                            # webhooks.py, saude.py
│   │   ├── schemas/                 # usuario.py, encomenda.py, webhook.py
│   │   ├── services/                # servico_autenticacao.py, servico_encomenda.py,
│   │   │                            # servico_webhook.py, maquina_de_estados.py,
│   │   │                            # verificador_hmac.py
│   │   ├── repositories/            # repositorio_usuario.py, repositorio_encomenda.py,
│   │   │                            # repositorio_evento.py
│   │   ├── models/                  # usuario.py, encomenda.py, historico_status.py,
│   │   │                            # evento_processado.py
│   │   ├── clients/                 # cliente_transportadora.py
│   │   └── workers/                 # registro_pendente.py
│   └── tests/{unit,integration}/
└── transportadora/
    ├── pyproject.toml, uv.lock, alembic.ini, Dockerfile
    ├── alembic/versions/
    ├── app/
    │   ├── main.py                  # app + lifespan (inicia a rotina de webhooks) + StaticFiles
    │   ├── core/                    # configuracao.py, banco_dados.py, seguranca.py,
    │   │                            # dependencias.py, erros.py, assinador_hmac.py
    │   ├── api/                     # autenticacao.py, remessas.py, logs_webhook.py, saude.py
    │   ├── schemas/
    │   ├── services/                # servico_remessa.py, maquina_de_estados.py
    │   ├── repositories/            # repositorio_remessa.py, repositorio_evento_webhook.py
    │   ├── models/                  # remessa.py, evento_webhook.py, tentativa_webhook.py
    │   ├── workers/                 # enviador_webhook.py (envia um evento),
    │   │                            # despachante_webhook.py (laço)
    │   └── static/                  # index.html + app.js (tela do ADMIN)
    └── tests/{unit,integration}/
```

## Comandos

Sempre dentro da pasta do serviço (cada um tem o seu `.venv`). Antes de tudo, crie o `.env` a partir do `.env.example` e **preencha `ADMIN_EMAIL` e `ADMIN_SENHA`** (sem eles nada sobe).

```bash
# bancos (a partir da raiz)
docker compose up -d monitoramento-db transportadora-db

# monitoramento (porta 8000)
cd monitoramento && uv sync
cd monitoramento && uv run alembic upgrade head
cd monitoramento && uv run uvicorn app.main:app --reload --port 8000
cd monitoramento && uv run pytest
cd monitoramento && uv run ruff check . && uv run ruff format .

# transportadora (porta 8001): mesmos comandos, com --port 8001

# frontend (porta 5173; o Vite faz proxy de /api para o monitoramento)
cd frontend && npm install && npm run dev

# tudo em containers (gateway em http://localhost:8080)
docker compose up --build
```

**Nunca rode `docker compose down -v`** (apaga os volumes e todos os dados dos bancos).

## Concorrência e código assíncrono (regras)

O sistema é **concorrente**: um único processo atende várias requisições ao mesmo tempo, usando **corrotinas** (`async def`) sobre o laço de eventos do `asyncio`. Regras:

1. **Todo endpoint e toda dependência do FastAPI é `async def`.**
2. **Toda E/S é assíncrona**: banco (`AsyncSession` + `asyncpg`) e HTTP (`httpx.AsyncClient`). Repositories e services que fazem E/S são `async def` e são chamados com `await`.
3. **Proibido bloquear o laço de eventos**: nada de `time.sleep` (use `await asyncio.sleep`), `requests`, `psycopg2`, `Session` síncrona, `asyncio.run` ou `run_until_complete` dentro do app.
4. **Trabalho de CPU ou biblioteca síncrona demorada** (hash argon2) roda com `await asyncio.to_thread(...)`. `gerar_hash_senha` e `verificar_senha` continuam sendo funções comuns (fáceis de testar), e quem as chama usa `to_thread`.
5. **Uma `AsyncSession` por requisição ou por tarefa. Nunca compartilhe uma sessão entre corrotinas concorrentes** (`asyncio.gather`). Cada tarefa abre a sua: `async with FabricaSessao() as sessao:`.
6. A fábrica de sessões usa `expire_on_commit=False`. **Sem lazy loading**: relações (como o histórico da encomenda) são carregadas explicitamente na consulta, com `selectinload`.
7. Transações explícitas: `await sessao.commit()` e `await sessao.rollback()`. Nunca segure transação aberta durante uma chamada HTTP (ver `docs/data-model.md`).
8. **Um cliente HTTP por serviço**: um `httpx.AsyncClient` criado no `lifespan`, guardado em `app.state`, injetado onde for usado e fechado no encerramento.
9. **Rotinas em segundo plano são tarefas `asyncio`** (`asyncio.create_task`), iniciadas no `lifespan` e **canceladas e aguardadas** no encerramento. O laço captura `Exception` (nunca engole `asyncio.CancelledError`), registra o erro em log, continua, e dorme com `await asyncio.sleep`.
10. **Paralelismo controlado**: lotes são processados com `asyncio.gather(..., return_exceptions=True)`, limitados por `asyncio.Semaphore` (`CONCORRENCIA_MAXIMA_*`), cada item com a sua sessão.
11. **Unicidade e corrida**: a garantia vem das restrições do banco (`UNIQUE`, PK) e do tratamento de `IntegrityError`, nunca de "consultar e depois inserir". Para mudar um estado de forma segura, bloqueie a linha com `with_for_update()`.
12. Funções que dependem do relógio recebem `agora` como parâmetro (para testar sem esperar).
13. **Testes**: `pytest-asyncio` (`asyncio_mode = "auto"`), `httpx.AsyncClient(transport=httpx.ASGITransport(app=app))` e engine de teste com `NullPool`. Cenários de concorrência usam `asyncio.gather`.

## Regras para testes

1. **Todo critério de "Aceite" da tarefa tem pelo menos um teste.** No resumo final, entregue uma tabela "critério -> nome do teste".
2. **Tarefas (TDD):** escreva os testes primeiro, rode e mostre que falham, **mostre-os e espere minha revisão**, e só então implemente.
3. **Nunca altere, apague, ignore (`skip`, `xfail`) ou afrouxe um teste para fazê-lo passar.** Se um teste falha, corrija o código. Se achar que o teste está errado, explique o motivo e peça autorização antes de mudá-lo.
4. **Teste comportamento, não implementação:** confira o status code, o corpo da resposta (inclusive o `codigo` do erro) e o estado do banco. Só use simulação (mock) nas **fronteiras externas**: HTTP de outro serviço (`httpx.MockTransport`) e o relógio (parâmetro `agora`). Não simule o código do próprio projeto para fazer o teste passar.
5. **Asserções específicas:** valores exatos (status, campos, contagens). Nada de `assert resposta` genérico, de apenas "não levantou exceção", nem de `assert True`.
6. **Caminhos de erro e de segurança também têm teste:** 401, 403, 404, 409 e 422 conforme o aceite, isolamento entre usuários, papel errado, assinatura inválida, evento duplicado.
7. **Concorrência:** use `asyncio.gather` com o número de requisições simultâneas que a tarefa pede e verifique a **contagem exata** (por exemplo, um 201 e quatro 409), não só a ausência de erro.
8. **Testes independentes e determinísticos:** não dependem da ordem de execução, não usam `sleep` real para esperar (use o relógio injetado), não acessam a rede externa e partem de um banco limpo.
9. **Nomes em português que descrevem o comportamento:** `test_login_com_senha_errada_retorna_401`.
10. **Organização:** testes unitários (funções puras, sem banco) em `tests/unit/`; testes de integração (API + Postgres de teste) em `tests/integration/`.
11. **Teste de sabotagem nas partes críticas** (HMAC, isolamento entre usuários, idempotência, transições de status, concorrência): ao concluir a tarefa, quebre a regra de propósito e confirme que **pelo menos um teste falha**. Exemplos: remover o filtro por dono, trocar `compare_digest` por `==`, remover o tratamento de `IntegrityError`, aceitar transição para trás. Relate o que quebrou e qual teste falhou, e então **desfaça a sabotagem**.
12. **Antes de encerrar, rode a suíte inteira do serviço** (`uv run pytest`, não só os testes novos) e informe o resultado: quantos testes passaram e se houve falha.
13. **Frontend:** não há testes automatizados no plano. Valide com `npm run build`, a checagem de tipos e os critérios manuais da tarefa.

## Convenções de código

- **Camadas**: `api -> services -> repositories -> models`.
  - `api/` só valida entrada, chama um service e devolve o schema. Sem SQL e sem regra de negócio.
  - `services/` guardam as regras de negócio e levantam exceções de domínio (subclasses de `ErroDeDominio`, com `status_code` e `codigo`).
  - `repositories/` são o **único** lugar com consultas SQLAlchemy.
- Injeção de dependência com `Depends()` e `Annotated[...]` (sessão do banco, usuário autenticado, papel exigido, chave de serviço).
- **Schemas** Pydantic separados para entrada e saída (`EncomendaCriar`, `EncomendaAtualizar`, `EncomendaLer`). Nunca devolva um model do SQLAlchemy direto.
- **Datas**: sempre `datetime` com fuso, em UTC (`datetime.now(UTC)`), colunas `DateTime(timezone=True)`. No JSON, ISO 8601 terminando em `Z`. A conversão para o horário de Brasília acontece **só no frontend**.
- **Valores de status** são MAIÚSCULOS em português nos dois serviços (contrato compartilhado, ver `docs/api.md`).
- **Erros**: handler global devolve `{"detalhe": "mensagem", "codigo": "CODIGO_DO_ERRO"}`. O 422 de validação do FastAPI mantém o formato padrão do framework (`{"detail": [...]}`), que é uma das exceções de idioma.
- **Configuração**: `pydantic-settings` lendo variáveis de ambiente (nomes em português, ver `docs/spec.md` seção 8). Nenhum segredo no código. `.env` fora do git.
- **Schema do banco só por Alembic.** `create_all` é permitido apenas nos testes.
- **Entre containers, use o nome do serviço** (`monitoramento-db`, `transportadora`, `monitoramento`), nunca `localhost`.
- Logs com `logging` (sem `print`). Em eventos de webhook, inclua `id_evento` e `codigo_rastreio`.

## O ADMIN mockado (regras de implementação)

- Definido por `ADMIN_EMAIL` e `ADMIN_SENHA` no `.env`. **Não é gravado em banco** e não aparece na tabela `usuarios`.
- A classe de configuração (`Configuracao`) declara os dois campos **sem valor padrão**, com validação (e-mail válido; senha com no mínimo 8 caracteres). Sem eles, o `pydantic-settings` levanta erro ao importar e o processo encerra. **Não crie valor padrão, nem "admin de desenvolvimento".**
- Login do ADMIN: comparar e-mail (em minúsculas) e senha com `secrets.compare_digest`, sem consultar o banco.
- Os **dois serviços** têm login próprio para o ADMIN, com a **mesma credencial** do `.env`, mas com **tokens independentes** (cada serviço tem o seu `SEGREDO_JWT`; um token de um serviço não vale no outro).
- O token do ADMIN tem `sub = "admin"` e `papel = "ADMIN"`. O do `USER` tem `sub = <id do usuário>` e `papel = "USER"`.
- O ADMIN **nunca** cria, edita nem exclui encomendas. Rotas de CRUD exigem `USER` (o ADMIN recebe 403).
- Registro público com o `ADMIN_EMAIL` é recusado (409 `EMAIL_JA_CADASTRADO`).

## Regras de segurança (não negociáveis)

- Senhas de `USER` com **argon2**. Nunca registre em log senha, token JWT, chave de API nem segredo de webhook.
- JWT: `PyJWT`, HS256, com `exp`, `sub` e `papel`. Token inválido ou expirado devolve 401.
- **Assinatura HMAC do webhook**: calculada e verificada sobre os **bytes brutos do corpo** (`request.body()`), nunca sobre um JSON reserializado. Compare com `hmac.compare_digest`. Valide o timestamp (tolerância de 300 s). A transportadora **assina de novo a cada tentativa de envio**, com timestamp atual.
- **Chave de API do serviço** (Monitoramento chamando a transportadora): comparar com `secrets.compare_digest`. É credencial de máquina, não de usuário.
- Recurso de outro usuário devolve **404**, nunca 403 (não revelar que existe).
- Sem SQL montado por interpolação de string.
- CORS: o frontend e a API ficam na mesma origem via gateway, então **não** habilite CORS aberto. Em desenvolvimento, o proxy do Vite resolve.

## O que NÃO fazer

- Não compartilhar código, pacote ou banco entre os serviços. Cada serviço tem a sua cópia da máquina de estados e do HMAC (de propósito: serviços independentes).
- Não persistir o ADMIN no banco e não criar rota de cadastro de ADMIN.
- Não usar `BackgroundTasks` para o que precisa sobreviver a um reinício. Use tabelas como fila (ver `docs/data-model.md`).
- Não escrever código bloqueante no caminho assíncrono (`def` em endpoint, `time.sleep`, `requests`, driver ou sessão síncronos). Ver as regras de concorrência.
- Não adicionar broker, Redis, Celery, WebSocket ou SSE. SSE e worker automático são **extras** (T19), só depois do MVP.
- Não criar funcionalidade que não esteja na tarefa atual.
- Não reescrever arquivos inteiros para ajustes pequenos. Edite o trecho necessário.

## Identidade visual (frontend e tela da transportadora)

Paleta **verde-petróleo**:

| Uso | Cor |
|---|---|
| Primária (botões, links) | `#0F766E` |
| Escura (navbar, hover) | `#134E4A` |
| Destaque (aba ativa, detalhes) | `#F97316` |
| Fundo da página | `#F3F8F7` |
| Texto | `#2C2C2A` |

No Bootstrap, sobrescreva as variáveis CSS em um `theme.css` importado **depois** do Bootstrap (`--bs-primary`, `--bs-primary-rgb`, `--bs-link-color`, `--bs-body-bg` e as variáveis do `.btn-primary`). Não use Sass.

Logos em `frontend/public/` (e uma cópia em `transportadora/app/static/`): `logo-horizontal.svg` (navbar clara), `logo-invertido.svg` (navbar escura `#134E4A`), `logo-vertical.svg` (login e registro), `icone.svg` e `favicon.svg`. O nome é sempre escrito **HookLog**.

### Selos (badges) de status

O selo sempre mostra o **texto** do status (nunca só a cor).

| Status | Rótulo | Fundo | Texto | Aba |
|---|---|---|---|---|
| `REGISTRO_PENDENTE` | Registrando na transportadora | `#F1EFE8` | `#444441` | Não encaminhadas |
| `FALHA_NO_REGISTRO` | Falha no registro | `#FCEBEB` | `#791F1F` | Não encaminhadas |
| `AGUARDANDO_ENVIO` | Aguardando envio | `#FAEEDA` | `#633806` | Não encaminhadas |
| `POSTADO` | Postado | `#FAEEDA` | `#633806` | Não encaminhadas |
| `EM_TRANSITO` | Em trânsito | `#E6F1FB` | `#0C447C` | A caminho |
| `SAIU_PARA_ENTREGA` | Saiu para entrega | `#E6F1FB` | `#0C447C` | A caminho |
| `ENTREGUE` | Entregue | `#EAF3DE` | `#27500A` | Entregues |

## Regras do frontend

- TypeScript `strict`. Sem `any`.
- Base da API: `import.meta.env.VITE_API_BASE ?? '/api'`. O Vite (`vite.config.ts`) faz proxy de `/api` para `http://localhost:8000` removendo o prefixo, para o dev se comportar como o gateway.
- Token JWT em `localStorage` (chave `hooklog_token`), enviado em `Authorization: Bearer`. Resposta 401 limpa o token e redireciona para `/login`.
- **Comportamento por papel**: depois do login, `GET /autenticacao/eu` informa o `papel`. `USER` vai para `/encomendas` (CRUD das suas encomendas). `ADMIN` vai para `/admin` (todas as encomendas, somente leitura) e só ele vê, na navbar, o link **Transportadora** (um `<a href="/transportadora/">`, não uma rota do React; a tela da transportadora pede o login dela).
- Atualização da lista por **polling**: TanStack Query com `refetchInterval: 5000`.
- Datas: `Intl.DateTimeFormat('pt-BR', { timeZone: 'America/Sao_Paulo', dateStyle: 'short', timeStyle: 'medium' })`.
- Textos da interface em português, com a primeira letra maiúscula e sem ponto final em rótulos e botões.
- Nomes de componentes, funções e variáveis em português (hooks mantêm o prefixo `use`).

## Definição de pronto (para cada tarefa)

- Critérios de aceite da tarefa atendidos em `docs/tasks.md`.
- Testes do serviço passando (`uv run pytest`, suíte inteira) e `ruff check` sem erros.
- Cada critério de aceite tem um teste correspondente, listado no resumo final (ver **Regras para testes**).
- Nomes novos em português, conforme a regra de idioma.
- Nenhuma chamada bloqueante no código assíncrono e nenhuma sessão compartilhada entre corrotinas concorrentes.
- Nada fora do escopo da tarefa foi alterado.
- Se a tarefa mudou um contrato (rota, campo, tabela), isso foi **avisado** para atualizar o documento correspondente, e não alterado em silêncio.
