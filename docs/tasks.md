# HookLog: plano de tarefas

Versão 1.2 · 24/11/2026 · Desenvolvimento: **24/11 a 04/12/2026** · Apresentação: 12/12/2026

Cada tarefa é uma **fatia pequena e completa**: dá para implementar, testar e revisar em uma sessão. Faça uma por vez, na ordem (respeitando "Depende de"). Esforço: **P** (pequeno, cerca de 1 hora), **M** (médio, 2 a 3 horas), **G** (grande, 3 a 5 horas).

**Regras em todas as tarefas:**
- Nomes em **português** (exceções listadas no `AGENTS.md`).
- Código **assíncrono** (`async def`, `AsyncSession`, `httpx.AsyncClient`) e as **regras de concorrência** do `AGENTS.md`. Nenhuma chamada bloqueante.

## Como pedir uma tarefa ao agente

```
Leia AGENTS.md e docs/ (spec, api, data-model).
Implemente a tarefa T06 de docs/tasks.md.
Antes de codar, liste os arquivos que vai criar ou alterar e espere minha confirmação.
Use nomes em português e siga as regras de concorrência (async def, uma sessão por tarefa,
nada bloqueante). Não faça nada fora do escopo da tarefa.
```

Em tarefas **(TDD)**: escreva os testes primeiro, rode e mostre que falham, depois implemente.

## Cronograma

São **10 dias de desenvolvimento (24/11 a 03/12)** mais o dia **04/12 de folga e ensaio**. As 18 tarefas do MVP somam cerca de 40 pontos de esforço (P = 1, M = 2, G = 3), ou seja, **uns 4 pontos por dia**. É um ritmo apertado: os dias de carga alta estão marcados, e o dia 01/12 foi deixado mais leve de propósito, para absorver atrasos.

| Dia | Data | Tarefas | Carga |
|---|---|---|---|
| 1 | Ter 24/11 | T01, T02 | 4 |
| 2 | Qua 25/11 | T03, T05, T09 | 4 |
| 3 | Qui 26/11 | T04, T07 | **6** |
| 4 | Sex 27/11 | T06, T14 | 5 |
| 5 | Sáb 28/11 | T08, T15 | **6** |
| 6 | Dom 29/11 | T10, T16 | 5 |
| 7 | Seg 30/11 | T11, T12 | 5 |
| 8 | Ter 01/12 | T13, T17, início da T18 | 3 (folga embutida) |
| 9 | Qua 02/12 | T18 | 2 + correções |
| 10 | Qui 03/12 | Revisão geral, correções e checklist final (sem tarefa nova) | folga |
| 11 | Sex 04/12 | Folga, ensaio da apresentação, correções finais | |
| | 05 a 12/12 | Reserva até a apresentação. Extras (T19) só se tudo estiver pronto | |

**README:** não há tarefa de README neste plano. Ele será feito no final, em uma tarefa especial passada à parte. A T01 só cria um README mínimo.

### Pontos de controle

| Quando | O que precisa estar pronto |
|---|---|
| Fim de 27/11 | Login funcionando pelo gateway (T04, T14) e CRUD do USER no backend (T06) |
| Fim de 29/11 | Cadastro integrado à transportadora (T10) e CRUD pela interface (T15) |
| Fim de 01/12 | Backend completo (T13) e todas as telas (T16, T17) |
| Fim de 03/12 | **MVP completo** e revisado (T18 e checklist final) |

Se, em um ponto de controle, o atraso passar de **meio dia**, aplique os cortes na ordem: (1) extras (T19); (2) página de detalhe com linha do tempo do USER (parte da T16); (3) script automatizado de ponta a ponta, mantendo só o roteiro manual (T18); (4) acabamento visual (contagem nas abas, estados vazios elaborados). **Nunca cortar:** o CRUD completo do `USER`, a visão do `ADMIN`, HMAC, retry com backoff, idempotência, registro pendente, a exigência do ADMIN na inicialização e o código assíncrono.

### Dicas para manter o ritmo

- Trabalhe em **duas frentes**: backend de manhã, frontend à tarde (o frontend só precisa do contrato de `docs/api.md`).
- Não deixe a conversa do agente crescer: **uma sessão por tarefa**.
- Rode o Compose completo ao fim de cada dia, para não descobrir problema de integração só no final.

---

## Fase 0: esqueleto

### T01 · Repositório, documentação e serviços FastAPI assíncronos mínimos (M)
**Dia:** 24/11 · **Depende de:** nada
**Escopo:** criar a estrutura de pastas do `AGENTS.md`, copiar `AGENTS.md` e `docs/`, criar `.gitignore`, `.env.example` e `README.md` mínimo, e inicializar os dois projetos Python com `uv`.
**Arquivos:**
- `.gitignore` (`.venv/`, `node_modules/`, `.env`, `__pycache__/`, `dist/`, `.ruff_cache/`).
- `.env.example` com as variáveis de `docs/spec.md` seção 9. Segredos com valor `troque-me`. **`ADMIN_EMAIL=` e `ADMIN_SENHA=` em branco, de propósito**, com comentário avisando que são obrigatórias.
- `README.md`: nome, uma frase, "ver docs/" e o aviso de preencher `ADMIN_EMAIL` e `ADMIN_SENHA`.
- `monitoramento/pyproject.toml` e `transportadora/pyproject.toml`: dependências da stack (FastAPI, uvicorn, SQLAlchemy 2.0, `asyncpg`, Alembic, pydantic-settings, httpx, `argon2-cffi`, `PyJWT`; dev: pytest, `pytest-asyncio`, ruff), com `asyncio_mode = "auto"` e ruff com line-length 100.
- `app/main.py` em cada serviço, com `GET /health` como **`async def`** (ainda sem banco), e `tests/unit/test_saude.py` usando `httpx.AsyncClient` com `ASGITransport`.
**Aceite:**
- A estrutura de pastas bate com a do `AGENTS.md`; `.env` não é versionado; `git init` e primeiro commit feitos.
- `uv sync` cria um `.venv` por serviço, com `uv.lock`.
- `GET /health` devolve 200 `{"status": "ok", "servico": "..."}` nos dois serviços (portas 8000 e 8001).
- `uv run pytest` e `uv run ruff check .` passam nos dois.

### T02 · Docker Compose, exigência do ADMIN e gateway nginx (M)
**Dia:** 24/11 · **Depende de:** T01
**Escopo:** Dockerfiles, `docker-compose.yml`, `docker-compose.override.yml`, `gateway/Dockerfile` e `gateway/nginx.conf`.
**Detalhes:**
- Dockerfile dos serviços: `python:3.12-slim`, `uv` copiado de `ghcr.io/astral-sh/uv`, `uv sync --frozen --no-dev`, usuário sem privilégios.
- Dois Postgres 16 (`monitoramento-db` e `transportadora-db`), cada um com volume, usuário (`usuario_monitoramento`, `usuario_transportadora`) e senha próprios, e `healthcheck` com `pg_isready`. Os serviços usam `depends_on` com `condition: service_healthy`.
- **Exigência do ADMIN:** `ADMIN_EMAIL: ${ADMIN_EMAIL:?defina ADMIN_EMAIL no arquivo .env}` e `ADMIN_SENHA: ${ADMIN_SENHA:?defina ADMIN_SENHA no arquivo .env}` nos dois serviços.
- Gateway: único com porta exposta (`8080:80`); até a T14 serve um `index.html` placeholder.
- Rotas do nginx: `/` (com `try_files $uri /index.html`); `/api/` com `proxy_pass http://monitoramento:8000/;` (a barra final remove o prefixo); `/api/webhooks/` devolve **404** (declarado antes de `/api/`); `/transportadora` redireciona (301) para `/transportadora/`; `/transportadora/` com `proxy_pass http://transportadora:8001/;`; cabeçalhos `Host`, `X-Real-IP` e `X-Forwarded-For`.
- O override publica as portas 5433, 5434, 8000 e 8001 (só dev).
**Aceite:**
- Com `ADMIN_EMAIL` e `ADMIN_SENHA` no `.env`, `docker compose up --build` sobe tudo, e `http://localhost:8080/api/health` e `http://localhost:8080/transportadora/health` respondem 200.
- **Sem** uma das duas variáveis, `docker compose up` falha na hora com a mensagem pedindo para defini-la, e nenhum contêiner sobe.
- `http://localhost:8080/transportadora` redireciona para `.../transportadora/`.
- `POST http://localhost:8080/api/webhooks/transportadora` devolve 404.
- Depois de `docker compose down` e `up`, os volumes continuam (sem `-v`).

---

## Fase 1: Monitoramento base

### T03 · Configuração, banco assíncrono, Alembic e modelos do Monitoramento (M)
**Dia:** 25/11 · **Depende de:** T02
**Escopo:** configuração (com ADMIN obrigatório), engine e sessão assíncronos, models, migração inicial e health com verificação do banco.
**Arquivos:**
- `app/core/configuracao.py`: classe `Configuracao` (pydantic-settings) com as variáveis de `docs/spec.md` seção 9. **`admin_email` (e-mail válido) e `admin_senha` (mínimo 8 caracteres) não têm valor padrão**; sem elas, criar a `Configuracao` levanta `ValidationError` e o processo encerra com mensagem clara.
- `app/core/banco_dados.py`: `create_async_engine` (`pool_size=TAMANHO_POOL_BANCO`, `pool_pre_ping=True`), `FabricaSessao = async_sessionmaker(..., expire_on_commit=False)`, `obter_sessao` (gerador assíncrono para `Depends`) e `MetaData` com a `CONVENCAO_NOMES` de `docs/data-model.md`.
- `app/models/*`: `Usuario` (sem coluna de papel), `Encomenda`, `HistoricoStatus`, `EventoProcessado`; enums `Papel` (`USER`, `ADMIN`) e `StatusEncomenda`.
- `alembic/` gerado com `alembic init -t async` e a migração inicial.
- `tests/conftest.py`: define `ADMIN_EMAIL` e `ADMIN_SENHA` fixos para os testes, cria `monitoramento_teste` se faltar, `create_all` via `conn.run_sync`, engine com `NullPool` e limpeza entre testes.
**Aceite:**
- `uv run alembic upgrade head` cria as 4 tabelas conforme `docs/data-model.md` (sem coluna `papel` em `usuarios`).
- O comando do contêiner passa a ser `alembic upgrade head && uvicorn ...`.
- `GET /health` (`async def`) devolve 503 quando o banco não responde (teste com URL inválida).
- Teste: duas consultas simultâneas (`asyncio.gather`) com **sessões distintas** funcionam.
- **Testes unitários:** criar `Configuracao` sem `ADMIN_EMAIL`, sem `ADMIN_SENHA`, com e-mail inválido e com senha de 7 caracteres levanta `ValidationError` em cada caso.
- **Teste manual:** iniciar o serviço sem as variáveis do ADMIN encerra o processo com código diferente de zero.

### T05 · Máquina de estados do Monitoramento (TDD) (P)
**Dia:** 25/11 · **Depende de:** T03
**Escopo:** `app/services/maquina_de_estados.py` com `ORDEM_STATUS`, `grupo_do_status(status)` e `pode_aplicar_evento(status_atual, status_evento)` (funções puras, sem E/S, portanto **não** são `async`).
**Testes (parametrizados):** toda a tabela de `docs/spec.md` seção 6 (ordem e grupo de cada status), avanço permitido (inclusive pulando um intermediário e saindo de `REGISTRO_PENDENTE`) e recusa de status igual ou anterior.
**Aceite:** testes passando, sem tocar no banco.

### T09 · HMAC: assinar e verificar (TDD) (P)
**Dia:** 25/11 · **Depende de:** T01
**Escopo:** `transportadora/app/core/assinador_hmac.py` (função `assinar(segredo, carimbo_tempo, corpo_bruto)`, que devolve os cabeçalhos `X-Carimbo-Tempo` e `X-Assinatura`) e `monitoramento/app/services/verificador_hmac.py` (função `verificar(segredo, carimbo_tempo, assinatura, corpo_bruto, agora, tolerancia_segundos)`). Código separado nos dois serviços, de propósito. Funções puras e rápidas (síncronas, sem E/S), podendo ser chamadas direto de dentro de corrotinas.
**Algoritmo:** exatamente o de `docs/api.md` seção 4 (HMAC-SHA256 sobre `"{carimbo_tempo}." + corpo bruto`, cabeçalho `sha256=<hex>`, tolerância de 300 s, `hmac.compare_digest`).
**Testes (em cada serviço):**
- Um **vetor de teste idêntico nos dois** (mesmo segredo, carimbo e corpo, com o resumo esperado gerado por um script Python à parte) prova que os dois lados são compatíveis.
- Falha com: corpo alterado em 1 byte, carimbo diferente, segredo errado, cabeçalho sem o prefixo `sha256=`, carimbo não numérico, carimbo fora da janela (passado e futuro).
- O verificador trabalha com **bytes**, não com JSON reserializado.
**Aceite:** testes passando nos dois serviços.

### T04 · Segurança e autenticação de USER e ADMIN (TDD) (G)
**Dia:** 26/11 · **Depende de:** T03
**Escopo:** `app/core/seguranca.py`, `app/core/dependencias.py`, `app/core/erros.py`, `ServicoAutenticacao`, schemas e as rotas `POST /autenticacao/registro`, `POST /autenticacao/login` (formulário OAuth2) e `GET /autenticacao/eu`. **Não existe seed de ADMIN.**
**Funções e classes (escreva os testes unitários primeiro):**
- `gerar_hash_senha` e `verificar_senha` (argon2, funções comuns). **O `ServicoAutenticacao` as chama com `await asyncio.to_thread(...)`**, para não bloquear o laço.
- `autenticar_admin(email, senha, configuracao)`: compara e-mail (em minúsculas) e senha com `secrets.compare_digest`, sem tocar no banco.
- `criar_token_acesso(sub, papel)` e `decodificar_token_acesso(token)` (levanta `TOKEN_EXPIRADO` ou `TOKEN_INVALIDO`).
- `UsuarioAutenticado` (`id: int | None`, `papel: Papel`) e as dependências **`async def`** `obter_usuario_atual`, `exigir_usuario` (só `USER`; o ADMIN recebe 403 `ACESSO_NEGADO`) e `exigir_admin` (só `ADMIN`; o USER recebe 403).
- `ErroDeDominio` e o handler global (formato `{"detalhe","codigo"}`).
**Aceite:**
- Unitários: hash diferente da senha; verificação certa e errada; `autenticar_admin` aceita a credencial certa (inclusive com e-mail em maiúsculas) e recusa e-mail ou senha errados; token válido, expirado, adulterado, sem `sub`, sem `papel` e com outra chave; matriz de `exigir_usuario` e `exigir_admin` com cada papel.
- **O laço não bloqueia:** durante 5 verificações de senha simultâneas (`asyncio.gather`), uma corrotina "relógio" que dorme 10 ms continua rodando (conta mais de um tique).
- Registro: 201; 409 `EMAIL_JA_CADASTRADO` (inclusive com maiúsculas diferentes e com o **`ADMIN_EMAIL`**); 422 (e-mail inválido, senha curta). O papel é sempre `USER`.
- Login de `USER`: 200 com token (`sub` = id, `papel` = `USER`); 401 `CREDENCIAIS_INVALIDAS` com a **mesma** mensagem para e-mail inexistente e senha errada.
- Login de `ADMIN` com a credencial do `.env`: 200 com token (`sub` = `admin`, `papel` = `ADMIN`) **sem nenhuma linha em `usuarios`**; senha errada: 401.
- `/autenticacao/eu`: 200 para USER (com `id`) e para ADMIN (`id` nulo); 401 sem token, inválido e expirado. O botão *Authorize* do Swagger funciona.
- Nenhuma senha ou token aparece em logs.

### T06 · CRUD das encomendas do USER e visão do ADMIN (G)
**Dia:** 27/11 · **Depende de:** T04, T05
**Escopo:** schemas (`EncomendaCriar`, `EncomendaAtualizar`, `EncomendaLer`), repository, `ServicoEncomenda` (todos `async`) e as rotas:
- `USER` (`exigir_usuario`): `POST /encomendas`, `GET /encomendas?grupo=`, `GET /encomendas/{id}` (com histórico, via `selectinload`), **`PATCH /encomendas/{id}`** e `DELETE /encomendas/{id}`.
- `ADMIN` (`exigir_admin`, somente leitura): `GET /admin/encomendas?grupo=&usuario_id=` e `GET /admin/encomendas/{id}`.
**Detalhes:** nesta tarefa, o `POST` salva como `REGISTRO_PENDENTE` com `proxima_tentativa_em = agora` e grava a primeira linha do histórico; o registro na transportadora entra na T10. Normalizar o código (maiúsculas, sem espaços nas pontas). `EncomendaAtualizar` aceita **só** `descricao` e `vendedor` (`extra="forbid"`). A duplicidade de código é resolvida pela restrição `UNIQUE` (tratando `IntegrityError`).
**Aceite (testes de integração):**
- **Create:** 201 com `grupo` correto; código repetido devolve 409 `CODIGO_RASTREIO_DUPLICADO` (inclusive entre usuários diferentes).
- **Read:** a lista devolve só as do usuário; o filtro `grupo` funciona; grupo inválido devolve 422; o detalhe traz o histórico em ordem cronológica.
- **Update:** `PATCH` devolve 200 e muda `atualizado_em`; corpo vazio, campo inválido ou envio de `codigo_rastreio` ou `status` devolve 422; **não** cria histórico.
- **Delete:** 204, e apaga também o histórico.
- **Isolamento:** o usuário B recebe **404** ao ver, editar ou excluir a encomenda do usuário A.
- **Papéis:** o ADMIN recebe **403** em todas as rotas `/encomendas`; o USER recebe 403 em `/admin/...`; sem token, 401.
- **ADMIN:** vê as encomendas de todos, com `usuario_id` e `usuario_email`; filtros funcionam; detalhe com histórico; id inexistente dá 404. `POST`, `PATCH` e `DELETE` em `/admin/encomendas...` devolvem 405 ou 404.
- **Concorrência:** 5 cadastros simultâneos (`asyncio.gather`) do **mesmo** código produzem exatamente um 201 e quatro 409; 20 cadastros simultâneos de códigos diferentes produzem 20 respostas 201.

---

## Fase 2: transportadora base

### T07 · Base da transportadora: configuração, banco, login do ADMIN e chave de serviço (G)
**Dia:** 26/11 · **Depende de:** T03
**Escopo:** mesma estrutura da T03 para a transportadora, mais a autenticação (tudo `async`).
**Arquivos:**
- `app/core/configuracao.py`: `Configuracao` com **`admin_email` e `admin_senha` obrigatórios** (mesmas validações da T03) e `segredo_jwt` próprio.
- `app/core/banco_dados.py`, `app/models/*` (`Remessa`, `EventoWebhook`, `TentativaWebhook`), migração inicial (template async), `conftest` (com `transportadora_teste`, `NullPool` e ADMIN fixo), health com banco.
- `app/core/erros.py`: `ErroDeDominio` e handler (`{"detalhe","codigo"}`).
- `app/core/seguranca.py` e `dependencias.py`: `autenticar_admin`, `criar_token_acesso`, `decodificar_token_acesso`, `exigir_admin` e `exigir_chave_servico` (compara `X-Chave-Api` com `secrets.compare_digest`), todas as dependências `async def`.
- `app/api/autenticacao.py`: `POST /autenticacao/login` (formulário OAuth2) e `GET /autenticacao/eu`.
**Aceite:**
- `alembic upgrade head` cria as 3 tabelas conforme `docs/data-model.md`.
- Login do ADMIN com a credencial do `.env`: 200 com token; senha errada: 401 `CREDENCIAIS_INVALIDAS`.
- **Matriz de acesso** (rota de teste protegida): sem credencial 401; token com outro segredo (como o de um USER do Monitoramento) 401 `TOKEN_INVALIDO`; token de ADMIN em rota de chave de serviço 403 `PERMISSAO_INSUFICIENTE`; chave de serviço em rota de ADMIN 403; credencial correta 200.
- **Testes unitários:** `Configuracao` sem `ADMIN_EMAIL` ou `ADMIN_SENHA` (ou com valores inválidos) levanta `ValidationError`; subir o serviço sem elas encerra o processo.

### T08 · Remessas, mudança de status e geração de evento (TDD) (G)
**Dia:** 28/11 · **Depende de:** T07
**Escopo:** `ServicoRemessa` e repositories (`async`), `app/services/maquina_de_estados.py` (com `proximo_status(status_atual)`, função pura) e as rotas:
- `POST /remessas` (chave de serviço, idempotente por `codigo_rastreio`), `GET /remessas/{codigo_rastreio}` (ADMIN ou chave de serviço), `GET /remessas` (ADMIN), com o campo calculado `proximo_status`.
- `POST /remessas/{codigo_rastreio}/status` e `POST /remessas/{codigo_rastreio}/entregar` (só ADMIN).
**Regra da mudança de status:** em **uma transação**, bloquear a remessa (`with_for_update()`), validar a transição, atualizar a remessa e inserir o `eventos_webhook` (`PENDENTE`, `proxima_tentativa_em = agora`, `corpo` serializado uma única vez, `id_evento` UUID v4).
**Testes primeiro:**
- Sequência válida passo a passo; pular um passo, repetir e voltar devolvem 409 `TRANSICAO_INVALIDA`.
- `status: "ENTREGUE"` em `/status` devolve 422; `/entregar` fora de `SAIU_PARA_ENTREGA` devolve 409.
- Cada mudança cria exatamente **um** evento, com `tipo_evento` correto (`remessa.status_alterado` ou `remessa.entregue`); o `corpo` tem os campos de `docs/api.md` seção 4 (`entregue_em` e `recebido_por` só na entrega) e datas em UTC com `Z`.
- Se a gravação do evento falhar, a remessa **não** muda.
- `POST /remessas`: 201 na primeira vez e 200 ao repetir o código (sem alterar); token de ADMIN no `POST` devolve 403; chave de serviço em `GET /remessas` devolve 403; código inexistente devolve 404 `REMESSA_NAO_ENCONTRADA`; `proximo_status` correto em cada estado (e `null` em `ENTREGUE`).
- **Concorrência:** 5 `POST /remessas` simultâneos do mesmo código dão um 201 e quatro 200; 5 chamadas simultâneas de `/status` para o mesmo próximo status dão um 200, quatro 409 e **um único** evento criado.
**Aceite:** testes passando; a resposta das rotas não espera nenhum envio de webhook.

---

## Fase 3: integração

### T10 · Cliente da transportadora, registro no cadastro e rotina de registro pendente (G)
**Dia:** 29/11 · **Depende de:** T06, T08
**Escopo:**
- `app/clients/cliente_transportadora.py`: classe `ClienteTransportadora` usando um **`httpx.AsyncClient` único** (criado no `lifespan`, em `app.state`, e fechado no encerramento), timeout configurável, cabeçalho `X-Chave-Api` e o método `async registrar_remessa`. Levanta `ErroTransitorio` ou `ErroPermanente` conforme `docs/api.md` seção 5.
- Integração em `POST /encomendas`, conforme `docs/spec.md` seção 7.1 (a chamada HTTP acontece **fora** de transação aberta). O `url_callback` enviado é `URL_PUBLICA_WEBHOOK`.
- `app/workers/registro_pendente.py`: função `processar_pendentes(fabrica_sessao, cliente, agora, concorrencia_maxima)`, que processa o lote **em paralelo** (`gather` + `Semaphore`, uma sessão por encomenda), e o laço `laco_registro_pendente`, iniciado como **tarefa `asyncio`** no `lifespan` e cancelada e aguardada no encerramento.
- Rota `POST /encomendas/{id}/registrar` (só `USER`).
**Aceite (testes com `httpx.MockTransport` e relógio injetado):**
- Cadastro com sucesso: `AGUARDANDO_ENVIO`, com linha de histórico. Timeout ou 503: `REGISTRO_PENDENTE`, `tentativas_registro = 1`, `proxima_tentativa_em` no futuro, resposta ainda **201**. 401 ou 422: `FALHA_NO_REGISTRO`, com `ultimo_erro_registro`. O corpo enviado tem `codigo_rastreio`, `vendedor` e `url_callback`, e o `X-Chave-Api` está presente.
- Rotina: pendente vencida é registrada; ainda não vencida é ignorada; backoff 5, 10, 20, 40 e 60 s (teto); ao atingir `MAX_TENTATIVAS_REGISTRO`, `FALHA_NO_REGISTRO`; erro permanente vira `FALHA_NO_REGISTRO` na hora.
- **Paralelismo:** com 10 pendentes e um servidor simulado que demora 0,2 s por chamada, o lote termina em bem menos que 2 s (processamento concorrente) e nunca excede `concorrencia_maxima` chamadas ao mesmo tempo.
- O laço sobrevive a exceções e **termina limpo** quando a tarefa é cancelada.
- `POST /encomendas/{id}/registrar`: 202 e volta a `REGISTRO_PENDENTE` com tentativas zeradas, só a partir de `FALHA_NO_REGISTRO`; outro status devolve 409 `ESTADO_INVALIDO`; encomenda alheia 404; ADMIN 403.
- **Teste manual:** derrubar `transportadora`, cadastrar encomenda (fica pendente), subir a transportadora; em poucos segundos o status muda sozinho.

### T11 · Despachante de webhooks (transportadora) (G)
**Dia:** 30/11 · **Depende de:** T08, T09
**Escopo:** `app/workers/enviador_webhook.py` (função `async enviar_evento`, envia um evento com `httpx.AsyncClient`) e `app/workers/despachante_webhook.py` (função `processar_eventos_pendentes(fabrica_sessao, cliente_http, agora, concorrencia_maxima)` e o laço, como **tarefa `asyncio`** no `lifespan`, a cada `INTERVALO_ROTINA_WEBHOOK_SEGUNDOS`).
**Regras:** as de `docs/spec.md` seção 7.3 e `docs/api.md` seção 4 (classificação das respostas, backoff `base * 2^(n-1)`, `MAX_TENTATIVAS_WEBHOOK`), a consulta de `docs/data-model.md` seção 4 (ordem por remessa) e as transações da seção 5. O lote é enviado **em paralelo** (`gather` + `Semaphore`, uma sessão por evento). Cada tentativa gera `X-Carimbo-Tempo` e `X-Assinatura` **novos**, sobre os mesmos bytes do `corpo`, e grava uma linha em `tentativas_webhook`.
**Aceite (testes com `httpx.MockTransport` e relógio injetado):**
- 200 marca `ENVIADO` com `enviado_em`.
- 500, timeout e conexão recusada reagendam com atrasos de 1, 2, 4 e 8 s; ao chegar a 5 tentativas, `FALHA`.
- 401, 404, 409 e 422 marcam `FALHA` **na primeira tentativa**, sem retry; 408 e 429 fazem retry.
- Evento mais novo da mesma remessa **espera** o mais antigo ainda `PENDENTE`; remessas diferentes não se bloqueiam.
- O corpo enviado é byte a byte igual ao `corpo` guardado, em todas as tentativas, e a assinatura passa no verificador (T09).
- **Paralelismo:** 10 eventos de remessas diferentes, com destino simulado que demora 0,2 s, são enviados em bem menos que 2 s, sem exceder `concorrencia_maxima` envios simultâneos.
- O laço sobrevive a exceções e termina limpo quando cancelado.

### T12 · Recebimento do webhook no Monitoramento (M)
**Dia:** 30/11 · **Depende de:** T05, T06, T09
**Escopo:** `app/api/webhooks.py`, `ServicoWebhook` (`app/services/servico_webhook.py`, método `async aplicar_evento`) e o schema do evento. Seguir a **ordem das verificações** de `docs/api.md` seção 2.4 e a transação de `docs/data-model.md` seção 5 (inserir em `eventos_processados`, bloquear a encomenda com `with_for_update()`, comparar as ordens, atualizar, gravar o histórico). Ler o corpo bruto com `await request.body()`.
**Aceite (testes de integração, usando `assinar` da T09 para montar requisições válidas):**
- Evento válido: 200 `aplicado`; status atualizado, linha no histórico com o `id_evento`, registro em `eventos_processados`, e `entregue_em` preenchido em `remessa.entregue`.
- Assinatura errada, carimbo antigo ou ausência dos cabeçalhos: 401 `ASSINATURA_INVALIDA`, nada alterado. Corpo inválido com assinatura válida: 422.
- Mesmo `id_evento` enviado de novo: 200 `duplicado`, nada alterado.
- `codigo_rastreio` desconhecido: 404. Status igual ou anterior ao atual: 409 `TRANSICAO_INVALIDA`.
- Pulo para frente (ex.: `EM_TRANSITO` com a encomenda em `AGUARDANDO_ENVIO`) e evento com a encomenda ainda em `REGISTRO_PENDENTE`: aplicados.
- O campo `vendedor` do webhook **não** sobrescreve o vendedor local.
- **Concorrência:** 10 requisições simultâneas (`asyncio.gather`) com o **mesmo** `id_evento` produzem exatamente um `aplicado` e nove `duplicado`, sem erro 500; 2 eventos diferentes e simultâneos da mesma encomenda (`EM_TRANSITO` e `SAIU_PARA_ENTREGA`) terminam em `SAIU_PARA_ENTREGA`, sem corromper o histórico.
- A rota funciona sem JWT.

### T13 · Log de webhooks e reenvio (P)
**Dia:** 01/12 · **Depende de:** T11
**Escopo:** `GET /logs-webhook?codigo_rastreio=&estado=` e `POST /logs-webhook/{id}/reenviar`, só para `ADMIN`.
**Aceite:**
- O log lista os eventos do mais recente para o mais antigo, cada um com `historico_tentativas` (carregado com `selectinload`); os filtros funcionam.
- Reenvio: 202, `estado = PENDENTE`, `total_tentativas = 0`, **mesmo `id_evento` e mesmo `corpo`**; inexistente devolve 404 `EVENTO_WEBHOOK_NAO_ENCONTRADO`.
- Sem token 401; chave de serviço 403.
- **Teste manual ponta a ponta:** reenviar um evento já `ENVIADO` e ver o Monitoramento responder `duplicado` (visível no histórico de tentativas) sem alterar a encomenda.

---

## Fase 4: frontend

### T14 · Base do frontend, login e registro (M)
**Dia:** 27/11 · **Depende de:** T02, T04
**Escopo:** projeto Vite + React + TypeScript `strict`, react-bootstrap, React Router, TanStack Query; `theme.css` com a paleta do `AGENTS.md`; logos e favicon em `public/`; cliente HTTP com base `/api` e tratamento de 401; `ContextoAutenticacao` (token e `papel`, obtido em `/autenticacao/eu`); `RotaProtegida` e `RotaAdmin`; navbar com `logo-invertido.svg`; proxy do Vite; `gateway/Dockerfile` em duas etapas (build do React + nginx); `PaginaLogin` e `PaginaRegistro` com o logo vertical.
**Comportamento por papel:** o login envia `application/x-www-form-urlencoded` e redireciona conforme o papel (`USER` para `/encomendas`, `ADMIN` para `/admin`). `USER` vê "Minhas encomendas" na navbar; `ADMIN` vê "Todas as encomendas" e o link **Transportadora** (`<a href="/transportadora/">`), e não vê telas de CRUD. O registro cria sempre um `USER`. Mensagens de erro por `codigo`.
**Aceite:**
- `npm run build` e a checagem de tipos passam.
- Pelo gateway (`http://localhost:8080`): registrar, entrar e sair funcionam para os dois papéis (o ADMIN com a credencial do `.env`); o token fica em `localStorage`; recarregar mantém a sessão; token expirado volta para `/login`.
- Rota protegida sem token redireciona para `/login`; `/admin` redireciona o `USER`; `/encomendas` redireciona o `ADMIN` para `/admin`.

### T15 · Lista de encomendas com CRUD (USER) (G)
**Dia:** 28/11 · **Depende de:** T06, T14
**Escopo:** `PaginaEncomendas` com as três abas e contagem em cada uma, `SeloStatus` conforme a tabela do `AGENTS.md`, `ModalEncomenda` (usado para **criar e editar**, com validação igual à API; na edição o código de rastreio fica somente leitura), exclusão com confirmação, botão "Tentar registrar novamente" em `FALHA_NO_REGISTRO`, polling de 5 s com TanStack Query, estados de carregamento, vazio e erro.
**Aceite:**
- **Create, Read, Update e Delete** funcionam pela interface.
- Cadastrar uma encomenda a mostra na aba correta; mudar o status na transportadora (pela API) move o item de aba em até 5 s, sem recarregar.
- Em `ENTREGUE`, a linha mostra vendedor e data e hora no horário de Brasília.
- Mensagem clara para código duplicado (409).

### T16 · Visão do ADMIN e detalhe da encomenda (M)
**Dia:** 29/11 · **Depende de:** T06, T15
**Escopo:**
- `PaginaAdmin` (`/admin`): tabela de **todas** as encomendas, filtro por grupo, e-mail do dono e abertura do detalhe (somente leitura, via `/admin/encomendas/{id}`). Sem botões de criar, editar ou excluir.
- `PaginaDetalheEncomenda` (`/encomendas/:id`): dados e histórico em linha do tempo. **(Parte cortável, ver cortes.)**
**Aceite:** o ADMIN vê todas e só consegue ler; o detalhe de encomenda alheia mostra "não encontrada" para o `USER`; a rota `/admin` e o link da transportadora não aparecem para o `USER`.

### T17 · Tela da transportadora, com login do ADMIN (M)
**Dia:** 01/12 · **Depende de:** T13
**Escopo:** `transportadora/app/static/index.html` e `app.js`, em HTML + Bootstrap + JavaScript puro, servidos por `StaticFiles`. Copiar o `bootstrap.min.css` do pacote npm para `static/` (a demonstração **não** pode depender de CDN). Usar **caminhos relativos** (`static/app.js`, `remessas`, `logs-webhook`, `autenticacao/login`).
**Conteúdo:**
- **Formulário de login** (e-mail e senha do ADMIN). O token fica em `sessionStorage` (`hooklog_token_transportadora`); resposta 401 volta para o formulário; botão "Sair".
- Tabela de remessas com **botão da próxima ação válida** (usa `proximo_status`; o último passo chama `/entregar`, com campo opcional "quem recebeu").
- Log de webhooks com as tentativas (sucesso, falha, retry nº N) e botão "reenviar".
- Atualização automática a cada 3 s; logo e paleta do `AGENTS.md`.
**Aceite:** pelo gateway (`/transportadora/`), sem login a página mostra só o formulário e nenhuma chamada de dados é feita; com a credencial do ADMIN, o ADMIN percorre o ciclo inteiro de uma remessa e vê os webhooks sendo enviados; um **`USER` comum não consegue entrar** (a credencial dele não vale aqui, 401).

---

## Fase 5: fechamento

### T18 · Teste ponta a ponta e cenários de demonstração (M)
**Dia:** 01 a 02/12 · **Depende de:** T13, T15, T17
**Escopo:** `scripts/e2e.py` (httpx assíncrono), rodando contra o Compose no ar.
**Cenários automatizados:**
1. Caminho feliz: registrar um `USER`, cadastrar encomenda, o ADMIN faz login na transportadora e percorre todos os status, a encomenda chega a `ENTREGUE` com `entregue_em`.
2. Webhook com assinatura inválida é rejeitado (401).
3. Evento duplicado é ignorado.
4. Usuário B não vê, edita nem apaga a encomenda de A.
5. **Papéis:** o ADMIN lista as encomendas de todos pelo Monitoramento, mas recebe 403 ao tentar criar uma; o USER recebe 403 em `/admin/encomendas`; o token do USER é rejeitado (401) na transportadora.
6. **Concorrência:** 20 cadastros simultâneos de códigos diferentes terminam todos em 201; 5 cadastros simultâneos do mesmo código dão um 201 e quatro 409; `GET /health` continua respondendo rápido durante a carga.
**Cenários manuais (documentar os comandos):**
7. Derrubar o Monitoramento, mudar status e ver o retry funcionar quando ele volta.
8. Derrubar a transportadora, cadastrar encomenda e ver o registro pendente resolver sozinho.
9. **Sem ADMIN:** remover `ADMIN_EMAIL` ou `ADMIN_SENHA` do `.env` e confirmar que `docker compose up` se recusa a subir, e que cada serviço, iniciado fora do Docker sem as variáveis, encerra com mensagem clara.
**Aceite:** o script termina com sucesso a partir de um ambiente limpo (`docker compose up --build`, com o `.env` preenchido); os cenários manuais estão documentados, com o passo a passo, em `scripts/cenarios_manuais.md` (o README final poderá reaproveitá-los).

---

## Extras (só se tudo estiver pronto, depois da T18)

### T19 · Extras, em ordem de prioridade (cada um é independente)
1. **Worker automático** da transportadora: avança os status por timer (tarefa `asyncio`), chamando a mesma lógica da T08 (nunca duplicar regra).
2. **SSE** no lugar do polling: `GET /stream` (`sse-starlette`) com registro de conexões por `usuario_id`, e `EventSource` no frontend. Lembrar que o `EventSource` nativo não envia `Authorization`.
3. Estado `FALHA_NA_ENTREGA` e estratégias de comportamento do simulador (rápido, lento, com falhas).

Cada extra precisa de testes e de uma linha no README. Não começar nenhum antes de a T18 estar concluída.

---

## Checklist final (04/12 e véspera da apresentação)

- [ ] `docker compose up --build` funciona a partir de um clone limpo, com `.env` criado do `.env.example` **e com `ADMIN_EMAIL` e `ADMIN_SENHA` preenchidos**.
- [ ] Sem `ADMIN_EMAIL` ou `ADMIN_SENHA`, o sistema se recusa a subir (cenário 9).
- [ ] Cenários 1 a 8 da T18 ensaiados, com o tempo que levam.
- [ ] Nenhum `def` síncrono em endpoints nem chamada bloqueante (revisão rápida com `grep` por `def ` em `app/api/`, `time.sleep` e `requests`).
- [ ] Swagger dos dois serviços abrindo (`/api/docs` e `/transportadora/docs`).
- [ ] Segredos e a senha do ADMIN do `.env` **não** estão no repositório.
- [ ] Nenhum `docker compose down -v` foi executado depois do ensaio final (os dados de demonstração estão preservados).
