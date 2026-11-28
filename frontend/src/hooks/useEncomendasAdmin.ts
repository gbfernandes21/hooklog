import { useQuery } from '@tanstack/react-query';
import { listarTodasEncomendas, obterEncomendaAdmin } from '../api/admin';
import { obterEncomenda } from '../api/encomendas';

export function useListarTodasEncomendas(
  grupo?: string | null,
  usuarioId?: number | null
) {
  return useQuery({
    queryKey: ['encomendasAdmin', grupo, usuarioId],
    queryFn: () => listarTodasEncomendas(grupo, usuarioId),
    enabled: true,
    refetchInterval: 5000,
    refetchIntervalInBackground: true,
  });
}

export function useObterEncomendaAdmin(id: number | null) {
  return useQuery({
    queryKey: ['encomendaAdmin', id],
    queryFn: () => obterEncomendaAdmin(id!),
    enabled: id !== null && id !== undefined,
    refetchInterval: 5000,
    refetchIntervalInBackground: true,
  });
}

export function useObterEncomendaUsuario(id: number | null) {
  return useQuery({
    queryKey: ['encomendaUsuario', id],
    queryFn: () => obterEncomenda(id!),
    enabled: id !== null && id !== undefined,
    refetchInterval: 5000,
    refetchIntervalInBackground: true,
  });
}
