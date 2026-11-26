import axios, { AxiosError, AxiosInstance } from 'axios';
import { CHAVE_TOKEN } from '../types';

function obterToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(CHAVE_TOKEN);
}

export const clienteApi: AxiosInstance = axios.create({
  baseURL: (import.meta.env.VITE_API_BASE ?? '/api') as string,
  headers: {
    'Content-Type': 'application/json',
  },
});

clienteApi.interceptors.request.use((config) => {
  const token = obterToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

clienteApi.interceptors.response.use(
  (resposta) => resposta,
  (erro: AxiosError) => {
    if (erro.response?.status === 401) {
      if (typeof window !== 'undefined') {
        localStorage.removeItem(CHAVE_TOKEN);
      }
      window.location.href = '/login';
    }
    return Promise.reject(erro);
  }
);

export async function postForm<T = any>(
  url: string,
  dados: Record<string, string>
): Promise<T> {
  const formData = new URLSearchParams();
  for (const [chave, valor] of Object.entries(dados)) {
    formData.append(chave, valor);
  }
  const resposta = await clienteApi.post<T>(url, formData, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  return resposta.data;
}
