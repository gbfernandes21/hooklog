import { clienteApi } from './clienteApi';
import { EncomendaAdmin } from '../types';

export async function listarTodasEncomendas(
  grupo?: string | null,
  usuarioId?: number | null
): Promise<EncomendaAdmin[]> {
  const params = new URLSearchParams();
  if (grupo) {
    params.set('grupo', grupo);
  }
  if (usuarioId !== undefined && usuarioId !== null) {
    params.set('usuario_id', String(usuarioId));
  }
  const query = params.toString() ? `?${params.toString()}` : '';
  const resposta = await clienteApi.get<EncomendaAdmin[]>(`/admin/encomendas${query}`);
  return resposta.data;
}

export async function obterEncomendaAdmin(id: number): Promise<EncomendaAdmin> {
  const resposta = await clienteApi.get<EncomendaAdmin>(`/admin/encomendas/${id}`);
  return resposta.data;
}
