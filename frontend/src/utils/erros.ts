import axios from 'axios';

interface CorpoErro {
  codigo?: string;
  detalhe?: string;
}

export interface ErroExtraido {
  status?: number;
  codigo?: string;
  detalhe?: string;
}

export function extrairErro(erro: unknown): ErroExtraido {
  if (!axios.isAxiosError(erro)) {
    return {};
  }

  const corpo = erro.response?.data as CorpoErro | undefined;
  return {
    status: erro.response?.status,
    codigo: corpo?.codigo,
    detalhe: corpo?.detalhe,
  };
}
