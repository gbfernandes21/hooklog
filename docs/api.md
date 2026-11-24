# HookLog: contrato das APIs

Versão 1.2 · 24/11/2026

As rotas abaixo são as do FastAPI, **sem** o prefixo do gateway. No navegador, o Monitoramento aparece em `/api/...` e a transportadora em `/transportadora/...`. A comunicação entre os serviços usa a rede interna do Docker e **não** passa pelo gateway.

## 1. Convenções

### Idioma

Rotas, campos JSON, cabeçalhos e códigos de erro estão em português. **Exceções impostas por protocolo ou framework:** `username` e `password` no formulário de login, `access_token` e `token_type` na resposta de login (OAuth2), `/health`, `/docs` e o 422 de validação do FastAPI (`{"detail": [...]}`).

### Formato de erro

Todo erro de domínio devolve:

```json
{ "detalhe": "Mensagem legível", "codigo": "CODIGO_DO_ERRO" }
```

### Datas

ISO 8601 em UTC, terminando em `Z`: `2026-11-18T17:42:10Z`.

### Autenticação por rota

| Serviço | Quem | Mecanismo | Cabeçalho |
|---|---|---|---|
| Monitoramento | `USER` e `ADMIN` | JWT do Monitoramento | `Authorization: Bearer <token>` |
| Monitoramento (webhook) | Transportadora | HMAC-SHA256 + timestamp | `X-Assinatura`, `X-Carimbo-Tempo` |
| Transportadora | `ADMIN` | JWT **da transportadora** (login próprio) | `Authorization: Bearer <token>` |
| Transportadora | Monitoramento | Chave de API de serviço | `X-Chave-Api: <chave>` |

Os dois JWT são **independentes**: cada serviço usa o seu segredo, então um token do Monitoramento é inválido na transportadora e vice-versa.

### Concorrência

Todos os endpoints são `async def` e atendem requisições simultâneas. Efeitos observáveis no contrato:

- Cadastros simultâneos do mesmo `codigo_rastreio`: um 201 e os demais 409.
- `POST /remessas` simultâneos do mesmo código: um 201 e os demais 200 (remessa existente).
- Webhooks simultâneos com o mesmo `id_evento`: um `aplicado` e os demais `duplicado`.
- Mudanças de status simultâneas na mesma remessa: uma 200 e as demais 409 `TRANSICAO_INVALIDA`, com **um** único evento gerado.

### Valores de status (contrato compartilhado)

`REGISTRO_PENDENTE`, `FALHA_NO_REGISTRO`, `AGUARDANDO_ENVIO`, `POSTADO`, `EM_TRANSITO`, `SAIU_PARA_ENTREGA`, `ENTREGUE`.

Grupos (campo `grupo`, calculado pelo Monitoramento): `nao_encaminhadas` (`REGISTRO_PENDENTE`, `FALHA_NO_REGISTRO`, `AGUARDANDO_ENVIO`, `POSTADO`), `a_caminho` (`EM_TRANSITO`, `SAIU_PARA_ENTREGA`), `entregues` (`ENTREGUE`).

### Significado dos status codes

| Código | Quando usar neste projeto |
|---|---|
| 200 | Deu certo e há corpo de resposta |
| 201 | Recurso novo criado |
| 202 | Pedido aceito, o trabalho termina depois (nova tentativa de registro, reenvio de webhook) |
| 204 | Deu certo, sem corpo (`DELETE`) |
| 401 | Não autenticado: token, chave de API ou assinatura ausente, inválida ou expirada |
| 403 | Autenticado, mas o papel não permite a ação |
| 404 | Recurso inexistente. Para recurso de **outro usuário**, também 404 |
| 409 | Conflito com o estado atual: duplicidade ou transição de status inválida |
| 422 | Corpo ou parâmetros inválidos (validação Pydantic) |
| 500 | Erro inesperado. Nunca expor detalhes internos |
| 503 | Dependência fora do ar (`/health` com banco indisponível) |

---

## 2. Monitoramento

### 2.0 Quem pode chamar o quê

| Rotas | `USER` | `ADMIN` | Sem token |
|---|---|---|---|
| `/autenticacao/registro`, `/autenticacao/login` | sim | sim | sim |
| `/autenticacao/eu` | sim | sim | 401 |
| `/encomendas` e `/encomendas/{id}...` | **sim (só as suas)** | **403** `ACESSO_NEGADO` | 401 |
| `/admin/encomendas...` | **403** `ACESSO_NEGADO` | **sim (leitura)** | 401 |

### 2.1 Autenticação

#### `POST /autenticacao/registro`

Público. Sempre cria um `USER`.

```json
// requisição
{ "email": "ana@exemplo.com", "senha": "minhasenha123" }
```
```json
// 201
{ "id": 1, "email": "ana@exemplo.com", "papel": "USER", "criado_em": "2026-11-22T12:00:00Z" }
```

Erros: **409** `EMAIL_JA_CADASTRADO` (e-mail já existente, **inclusive o `ADMIN_EMAIL`**) · **422** (e-mail inválido, senha com menos de 8 caracteres).

#### `POST /autenticacao/login`

Público. Corpo **`application/x-www-form-urlencoded`** (padrão OAuth2, para o botão *Authorize* do Swagger funcionar): `username` (o e-mail) e `password`.

Ordem da verificação:

1. Se o e-mail (em minúsculas) for o `ADMIN_EMAIL`, a senha é comparada com `ADMIN_SENHA` (`secrets.compare_digest`), **sem consultar o banco**. O token emitido tem `sub = "admin"` e `papel = "ADMIN"`.
2. Senão, procura o `USER` no banco e verifica a senha (argon2). O token tem `sub = <id>` e `papel = "USER"`.

```json
// 200
{ "access_token": "eyJhbGciOi...", "token_type": "bearer" }
```

Erros: **401** `CREDENCIAIS_INVALIDAS` (mesma mensagem para e-mail inexistente e senha errada, inclusive no caminho do ADMIN) · **422**.

#### `GET /autenticacao/eu`

`USER` ou `ADMIN`. **200**: `{ "id": 1, "email": "ana@exemplo.com", "papel": "USER" }`. Para o `ADMIN`, `id` é `null`.

Erros: **401** `TOKEN_INVALIDO` ou `TOKEN_EXPIRADO`.

### 2.2 Encomendas (somente `USER`, só as próprias)

Objeto **Encomenda**:

```json
{
  "id": 12,
  "codigo_rastreio": "BR123456789",
  "descricao": "Fone de ouvido",
  "vendedor": "Loja Exemplo LTDA",
  "status": "EM_TRANSITO",
  "grupo": "a_caminho",
  "entregue_em": null,
  "criado_em": "2026-11-18T14:00:00Z",
  "atualizado_em": "2026-11-18T14:30:00Z"
}
```

#### `POST /encomendas` (Create)

O `codigo_rastreio` é normalizado para maiúsculas, sem espaços nas pontas.

```json
// requisição
{ "codigo_rastreio": "BR123456789", "descricao": "Fone de ouvido", "vendedor": "Loja Exemplo LTDA" }
```

Validações: `codigo_rastreio` 5 a 40 caracteres, apenas letras, números e hífen; `descricao` 1 a 200; `vendedor` 1 a 120.

**201**: objeto Encomenda. O `status` pode ser `AGUARDANDO_ENVIO` (registrou na hora), `REGISTRO_PENDENTE` (transportadora indisponível) ou `FALHA_NO_REGISTRO` (erro permanente). Ver `docs/spec.md`, seção 7.1.

Erros: **401** · **403** (ADMIN) · **409** `CODIGO_RASTREIO_DUPLICADO` · **422**.

#### `GET /encomendas?grupo=` (Read, lista)

Lista **só as do usuário logado**, da mais recente para a mais antiga. `grupo` é opcional: `nao_encaminhadas`, `a_caminho` ou `entregues`.

**200**: lista de Encomenda. Erros: **401** · **403** · **422** (grupo inválido).

#### `GET /encomendas/{id}` (Read, detalhe)

**200**: Encomenda + `historico`:

```json
{
  "id": 12, "codigo_rastreio": "BR123456789", "status": "ENTREGUE", "grupo": "entregues",
  "descricao": "Fone de ouvido", "vendedor": "Loja Exemplo LTDA",
  "entregue_em": "2026-11-18T17:42:10Z", "criado_em": "...", "atualizado_em": "...",
  "historico": [
    { "status_anterior": null, "status_novo": "AGUARDANDO_ENVIO", "ocorrido_em": "2026-11-18T14:00:01Z" },
    { "status_anterior": "AGUARDANDO_ENVIO", "status_novo": "POSTADO", "ocorrido_em": "2026-11-18T14:30:00Z" }
  ]
}
```

O histórico vem em ordem cronológica. Erros: **401** · **403** · **404** `ENCOMENDA_NAO_ENCONTRADA` (inclusive se for de outro usuário).

#### `PATCH /encomendas/{id}` (Update)

Edita **apenas** `descricao` e/ou `vendedor`. Pelo menos um dos dois deve vir. O código de rastreio e o status **não** mudam por aqui.

```json
// requisição (campos opcionais)
{ "descricao": "Fone de ouvido bluetooth", "vendedor": "Loja Exemplo" }
```

Mesmas validações do cadastro. Não altera a remessa na transportadora (ver RN13).

**200**: objeto Encomenda atualizado (`atualizado_em` muda). Erros: **401** · **403** · **404** · **422** (corpo vazio, campo inválido, ou tentativa de enviar `codigo_rastreio` ou `status`).

#### `DELETE /encomendas/{id}` (Delete)

**204**, sem corpo. Apaga também o histórico. Não cancela a remessa na transportadora. Erros: **401** · **403** · **404**.

#### `POST /encomendas/{id}/registrar`

Pede novo registro de uma encomenda em `FALHA_NO_REGISTRO`: volta para `REGISTRO_PENDENTE`, zera as tentativas e agenda a rotina para agora. Sem corpo.

**202**: objeto Encomenda (`status: "REGISTRO_PENDENTE"`). Erros: **401** · **403** · **404** · **409** `ESTADO_INVALIDO` (a encomenda não está em `FALHA_NO_REGISTRO`).

### 2.3 Visão do ADMIN (somente leitura)

#### `GET /admin/encomendas?grupo=&usuario_id=`

Somente `ADMIN`. Lista de **todas** as encomendas; cada item é uma Encomenda com `usuario_id` e `usuario_email`. Filtros opcionais.

Erros: **401** · **403** `ACESSO_NEGADO` (USER) · **422**.

#### `GET /admin/encomendas/{id}`

Somente `ADMIN`. **200**: Encomenda + `historico` + `usuario_id` e `usuario_email`. Erros: **401** · **403** · **404** `ENCOMENDA_NAO_ENCONTRADA`.

Não existem rotas de criação, edição ou exclusão para o ADMIN.

### 2.4 Webhook (recebimento)

#### `POST /webhooks/transportadora`

Não usa JWT. Autenticada por **assinatura HMAC** (seção 4). **Não é exposta pelo gateway** (o nginx devolve 404 para `/api/webhooks/`); só a transportadora a alcança, pela rede interna.

Ordem das verificações:

1. `X-Carimbo-Tempo` e `X-Assinatura` presentes, timestamp dentro da tolerância e assinatura correta, senão **401** `ASSINATURA_INVALIDA`.
2. Corpo válido (schema do evento), senão **422**.
3. `id_evento` já processado: **200** `{"resultado": "duplicado"}`, sem alterar nada.
4. Encomenda com aquele `codigo_rastreio`, senão **404** `ENCOMENDA_NAO_ENCONTRADA`.
5. Ordem do status do evento maior que a do status atual, senão **409** `TRANSICAO_INVALIDA`.
6. Aplica: atualiza status (e `entregue_em` se for entrega), grava o histórico e o `id_evento` em `eventos_processados`, tudo na mesma transação. **200** `{"resultado": "aplicado"}`.

Se dois eventos com o mesmo `id_evento` chegarem ao mesmo tempo, a violação de chave primária em `eventos_processados` deve ser tratada como duplicado (**200** `duplicado`).

### 2.5 Saúde

`GET /health`: **200** `{"status": "ok", "servico": "monitoramento"}`. **503** se o banco não responder.

---

## 3. Transportadora (simulador)

### 3.0 Quem pode chamar o quê

| Rotas | `ADMIN` (JWT da transportadora) | Monitoramento (chave de serviço) | Sem credencial |
|---|---|---|---|
| `POST /autenticacao/login` | sim | n/a | sim |
| `GET /autenticacao/eu` | sim | 401 | 401 |
| `POST /remessas` | **403** `PERMISSAO_INSUFICIENTE` | **sim** | 401 |
| `GET /remessas/{codigo_rastreio}` | sim | sim | 401 |
| `GET /remessas` | sim | 403 `PERMISSAO_INSUFICIENTE` | 401 |
| `POST /remessas/{codigo_rastreio}/status` | sim | 403 | 401 |
| `POST /remessas/{codigo_rastreio}/entregar` | sim | 403 | 401 |
| `GET /logs-webhook` | sim | 403 | 401 |
| `POST /logs-webhook/{id}/reenviar` | sim | 403 | 401 |
| `GET /` (página) e `GET /health` | pública | pública | pública |

Nenhum `USER` acessa a transportadora: o token de um `USER` (emitido pelo Monitoramento) é **inválido** aqui (401), pois os segredos JWT são diferentes. Credencial ausente ou inválida: **401** (`TOKEN_INVALIDO`, `TOKEN_EXPIRADO` ou `CHAVE_API_INVALIDA`). Credencial válida, mas de tipo sem permissão para a rota: **403** `PERMISSAO_INSUFICIENTE`.

Objeto **Remessa**:

```json
{
  "id": 3,
  "codigo_rastreio": "BR123456789",
  "vendedor": "Loja Exemplo LTDA",
  "status": "POSTADO",
  "proximo_status": "EM_TRANSITO",
  "url_callback": "http://monitoramento:8000/webhooks/transportadora",
  "entregue_em": null,
  "recebido_por": null,
  "criado_em": "2026-11-18T14:00:01Z",
  "atualizado_em": "2026-11-18T14:30:00Z"
}
```

`proximo_status` é a próxima ação válida, ou `null` se já estiver `ENTREGUE`. A tela usa esse campo para mostrar o botão certo.

### 3.1 Autenticação do ADMIN

#### `POST /autenticacao/login`

Público. Mesmo formato do login do Monitoramento (`username` = e-mail e `password`, em `application/x-www-form-urlencoded`). Compara com `ADMIN_EMAIL` e `ADMIN_SENHA` (`secrets.compare_digest`), **sem banco de usuários**. O token emitido (segredo da transportadora) tem `sub = "admin"` e `papel = "ADMIN"`.

**200**: `{ "access_token": "...", "token_type": "bearer" }`. Erros: **401** `CREDENCIAIS_INVALIDAS` · **422**.

#### `GET /autenticacao/eu`

Somente `ADMIN`. **200**: `{ "email": "admin@exemplo.com", "papel": "ADMIN" }`. Erros: **401**.

### 3.2 Remessas

#### `POST /remessas`

Somente chave de serviço (`X-Chave-Api`). Idempotente por `codigo_rastreio`.

```json
// requisição
{
  "codigo_rastreio": "BR123456789",
  "vendedor": "Loja Exemplo LTDA",
  "url_callback": "http://monitoramento:8000/webhooks/transportadora"
}
```

**201** (remessa nova, status `AGUARDANDO_ENVIO`) ou **200** (já existia; devolve a existente, sem alterar). Erros: **401** `CHAVE_API_INVALIDA` · **403** · **422**.

#### `GET /remessas`

Somente `ADMIN`. **200**: lista de Remessa, da mais recente para a mais antiga.

#### `GET /remessas/{codigo_rastreio}`

`ADMIN` ou chave de serviço. **200**: Remessa. Erros: **401** · **404** `REMESSA_NAO_ENCONTRADA`.

#### `POST /remessas/{codigo_rastreio}/status`

Somente `ADMIN`. Só aceita o **próximo** status da sequência, entre `POSTADO`, `EM_TRANSITO` e `SAIU_PARA_ENTREGA`.

```json
// requisição
{ "status": "POSTADO" }
```

Na mesma transação, atualiza a remessa e cria um evento `remessa.status_alterado` (`PENDENTE`). O envio acontece depois, em segundo plano, então a resposta **não espera** o Monitoramento.

**200**: Remessa atualizada. Erros: **401** · **403** · **404** · **409** `TRANSICAO_INVALIDA` · **422** (status fora dos três permitidos, inclusive `ENTREGUE`).

#### `POST /remessas/{codigo_rastreio}/entregar`

Somente `ADMIN`. Só a partir de `SAIU_PARA_ENTREGA`. `entregue_em` é a hora do servidor (UTC).

```json
// requisição (corpo opcional)
{ "recebido_por": "Maria Souza" }
```

Cria o evento `remessa.entregue`. **200**: Remessa com `status: "ENTREGUE"` e `entregue_em`. Erros: **401** · **403** · **404** · **409** `TRANSICAO_INVALIDA` · **422**.

### 3.3 Log de webhooks

#### `GET /logs-webhook?codigo_rastreio=&estado=`

Somente `ADMIN`. `estado`: `PENDENTE`, `ENVIADO` ou `FALHA`. Do mais recente para o mais antigo.

```json
[
  {
    "id": 21,
    "id_evento": "6f1c7d4e-2b0a-4f43-9c1a-1d7f3c2b9a10",
    "tipo_evento": "remessa.entregue",
    "codigo_rastreio": "BR123456789",
    "estado": "ENVIADO",
    "total_tentativas": 2,
    "ultimo_status_http": 200,
    "ultimo_erro": null,
    "criado_em": "2026-11-18T17:42:10Z",
    "enviado_em": "2026-11-18T17:42:13Z",
    "historico_tentativas": [
      { "numero": 1, "status_http": null, "erro": "conexao recusada", "duracao_ms": 12, "tentou_em": "2026-11-18T17:42:10Z" },
      { "numero": 2, "status_http": 200, "erro": null, "duracao_ms": 48, "tentou_em": "2026-11-18T17:42:12Z" }
    ]
  }
]
```

Erros: **401** · **403** · **422**.

#### `POST /logs-webhook/{id}/reenviar`

Somente `ADMIN`. Recoloca o evento como `PENDENTE` (`total_tentativas = 0`, `proxima_tentativa_em = agora`), **mantendo o mesmo `id_evento` e o mesmo corpo**. Serve para demonstrar a idempotência: o Monitoramento responde 200 `duplicado`.

**202**: o item do log. Erros: **401** · **403** · **404** `EVENTO_WEBHOOK_NAO_ENCONTRADO`.

### 3.4 Página do ADMIN e saúde

- `GET /`: **200**, página HTML estática (pública, mas sozinha não faz nada: mostra o **formulário de login** e, depois do login, a tela). Os assets usam **caminhos relativos** (`static/app.js`, `remessas`), pois a página roda em `/transportadora/`. O nginx deve redirecionar `/transportadora` para `/transportadora/`.
- O token da transportadora fica em `sessionStorage` (chave `hooklog_token_transportadora`) e é enviado em `Authorization: Bearer`. Resposta 401 volta para o formulário de login.
- `GET /health`: **200** `{"status": "ok", "servico": "transportadora"}`. **503** se o banco não responder.

---

## 4. Contrato do webhook

### Requisição enviada pela transportadora

```
POST {url_callback}
Content-Type: application/json
X-Carimbo-Tempo: 1763487730
X-Assinatura: sha256=3b8c...e41f
```

### Corpo

```json
{
  "id_evento": "6f1c7d4e-2b0a-4f43-9c1a-1d7f3c2b9a10",
  "tipo_evento": "remessa.entregue",
  "codigo_rastreio": "BR123456789",
  "status": "ENTREGUE",
  "vendedor": "Loja Exemplo LTDA",
  "ocorrido_em": "2026-11-18T17:42:10Z",
  "entregue_em": "2026-11-18T17:42:10Z",
  "recebido_por": "Maria Souza"
}
```

| Campo | Tipo | Obrigatório | Observação |
|---|---|---|---|
| `id_evento` | UUID (texto) | sim | Chave de idempotência. Estável em retries e reenvios |
| `tipo_evento` | texto | sim | `remessa.status_alterado` ou `remessa.entregue` |
| `codigo_rastreio` | texto | sim | Chave para achar a encomenda |
| `status` | texto | sim | Um dos valores de status |
| `vendedor` | texto | sim | Informativo; **não** sobrescreve o dado local (RN13) |
| `ocorrido_em` | data UTC | sim | Quando a mudança aconteceu |
| `entregue_em` | data UTC | só em `remessa.entregue` | Quando a entrega foi feita |
| `recebido_por` | texto | não | Só em `remessa.entregue` |

O corpo é **serializado uma única vez**, na criação do evento, e guardado como texto em `eventos_webhook.corpo`. Todos os envios (inclusive retries e reenvios) usam esses mesmos bytes.

### Assinatura

```python
conteudo_assinado = f"{carimbo_tempo}.".encode() + corpo_bruto      # bytes
resumo = hmac.new(segredo.encode(), conteudo_assinado, hashlib.sha256).hexdigest()
cabecalho_assinatura = f"sha256={resumo}"
```

- `carimbo_tempo`: segundos desde a época (inteiro), em `X-Carimbo-Tempo`.
- **Verificação** (Monitoramento): ler o corpo bruto, validar que `abs(agora - carimbo_tempo) <= 300`, recalcular o resumo e comparar com `hmac.compare_digest`. Qualquer falha: 401 `ASSINATURA_INVALIDA` (mensagem genérica, sem dizer qual verificação falhou).
- **A cada tentativa de envio**, a transportadora gera um `X-Carimbo-Tempo` novo e recalcula a assinatura (o evento pode ser reenviado minutos depois e ainda precisa passar na janela).

### Como a transportadora reage à resposta

| Resposta do Monitoramento | Ação | Motivo |
|---|---|---|
| 200 (`aplicado` ou `duplicado`) | Marca `ENVIADO`, para | Processado, ou duplicado já ignorado |
| 401, 404, 409, 422 | Marca `FALHA` na hora, **sem retry** | O problema está no pedido; repetir não resolve |
| 408, 429 | Retry com backoff | Condição temporária |
| 5xx, timeout, conexão recusada | Retry com backoff | Falha temporária |
| Esgotou `MAX_TENTATIVAS_WEBHOOK` | Marca `FALHA` | Pode ser reenviado manualmente pelo ADMIN |

Backoff: após a tentativa `n` falhar (e `n < máximo`), a próxima ocorre em `base * 2^(n-1)` segundos. Com `base = 1`: 1, 2, 4 e 8 s.

---

## 5. Chamadas internas (só na rede do Docker)

| De -> Para | Requisição |
|---|---|
| Monitoramento -> Transportadora | `POST http://transportadora:8001/remessas` com `X-Chave-Api: CHAVE_API_SERVICO` |
| Transportadora -> Monitoramento | `POST http://monitoramento:8000/webhooks/transportadora` (HMAC) |

Como o Monitoramento classifica a resposta da transportadora ao registrar:

| Resposta | Classificação | Efeito |
|---|---|---|
| 200 ou 201 | Sucesso | `AGUARDANDO_ENVIO` |
| 401, 403, 422 | **Permanente** | `FALHA_NO_REGISTRO` (configuração ou contrato errado; repetir não adianta) |
| Timeout, conexão recusada, 5xx, 408, 429 | **Transitória** | `REGISTRO_PENDENTE` com backoff |

---

## 6. Catálogo de códigos de erro

### Monitoramento

| `codigo` | Status | Quando |
|---|---|---|
| `EMAIL_JA_CADASTRADO` | 409 | Registro com e-mail existente (ou o do ADMIN) |
| `CREDENCIAIS_INVALIDAS` | 401 | Login incorreto |
| `TOKEN_INVALIDO` | 401 | Token ausente, malformado ou com assinatura errada |
| `TOKEN_EXPIRADO` | 401 | Token vencido |
| `ACESSO_NEGADO` | 403 | Papel sem permissão (ADMIN em rota de USER, ou o inverso) |
| `ENCOMENDA_NAO_ENCONTRADA` | 404 | Não existe, ou é de outro usuário |
| `CODIGO_RASTREIO_DUPLICADO` | 409 | Código já cadastrado |
| `ESTADO_INVALIDO` | 409 | Ação incompatível com o status atual (ex.: `/registrar`) |
| `ASSINATURA_INVALIDA` | 401 | Falha na verificação do webhook |
| `TRANSICAO_INVALIDA` | 409 | Evento não avança o status |

### Transportadora

| `codigo` | Status | Quando |
|---|---|---|
| `CREDENCIAIS_INVALIDAS` | 401 | Login do ADMIN incorreto |
| `TOKEN_INVALIDO` | 401 | Token ausente, malformado, de outro serviço ou com assinatura errada |
| `TOKEN_EXPIRADO` | 401 | Token vencido |
| `CHAVE_API_INVALIDA` | 401 | Chave de serviço ausente ou desconhecida |
| `PERMISSAO_INSUFICIENTE` | 403 | Credencial válida, mas de tipo sem acesso à rota |
| `REMESSA_NAO_ENCONTRADA` | 404 | Remessa inexistente |
| `EVENTO_WEBHOOK_NAO_ENCONTRADO` | 404 | Evento de webhook inexistente |
| `TRANSICAO_INVALIDA` | 409 | Status não é o próximo da sequência |
