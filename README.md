# HookLog

Sistema de monitoramento de encomendas com API REST e webhooks.

A especificação, o contrato das APIs, o modelo de dados e o plano de tarefas estão em `docs/`.

## Antes de rodar

Copie `.env.example` para `.env` e preencha `ADMIN_EMAIL` e `ADMIN_SENHA`. Essas variáveis são obrigatórias: sem elas, o sistema e o `docker compose` se recusam a iniciar.
