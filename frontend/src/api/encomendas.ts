import { clienteApi } from './clienteApi';
import { Encomenda, EncomendaAtualizar, EncomendaCriar } from '../types';

export async function listarEncomendas(): Promise<Encomenda[]> {
  const resposta = await clienteApi.get<Encomenda[]>('/encomendas');
  return resposta.data;
}

export async function criarEncomenda(dados: EncomendaCriar): Promise<Encomenda> {
  const resposta = await clienteApi.post<Encomenda>('/encomendas', dados);
  return resposta.data;
}

export async function atualizarEncomenda(
  id: number,
  dados: EncomendaAtualizar
): Promise<Encomenda> {
  const resposta = await clienteApi.patch<Encomenda>(`/encomendas/${id}`, dados);
  return resposta.data;
}

export async function excluirEncomenda(id: number): Promise<void> {
  await clienteApi.delete(`/encomendas/${id}`);
}

export async function obterEncomenda(id: number): Promise<Encomenda> {
  const resposta = await clienteApi.get<Encomenda>(`/encomendas/${id}`);
  return resposta.data;
}

export async function solicitarNovoRegistro(id: number): Promise<Encomenda> {
  const resposta = await clienteApi.post<Encomenda>(`/encomendas/${id}/registrar`);
  return resposta.data;
}
