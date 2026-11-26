import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { clienteApi, postForm } from '../api/clienteApi';
import { CHAVE_TOKEN, Usuario, UsuarioLer } from '../types';

interface ContextoAutenticacaoValor {
  usuario: Usuario | null;
  carregando: boolean;
  login: (email: string, senha: string) => Promise<void>;
  registrar: (dados: { email: string; senha: string }) => Promise<void>;
  logout: () => void;
  estaAutenticado: boolean;
  ehAdmin: boolean;
  ehUsuario: boolean;
}

const ContextoAutenticacao = createContext<ContextoAutenticacaoValor | undefined>(
  undefined
);

export function ProvedorAutenticacao({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [carregando, setCarregando] = useState(true);

  const ehAdmin = usuario?.papel === 'ADMIN';
  const ehUsuario = usuario?.papel === 'USER';
  const estaAutenticado = !!usuario;

  useEffect(() => {
    const token = localStorage.getItem(CHAVE_TOKEN);
    if (token) {
      carregarUsuario();
    } else {
      setCarregando(false);
    }
  }, []);

  async function carregarUsuario(): Promise<void> {
    try {
      const resposta = await clienteApi.get<UsuarioLer>('/autenticacao/eu');
      const dados = resposta.data;
      setUsuario({
        id: dados.id ?? null,
        email: dados.email,
        papel: dados.papel,
      });
    } catch {
      logoutSemRedirecionar();
    } finally {
      setCarregando(false);
    }
  }

  async function login(email: string, senha: string): Promise<void> {
    const token = await postForm<{ access_token: string }>(
      '/autenticacao/login',
      { username: email, password: senha }
    );
    localStorage.setItem(CHAVE_TOKEN, token.access_token);
    await carregarUsuario();
  }

  async function registrar(dados: { email: string; senha: string }): Promise<void> {
    await clienteApi.post<UsuarioLer>('/autenticacao/registro', dados);
    await login(dados.email, dados.senha);
  }

  function logout(): void {
    logoutSemRedirecionar();
    window.location.href = '/login';
  }

  function logoutSemRedirecionar(): void {
    localStorage.removeItem(CHAVE_TOKEN);
    setUsuario(null);
    setCarregando(false);
  }

  const valor: ContextoAutenticacaoValor = {
    usuario,
    carregando,
    login,
    registrar,
    logout,
    estaAutenticado,
    ehAdmin,
    ehUsuario,
  };

  return (
    <ContextoAutenticacao.Provider value={valor}>{children}</ContextoAutenticacao.Provider>
  );
}

export function useAutenticacao(): ContextoAutenticacaoValor {
  const contexto = useContext(ContextoAutenticacao);
  if (!contexto) {
    throw new Error('useAutenticacao deve ser usado dentro de ProvedorAutenticacao');
  }
  return contexto;
}
