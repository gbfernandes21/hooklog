const TOKEN_KEY = "hooklog_token_transportadora";

const btnSair = document.getElementById("btnSair");
const telaLogin = document.getElementById("telaLogin");
const telaPrincipal = document.getElementById("telaPrincipal");
const formLogin = document.getElementById("formLogin");
const msgErroLogin = document.getElementById("msgErroLogin");
const msgSucesso = document.getElementById("msgSucesso");
const msgErro = document.getElementById("msgErro");

let intervaloPolling = null;

function mostrarErro(elemento, texto) {
  elemento.textContent = texto;
  elemento.classList.remove("d-none");
}

function esconderErro(elemento) {
  elemento.classList.add("d-none");
}

function estaLogado() {
  return !!sessionStorage.getItem(TOKEN_KEY);
}

function mostrarTelaLogin() {
  telaLogin.classList.remove("d-none");
  telaPrincipal.classList.add("d-none");
  btnSair.classList.add("d-none");
  if (intervaloPolling) {
    clearInterval(intervaloPolling);
    intervaloPolling = null;
  }
}

function mostrarTelaPrincipal() {
  telaLogin.classList.add("d-none");
  telaPrincipal.classList.remove("d-none");
  btnSair.classList.remove("d-none");
}

async function login(email, senha) {
  const corpo = new URLSearchParams();
  corpo.append("username", email);
  corpo.append("password", senha);

  const resposta = await fetch("autenticacao/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: corpo,
  });

  if (!resposta.ok) {
    const erro = await resposta.json();
    throw new Error(erro.detalhe || "Credenciais inválidas");
  }

  const dados = await resposta.json();
  sessionStorage.setItem(TOKEN_KEY, dados.access_token);
}

async function requisicaoAutenticada(caminho, opcoes = {}) {
  const token = sessionStorage.getItem(TOKEN_KEY);
  const headers = {
    ...(opcoes.headers || {}),
    Authorization: `Bearer ${token}`,
  };
  return fetch(caminho, { ...opcoes, headers });
}

function formatarBrasilia(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleString("pt-BR", {
    timeZone: "America/Sao_Paulo",
    dateStyle: "short",
    timeStyle: "medium",
  });
}

function seloParaStatus(status) {
  const classes = {
    REGISTRO_PENDENTE: "selo-pendente",
    FALHA_NO_REGISTRO: "selo-falha",
    AGUARDANDO_ENVIO: "selo-pendente",
    POSTADO: "selo-pendente",
    EM_TRANSITO: "selo-enviado",
    SAIU_PARA_ENTREGA: "selo-enviado",
    ENTREGUE: "selo-enviado",
  };
  return classes[status] || "selo-padrao";
}

async function carregarRemessas() {
  const resposta = await requisicaoAutenticada("remessas");
  if (resposta.status === 401) {
    sessionStorage.removeItem(TOKEN_KEY);
    mostrarTelaLogin();
    return;
  }
  if (!resposta.ok) {
    throw new Error("Erro ao carregar remessas");
  }
  const remessas = await resposta.json();

  const tbody = document.getElementById("tbodyRemessas");
  tbody.innerHTML = "";
  document.getElementById("badgeContagem").textContent = remessas.length;

  for (const remessa of remessas) {
    const linha = document.createElement("tr");
    const proximo = remessa.proximo_status;
    let botoesAcao = "";

    if (proximo === "ENTREGUE") {
      botoesAcao = `
        <button class="btn btn-sm btn-primary btn-entregar" data-codigo="${remessa.codigo_rastreio}">Entregar</button>
      `;
    } else if (proximo) {
      botoesAcao = `
        <button class="btn btn-sm btn-primary btn-avancar" data-codigo="${remessa.codigo_rastreio}" data-status="${proximo}">${proximo}</button>
      `;
    } else {
      botoesAcao = `<span class="text-muted">--</span>`;
    }

    linha.innerHTML = `
      <td><span class="codigo-rastreio">${remessa.codigo_rastreio}</span></td>
      <td>${remessa.vendedor}</td>
      <td><span class="selo-status ${seloParaStatus(remessa.status)}">${remessa.status}</span></td>
      <td class="text-center">${botoesAcao}</td>
    `;
    tbody.appendChild(linha);
  }

  document.querySelectorAll(".btn-avancar").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const codigo = btn.dataset.codigo;
      const novoStatus = btn.dataset.status;
      try {
        const resp = await requisicaoAutenticada(`remessas/${codigo}/status`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: novoStatus }),
        });
        if (resp.status === 401) {
          sessionStorage.removeItem(TOKEN_KEY);
          mostrarTelaLogin();
          return;
        }
        if (!resp.ok) {
          const erro = await resp.json();
          mostrarErro(msgErro, `Erro: ${erro.detalhe || "falha ao avançar status"}`);
          return;
        }
        esconderErro(msgErro);
        await carregarRemessas();
        await carregarLogs();
      } catch (erro) {
        mostrarErro(msgErro, erro.message);
      }
    });
  });

  document.querySelectorAll(".btn-entregar").forEach((btn) => {
    btn.addEventListener("click", () => {
      const codigo = btn.dataset.codigo;
      document.getElementById("inputCodigoEntrega").value = codigo;
      document.getElementById("inputRecebidoPor").value = "";
      const modal = new bootstrap.Modal(document.getElementById("modalEntrega"));
      modal.show();
    });
  });

  document.getElementById("btnConfirmarEntrega").addEventListener("click", async () => {
    const codigo = document.getElementById("inputCodigoEntrega").value;
    const recebidoPor = document.getElementById("inputRecebidoPor").value || undefined;
    try {
      const resp = await requisicaoAutenticada(`remessas/${codigo}/entregar`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ recebido_por: recebidoPor }),
      });
      if (resp.status === 401) {
        sessionStorage.removeItem(TOKEN_KEY);
        mostrarTelaLogin();
        return;
      }
      if (!resp.ok) {
        const erro = await resp.json();
        mostrarErro(msgErro, `Erro: ${erro.detalhe || "falha ao entregar"}`);
        return;
      }
      const modal = bootstrap.Modal.getInstance(document.getElementById("modalEntrega"));
      modal.hide();
      esconderErro(msgErro);
      await carregarRemessas();
      await carregarLogs();
    } catch (erro) {
      mostrarErro(msgErro, erro.message);
    }
  });
}

async function carregarLogs() {
  const resposta = await requisicaoAutenticada("logs-webhook");
  if (resposta.status === 401) {
    sessionStorage.removeItem(TOKEN_KEY);
    mostrarTelaLogin();
    return;
  }
  if (!resposta.ok) {
    throw new Error("Erro ao carregar log de webhooks");
  }
  const eventos = await resposta.json();

  const tbody = document.getElementById("tbodyLogs");
  tbody.innerHTML = "";

  for (const evento of eventos) {
    const linha = document.createElement("tr");
    const classeEstado = {
      PENDENTE: "selo-pendente",
      ENVIADO: "selo-enviado",
      FALHA: "selo-falha",
    }[evento.estado] || "selo-padrao";

    const botoesAcao = evento.estado !== "ENVIADO"
      ? `<button class="btn btn-sm btn-outline-primary btn-reenviar" data-id="${evento.id}">reenviar</button>`
      : `<span class="text-muted">--</span>`;

    linha.innerHTML = `
      <td>${evento.id}</td>
      <td><span class="codigo-rastreio">${evento.codigo_rastreio}</span></td>
      <td>${evento.tipo_evento}</td>
      <td class="text-center"><span class="selo-status ${classeEstado}">${evento.estado}</span></td>
      <td class="text-center">${evento.total_tentativas}</td>
      <td class="text-center">${evento.ultimo_status_http ?? "-"}</td>
      <td>${evento.ultimo_erro ?? "-"}</td>
      <td>${formatarBrasilia(evento.criado_em)}</td>
      <td class="text-center">${formatarBrasilia(evento.enviado_em)}</td>
      <td class="text-end">${botoesAcao}</td>
    `;
    tbody.appendChild(linha);
  }

  document.querySelectorAll(".btn-reenviar").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.dataset.id;
      try {
        const resp = await requisicaoAutenticada(`logs-webhook/${id}/reenviar`, {
          method: "POST",
        });
        if (resp.status === 401) {
          sessionStorage.removeItem(TOKEN_KEY);
          mostrarTelaLogin();
          return;
        }
        if (!resp.ok) {
          const erro = await resp.json();
          mostrarErro(msgErro, `Erro: ${erro.detalhe || "falha ao reenviar"}`);
          return;
        }
        esconderErro(msgErro);
        mostrarErro(msgSucesso, "Evento reenviado com sucesso.");
        setTimeout(() => esconderErro(msgSucesso), 3000);
        await carregarLogs();
      } catch (erro) {
        mostrarErro(msgErro, erro.message);
      }
    });
  });
}

async function atualizarDados() {
  await carregarRemessas();
  await carregarLogs();
}

formLogin.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  esconderErro(msgErroLogin);
  const email = formLogin.elements.email.value.trim();
  const senha = formLogin.elements.senha.value.trim();
  try {
    await login(email, senha);
    mostrarTelaPrincipal();
    await atualizarDados();
    intervaloPolling = setInterval(atualizarDados, 3000);
  } catch (erro) {
    mostrarErro(msgErroLogin, erro.message);
  }
});

btnSair.addEventListener("click", () => {
  sessionStorage.removeItem(TOKEN_KEY);
  if (intervaloPolling) {
    clearInterval(intervaloPolling);
    intervaloPolling = null;
  }
  formLogin.reset();
  mostrarTelaLogin();
});

// Inicializacao
if (estaLogado()) {
  mostrarTelaPrincipal();
  atualizarDados().catch(() => {
    sessionStorage.removeItem(TOKEN_KEY);
    mostrarTelaLogin();
  });
  intervaloPolling = setInterval(atualizarDados, 3000);
} else {
  mostrarTelaLogin();
}
