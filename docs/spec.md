# HookLog: especificação

Versão 1.2 · 24/11/2026 · Desenvolvimento: 24/11 a 04/12/2026 · Apresentação: 12/12/2026

## 1. Visão geral

O HookLog permite que um usuário cadastre as encomendas que está esperando e acompanhe o andamento de cada uma. O andamento vem de um serviço independente que **simula uma transportadora**: quando o ADMIN muda o status de uma remessa (ou finaliza a entrega) pela tela da transportadora, o simulador envia um **webhook assinado** ao serviço de Monitoramento, que atualiza o banco. O navegador do usuário descobre a mudança por **polling** (a cada 5 s) no próprio Monitoramento.

Objetivos acadêmicos que o projeto demonstra:

- Comunicação entre serviços por **API REST** e por **webhooks**.
- **Bancos separados** por serviço (nenhum acessa o banco do outro).
- **Segurança por canal**: JWT + controle de acesso por papel para as pessoas, chave de API entre serviços, HMAC + timestamp no webhook.
- **Tolerância a falhas**: retry com backoff, filas em banco, idempotência, registro pendente.

### Peças

| Peça | Responsabilidade |
|---|---|
| Frontend (React) | Login, registro, CRUD das encomendas do `USER` em três abas, detalhe e a lista geral do `ADMIN` |
| Monitoramento (FastAPI + PostgreSQL) | Autenticação, controle de acesso, encomendas, recebimento de webhooks, registro na transportadora |
| Transportadora (FastAPI + PostgreSQL) | Remessas, mudança de status, fila e envio de webhooks, login do ADMIN e tela do ADMIN |
| Gateway (nginx) | Porta única: `/` frontend, `/api/` Monitoramento, `/transportadora/` simulador |

```mermaid
sequenceDiagram
    actor U as USER
    participant F as Frontend
    participant M as Monitoramento
    participant T as Transportadora
    actor A as ADMIN

    U->>F: Cadastra encomenda
    F->>M: POST /encomendas (JWT do USER)
    M->>T: POST /remessas (chave de API do serviço)
    T-->>M: 201 remessa registrada
    M-->>F: 201 (AGUARDANDO_ENVIO)
    A->>T: POST /remessas/{código}/status (JWT do ADMIN)
    T->>T: Atualiza remessa e grava evento (mesma transação)
    T->>M: POST /webhooks/transportadora (HMAC)
    M->>M: Valida assinatura, idempotência e transição
    M-->>T: 200
    F->>M: GET /encomendas (polling, 5 s)
    M-->>F: Lista com o novo status
```

## 2. Atores e papéis

O sistema tem **apenas dois tipos de usuário**: `USER` e `ADMIN`.

| Ator | Descrição | Permissões |
|---|---|---|
| Visitante | Ainda sem login | Registrar-se e fazer login |
| `USER` | Cadastrado pela tela de registro; salvo no banco do Monitoramento | **CRUD das próprias encomendas**: criar, listar, ver detalhe, editar descrição e vendedor, excluir (e pedir novo registro). Não acessa a transportadora |
| `ADMIN` | **Mockado** por `ADMIN_EMAIL` e `ADMIN_SENHA` no `.env`; não existe no banco | **Ver as encomendas de todos os usuários** (somente leitura) e **único acesso à tela da transportadora**, por login. Não cria, edita nem exclui encomendas |

Atores técnicos (não são usuários):

| Ator | Como se autentica |
|---|---|
| Serviço Monitoramento (chamando a transportadora) | Chave de API de serviço (`X-Chave-Api`) |
| Serviço Transportadora (chamando o webhook) | Assinatura HMAC + timestamp |

### Matriz de acesso

| Recurso | Visitante | `USER` | `ADMIN` |
|---|---|---|---|
| `POST /autenticacao/registro`, `POST /autenticacao/login` | sim | sim | sim |
| `/encomendas` (criar, listar, ver, editar, excluir, registrar) | não | **sim (só as suas)** | não (403) |
| `/admin/encomendas` (listar e ver todas) | não | não (403) | **sim (leitura)** |
| Tela e API da transportadora (exceto `POST /remessas`) | não | não | **sim, com login próprio** |
| `POST /remessas` | não | não | não (só a chave de serviço) |

## 3. Inicialização e o ADMIN obrigatório

**O sistema não pode ser executado sem a criação prévia do ADMIN.**

1. O usuário copia `.env.example` para `.env` e **preenche `ADMIN_EMAIL` e `ADMIN_SENHA`** (os valores vêm em branco no exemplo, de propósito).
2. O `docker-compose.yml` exige as duas variáveis (`${ADMIN_EMAIL:?...}` e `${ADMIN_SENHA:?...}`); sem elas, `docker compose up` falha com mensagem clara, antes de subir qualquer contêiner.
3. Cada serviço valida as variáveis ao iniciar (`Configuracao`, sem valor padrão): e-mail válido e senha com no mínimo 8 caracteres. Se faltar ou for inválido, o processo **encerra com código diferente de zero** e uma mensagem indicando o que corrigir.
4. Os dois serviços usam a **mesma credencial**, mas emitem **tokens independentes** (segredos JWT diferentes).

## 4. Requisitos funcionais

Prioridade: **M** = MVP, **E** = extra (só depois do MVP).

### Monitoramento

| ID | Requisito | Pri. |
|---|---|---|
| RF01 | O visitante pode se registrar como `USER` com e-mail e senha | M |
| RF02 | `USER` e `ADMIN` fazem login e recebem um token JWT; o logout descarta o token no frontend | M |
| RF03 | O acesso é controlado por papel: `USER` só opera as próprias encomendas e `ADMIN` só lê todas (ver matriz de acesso) | M |
| RF04 | O `USER` pode cadastrar uma encomenda (código de rastreio, descrição, vendedor) | M |
| RF05 | Ao cadastrar, o sistema registra a remessa na transportadora. Se ela estiver indisponível, a encomenda fica `REGISTRO_PENDENTE` e é registrada depois, automaticamente | M |
| RF06 | O `USER` pode listar as próprias encomendas, com o grupo (aba) de cada uma | M |
| RF07 | O `USER` pode ver os detalhes de uma encomenda e o histórico de mudanças de status | M |
| RF08 | O `USER` pode **editar** a descrição e o vendedor de uma encomenda (o código de rastreio não muda) | M |
| RF09 | O `USER` pode excluir as próprias encomendas | M |
| RF10 | O `USER` pode pedir um novo registro de uma encomenda em `FALHA_NO_REGISTRO` | M |
| RF11 | O sistema recebe webhooks, valida a assinatura, aplica a mudança de status e grava o histórico | M |
| RF12 | O sistema ignora eventos duplicados (mesmo `id_evento`) e rejeita transições inválidas | M |
| RF13 | Nas encomendas entregues, o sistema exibe vendedor e data e hora da entrega (horário de Brasília) | M |
| RF14 | O `ADMIN` pode listar as encomendas de **todos** os usuários (com o e-mail do dono) e abrir o detalhe de qualquer uma, sem poder alterá-las | M |
| RF15 | A interface atualiza a lista sozinha por polling a cada 5 s | M |
| RF16 | O sistema oferece `GET /health` | M |
| RF17 | O serviço **não inicia** sem `ADMIN_EMAIL` e `ADMIN_SENHA` válidos (seção 3) | M |

### Transportadora

| ID | Requisito | Pri. |
|---|---|---|
| RF18 | Registrar remessa (código, vendedor, URL de callback), de forma idempotente por código, usando a chave de API de serviço | M |
| RF19 | O `ADMIN` logado consulta e lista as remessas | M |
| RF20 | O `ADMIN` muda o status manualmente, validando a sequência permitida | M |
| RF21 | O `ADMIN` finaliza a entrega, registrando data e hora (e, opcionalmente, quem recebeu) | M |
| RF22 | A cada mudança, gerar um evento de webhook na **mesma transação** da mudança | M |
| RF23 | Enviar o webhook assinado (HMAC-SHA256 + timestamp) com retry e backoff exponencial | M |
| RF24 | Registrar cada tentativa de envio (resultado, código HTTP, erro) e permitir consultar o log | M |
| RF25 | Reenviar manualmente um evento (demonstra a idempotência) | M |
| RF26 | Login do `ADMIN` na transportadora (mesma credencial do `.env`), emitindo um token próprio; é o **único** acesso à tela | M |
| RF27 | Tela do ADMIN: tabela de remessas, botão com a próxima ação válida, log de webhooks, reenvio e login | M |
| RF28 | Worker automático que avança os status sozinho, por timer | E |
| RF29 | SSE no lugar do polling | E |

## 5. Regras de negócio

- **RN01** O código de rastreio é **único globalmente** no Monitoramento (não por usuário), pois é a chave que o webhook usa para achar a encomenda. Depois de cadastrado, **não pode ser alterado**.
- **RN02** O `USER` nunca acessa encomendas de outro. Acesso a recurso alheio devolve **404**.
- **RN03** O status só avança (ver seção 6). Evento com status igual ou anterior ao atual é rejeitado com 409.
- **RN04** O cadastro de encomenda **sempre é salvo**, mesmo com a transportadora fora do ar (status `REGISTRO_PENDENTE`).
- **RN05** `POST /remessas` na transportadora é **idempotente** por `codigo_rastreio`: repetir devolve a remessa existente (200).
- **RN06** Um mesmo `id_evento` é processado **no máximo uma vez** pelo Monitoramento. Repetição devolve 200 sem alterar nada.
- **RN07** O `ADMIN` é **único**, mockado por `.env`, **não persistido** e sem rota de cadastro. O sistema não inicia sem ele (seção 3).
- **RN08** E-mails de `USER` são salvos em minúsculas; senhas têm no mínimo 8 caracteres. O `ADMIN_EMAIL` **não pode** ser registrado como `USER` (409 `EMAIL_JA_CADASTRADO`).
- **RN09** O `ADMIN` é **somente leitura** sobre encomendas: não cria, edita nem exclui. Rotas de CRUD exigem o papel `USER` (o ADMIN recebe 403 `ACESSO_NEGADO`). Rotas `/admin/*` exigem `ADMIN` (o USER recebe 403).
- **RN10** Excluir uma encomenda **não** cancela a remessa na transportadora (não há cancelamento). Webhooks posteriores recebem 404 e não são reenviados.
- **RN11** Data e hora trafegam em UTC (ISO 8601 com `Z`); só o frontend converte para `America/Sao_Paulo`.
- **RN12** Na transportadora, a entrega (`ENTREGUE`) só acontece por `POST /remessas/{código}/entregar`, e só a partir de `SAIU_PARA_ENTREGA`. O horário da entrega é o do servidor.
- **RN13** Editar uma encomenda altera só o dado **local** (descrição e vendedor). A cópia do vendedor guardada na transportadora não é atualizada, e o campo `vendedor` do webhook **não** sobrescreve o dado local.

## 6. Máquina de estados

Sequência normal:

`AGUARDANDO_ENVIO -> POSTADO -> EM_TRANSITO -> SAIU_PARA_ENTREGA -> ENTREGUE`

Estados exclusivos do Monitoramento (antes de a remessa existir na transportadora): `REGISTRO_PENDENTE` e `FALHA_NO_REGISTRO`.

### Ordem dos estados

| Status | Ordem | Aba (grupo) |
|---|---|---|
| `REGISTRO_PENDENTE` | 0 | `nao_encaminhadas` |
| `FALHA_NO_REGISTRO` | 0 | `nao_encaminhadas` |
| `AGUARDANDO_ENVIO` | 1 | `nao_encaminhadas` |
| `POSTADO` | 2 | `nao_encaminhadas` |
| `EM_TRANSITO` | 3 | `a_caminho` |
| `SAIU_PARA_ENTREGA` | 4 | `a_caminho` |
| `ENTREGUE` | 5 | `entregues` |

### Regra na Transportadora (ADMIN)

Só é permitido o **próximo** status da sequência, sem pular nem voltar. `ENTREGUE` só por `/entregar`. Qualquer outra tentativa devolve **409 `TRANSICAO_INVALIDA`**.

### Regra no Monitoramento (webhook)

O evento é aplicado se a **ordem do status do evento for maior** que a ordem do status atual da encomenda. Isso tolera um evento intermediário perdido (por exemplo, chega `EM_TRANSITO` com a encomenda ainda em `AGUARDANDO_ENVIO`) e também cobre o caso de a encomenda estar em `REGISTRO_PENDENTE` quando o primeiro evento chega. Igual ou menor: **409 `TRANSICAO_INVALIDA`**.

### Transições do registro (apenas Monitoramento)

| De | Para | Quando |
|---|---|---|
| (novo) | `AGUARDANDO_ENVIO` | Registro na transportadora deu certo na hora |
| (novo) | `REGISTRO_PENDENTE` | Transportadora indisponível (timeout, conexão recusada, 5xx) |
| `REGISTRO_PENDENTE` | `AGUARDANDO_ENVIO` | A rotina conseguiu registrar |
| `REGISTRO_PENDENTE` | `FALHA_NO_REGISTRO` | Esgotou as tentativas, ou erro permanente (401, 403, 422) |
| `FALHA_NO_REGISTRO` | `REGISTRO_PENDENTE` | O `USER` pediu novo registro (`POST /encomendas/{id}/registrar`) |

## 7. Fluxos

### 7.1 Cadastro de encomenda

1. `POST /encomendas` com JWT válido de um `USER`.
2. O Monitoramento valida os dados e confere a unicidade do código (409 se repetido).
3. Salva a encomenda como `REGISTRO_PENDENTE` com `tentativas_registro = 0` e grava a primeira linha do histórico.
4. Tenta registrar a remessa na transportadora (timeout curto, 3 s). Essa é a tentativa 1.
5. Sucesso: status `AGUARDANDO_ENVIO`, campos da fila zerados, linha de histórico. Resposta **201**.
6. Falha transitória: `tentativas_registro = 1` e `proxima_tentativa_em` calculada com backoff. Resposta **201** com status `REGISTRO_PENDENTE`.
7. Falha permanente (401, 403, 422 da transportadora): status `FALHA_NO_REGISTRO`. Resposta **201**.

### 7.2 Registro pendente (rotina em segundo plano, banco como fila)

Uma **tarefa `asyncio`** (corrotina em laço) iniciada no `lifespan` roda a cada `INTERVALO_ROTINA_REGISTRO_SEGUNDOS` e processa as encomendas `REGISTRO_PENDENTE` com `proxima_tentativa_em <= agora` **em paralelo** (até `CONCORRENCIA_MAXIMA_REGISTRO` por vez, cada uma com a sua sessão). Para cada encomenda:

- Sucesso: `AGUARDANDO_ENVIO`.
- Falha transitória: incrementa `tentativas_registro`. Se chegou a `MAX_TENTATIVAS_REGISTRO`, vira `FALHA_NO_REGISTRO`; senão `proxima_tentativa_em = agora + min(base * 2^(n-1), teto)`.
- Falha permanente: `FALHA_NO_REGISTRO`.

### 7.3 Mudança de status e webhook

1. O `ADMIN`, logado na tela da transportadora, chama `POST /remessas/{código}/status` (ou `/entregar`).
2. **Em uma transação**: atualiza a remessa e insere um `eventos_webhook` `PENDENTE` com o corpo JSON já serializado (padrão *transactional outbox*).
3. A rotina da transportadora (tarefa `asyncio`) pega os eventos `PENDENTE` com `proxima_tentativa_em <= agora`, em ordem de criação, e envia **vários em paralelo** (até `CONCORRENCIA_MAXIMA_WEBHOOK`, cada um com a sua sessão). Um evento só é enviado se **não houver evento mais antigo da mesma remessa ainda `PENDENTE`** (preserva a ordem).
4. Para cada tentativa: monta `X-Carimbo-Tempo` e `X-Assinatura` **novos**, faz o `POST` e grava uma linha em `tentativas_webhook`.
5. Resultado: 2xx marca `ENVIADO`. 4xx (exceto 408 e 429) marca `FALHA` na hora, sem retry. Falha de rede, timeout, 5xx, 408 ou 429: incrementa `total_tentativas`; se chegou a `MAX_TENTATIVAS_WEBHOOK`, `FALHA`; senão `proxima_tentativa_em = agora + base * 2^(n-1)`.
6. O Monitoramento (RF11 e RF12) valida a assinatura, o timestamp, a idempotência e a transição, grava o histórico e responde.

### 7.4 Falha e recuperação (cenário de demonstração)

1. Derrubar o Monitoramento. 2. O ADMIN muda um status na tela da transportadora. 3. O log mostra as tentativas falhando com backoff. 4. Subir o Monitoramento. 5. A próxima tentativa dá certo, o evento fica `ENVIADO` e a interface do USER mostra o novo status.

## 8. Requisitos não funcionais

| Categoria | Requisito |
|---|---|
| Segurança | Senhas de `USER` com argon2; JWT com expiração; credencial do ADMIN comparada em tempo constante; HMAC-SHA256 sobre o corpo bruto com timestamp (tolerância de 300 s, contra replay); chave de API comparada em tempo constante; segredos só em variáveis de ambiente; validação de entrada com Pydantic; recurso alheio devolve 404 |
| Confiabilidade | Retry com backoff nos dois sentidos; recebimento idempotente; filas persistidas em banco (sobrevivem a reinício); a queda de um serviço não derruba o outro |
| Consistência | Consistência eventual entre os serviços; evento duplicado, atrasado ou fora de ordem não corrompe o estado |
| Desempenho (meta para a demo) | Respostas da API abaixo de 500 ms; webhook processado em cerca de 1 s; mudança visível na tela em até 5 s |
| **Concorrência** | **Todo o sistema é assíncrono, com corrotinas (`async def`)**: endpoints, acesso ao banco (`asyncpg`) e chamadas HTTP (`httpx.AsyncClient`). Um processo atende várias requisições simultâneas, e as rotinas em segundo plano processam itens em paralelo com limite. Nenhuma chamada bloqueia o laço de eventos |
| Usabilidade | Interface responsiva (Bootstrap); mensagens de erro claras em português; selos com texto (não só cor); datas em horário de Brasília |
| Manutenibilidade | Camadas `api -> services -> repositories -> models`; migrações Alembic; código tipado; lint com ruff; **nomes em português** (regra do `AGENTS.md`) |
| Portabilidade | `docker compose up --build` sobe tudo (com o `.env` preenchido); configuração por `.env` |
| Observabilidade | Logs com `id_evento` e `codigo_rastreio`; `GET /health` em cada serviço; histórico de tentativas de webhook consultável |
| Documentação | OpenAPI automático (`/docs`); README com diagrama e roteiro da demonstração |
| Testabilidade | pytest + pytest-asyncio cobrindo autenticação, papéis, isolamento entre usuários, HMAC, idempotência, transições, rotinas em segundo plano, **cenários de concorrência** e a recusa de iniciar sem ADMIN |

### Modelo de concorrência

- **Uma corrotina por requisição.** O Uvicorn atende todas no mesmo laço de eventos; enquanto uma espera o banco ou outro serviço, as demais seguem.
- **Sessão do banco por requisição ou por tarefa** (nunca compartilhada entre corrotinas concorrentes).
- **Pontos de corrida e como são resolvidos:**

| Situação | Resolução |
|---|---|
| Dois cadastros simultâneos do mesmo `codigo_rastreio` | Restrição `UNIQUE`: um recebe 201, o outro 409 `CODIGO_RASTREIO_DUPLICADO` |
| Dois webhooks simultâneos com o mesmo `id_evento` | PK em `eventos_processados`: um `aplicado`, o outro `duplicado` |
| Dois webhooks simultâneos de eventos diferentes da mesma encomenda | Linha da encomenda bloqueada com `with_for_update()` antes de comparar a ordem dos status |
| Dois cliques simultâneos do ADMIN na mesma remessa | Linha da remessa bloqueada com `with_for_update()`: um muda o status e gera **um** evento, o outro recebe 409 `TRANSICAO_INVALIDA` |
| Dois `POST /remessas` simultâneos do mesmo código | Restrição `UNIQUE`: um 201, o outro 200 com a remessa existente |

- **Rotinas em segundo plano** são tarefas `asyncio` com paralelismo limitado por `Semaphore`.
- **Trabalho de CPU** (hash argon2) roda em `asyncio.to_thread`, para não travar as demais requisições.

## 9. Configuração (variáveis de ambiente)

Valores de exemplo vão no `.env.example`. Segredos reais ficam no `.env` (fora do git). **`ADMIN_EMAIL` e `ADMIN_SENHA` vêm em branco no exemplo e são obrigatórios.**

### Compartilhadas (raiz, lidas pelo Compose)

| Variável | Uso |
|---|---|
| `ADMIN_EMAIL` | **Obrigatória.** E-mail do ADMIN mockado |
| `ADMIN_SENHA` | **Obrigatória.** Senha do ADMIN mockado (mínimo 8 caracteres) |
| `SENHA_BANCO_MONITORAMENTO` | Senha do Postgres do Monitoramento |
| `SENHA_BANCO_TRANSPORTADORA` | Senha do Postgres da transportadora (**diferente** da outra) |
| `SEGREDO_WEBHOOK` | Segredo HMAC, igual nos dois serviços |
| `CHAVE_API_SERVICO` | Chave que o Monitoramento usa na transportadora |
| `SEGREDO_JWT_MONITORAMENTO` | Assinatura dos tokens do Monitoramento |
| `SEGREDO_JWT_TRANSPORTADORA` | Assinatura dos tokens da transportadora (**diferente** do outro) |

### Monitoramento

| Variável | Padrão | Uso |
|---|---|---|
| `ADMIN_EMAIL`, `ADMIN_SENHA` | (sem padrão) | Obrigatórias; o serviço não inicia sem elas |
| `URL_BANCO` | `postgresql+asyncpg://usuario_monitoramento:...@monitoramento-db:5432/monitoramento` | Conexão |
| `CAMINHO_RAIZ` | `/api` | Prefixo do gateway (para o Swagger) |
| `SEGREDO_JWT` | = `SEGREDO_JWT_MONITORAMENTO` | Assinatura dos tokens |
| `MINUTOS_EXPIRACAO_TOKEN` | `60` | Validade do JWT |
| `SEGREDO_WEBHOOK` | (segredo) | Verificação do HMAC |
| `TOLERANCIA_TIMESTAMP_WEBHOOK_SEGUNDOS` | `300` | Janela do timestamp |
| `URL_TRANSPORTADORA` | `http://transportadora:8001` | Base da API da transportadora |
| `CHAVE_API_TRANSPORTADORA` | = `CHAVE_API_SERVICO` | Header `X-Chave-Api` |
| `TIMEOUT_TRANSPORTADORA_SEGUNDOS` | `3` | Timeout do registro |
| `URL_PUBLICA_WEBHOOK` | `http://monitoramento:8000/webhooks/transportadora` | Callback enviado à transportadora |
| `INTERVALO_ROTINA_REGISTRO_SEGUNDOS` | `5` | Frequência da rotina |
| `MAX_TENTATIVAS_REGISTRO` | `8` | Tentativas de registro |
| `BASE_BACKOFF_REGISTRO_SEGUNDOS` | `5` | Base do backoff |
| `TETO_BACKOFF_REGISTRO_SEGUNDOS` | `60` | Teto do backoff |
| `CONCORRENCIA_MAXIMA_REGISTRO` | `5` | Registros simultâneos na rotina |
| `TAMANHO_POOL_BANCO` | `10` | Conexões do pool do banco |

### Transportadora

| Variável | Padrão | Uso |
|---|---|---|
| `ADMIN_EMAIL`, `ADMIN_SENHA` | (sem padrão) | Obrigatórias; o serviço não inicia sem elas |
| `URL_BANCO` | `postgresql+asyncpg://usuario_transportadora:...@transportadora-db:5432/transportadora` | Conexão |
| `CAMINHO_RAIZ` | `/transportadora` | Prefixo do gateway |
| `SEGREDO_JWT` | = `SEGREDO_JWT_TRANSPORTADORA` | Assinatura dos tokens |
| `MINUTOS_EXPIRACAO_TOKEN` | `60` | Validade do JWT |
| `CHAVE_API_SERVICO` | (segredo) | Autentica o Monitoramento em `POST /remessas` |
| `SEGREDO_WEBHOOK` | (segredo) | Assinatura do webhook |
| `MAX_TENTATIVAS_WEBHOOK` | `5` | Tentativas por evento |
| `BASE_BACKOFF_WEBHOOK_SEGUNDOS` | `1` | Atrasos de 1, 2, 4, 8 s |
| `INTERVALO_ROTINA_WEBHOOK_SEGUNDOS` | `1` | Frequência da rotina |
| `TIMEOUT_ENVIO_WEBHOOK_SEGUNDOS` | `5` | Timeout do envio |
| `CONCORRENCIA_MAXIMA_WEBHOOK` | `5` | Envios simultâneos na rotina |
| `TAMANHO_POOL_BANCO` | `10` | Conexões do pool do banco |

### Portas

| Serviço | Porta interna | Exposta ao host |
|---|---|---|
| Gateway | 80 | `8080` (única do Compose final) |
| Monitoramento | 8000 | só em dev |
| Transportadora | 8001 | só em dev |
| Postgres (Monitoramento) | 5432 | `5433` só no `docker-compose.override.yml` |
| Postgres (transportadora) | 5432 | `5434` só no `docker-compose.override.yml` |

## 10. Fora do escopo

- Cancelamento de remessa, múltiplas transportadoras, cálculo de frete, notificações por e-mail.
- Mais de um ADMIN, cadastro ou troca de senha do ADMIN pela interface (muda-se o `.env` e reinicia-se).
- Refresh token, recuperação de senha, confirmação de e-mail.
- Múltiplas instâncias do backend (as filas em banco assumem uma instância por serviço).
- Modo escuro.

Limitação conhecida e aceita para o projeto acadêmico: a senha do ADMIN fica em texto no `.env`. Em produção, seria um hash (ou um provedor de identidade) e um gerenciador de segredos.

## 11. Extras (somente após o MVP)

Em ordem de prioridade: worker automático da transportadora (RF28), SSE no lugar do polling (RF29), estado `FALHA_NA_ENTREGA`, estratégias de comportamento do simulador (rápido, lento, com falhas).

Se o prazo apertar, corte nesta ordem: extras acima e a página de detalhe com linha do tempo (T16, parte do detalhe do `USER`) e o script automatizado de ponta a ponta (T18, mantendo o roteiro manual). **Nunca cortar**: o CRUD completo do `USER` (inclusive a edição), a visão geral do `ADMIN`, HMAC, retry com backoff, idempotência, registro pendente e a exigência do ADMIN na inicialização.
