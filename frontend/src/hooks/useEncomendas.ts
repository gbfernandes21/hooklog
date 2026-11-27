import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  atualizarEncomenda,
  criarEncomenda,
  excluirEncomenda,
  listarEncomendas,
  solicitarNovoRegistro,
} from '../api/encomendas';
import { EncomendaAtualizar, EncomendaCriar } from '../types';

const CHAVE_ENCOMENDAS = ['encomendas'];

export function useEncomendas() {
  return useQuery({
    queryKey: CHAVE_ENCOMENDAS,
    queryFn: listarEncomendas,
    refetchInterval: 5000,
    refetchIntervalInBackground: true,
  });
}

function useInvalidarEncomendas() {
  const clienteConsultas = useQueryClient();
  return () => clienteConsultas.invalidateQueries({ queryKey: CHAVE_ENCOMENDAS });
}

export function useCriarEncomenda() {
  const invalidar = useInvalidarEncomendas();
  return useMutation({
    mutationFn: (dados: EncomendaCriar) => criarEncomenda(dados),
    onSuccess: () => {
      void invalidar();
    },
  });
}

export function useAtualizarEncomenda() {
  const invalidar = useInvalidarEncomendas();
  return useMutation({
    mutationFn: ({ id, dados }: { id: number; dados: EncomendaAtualizar }) =>
      atualizarEncomenda(id, dados),
    onSuccess: () => {
      void invalidar();
    },
  });
}

export function useExcluirEncomenda() {
  const invalidar = useInvalidarEncomendas();
  return useMutation({
    mutationFn: (id: number) => excluirEncomenda(id),
    onSuccess: () => {
      void invalidar();
    },
  });
}

export function useRegistrarEncomenda() {
  const invalidar = useInvalidarEncomendas();
  return useMutation({
    mutationFn: (id: number) => solicitarNovoRegistro(id),
    onSuccess: () => {
      void invalidar();
    },
  });
}
