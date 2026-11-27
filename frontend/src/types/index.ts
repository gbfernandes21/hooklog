export type Papel = 'USER' | 'ADMIN';

export interface Usuario {
  id: number | null;
  email: string;
  papel: Papel;
}

export interface TokenAcesso {
  access_token: string;
  token_type: string;
}

export interface UsuarioRegistro {
  email: string;
  senha: string;
}

export interface UsuarioLer {
  id: number;
  email: string;
  papel: Papel;
  criado_em: string;
}

export interface HistoricoStatus {
  status_anterior: string | null;
  status_novo: string;
  ocorrido_em: string;
  id_evento: string | null;
}

export interface Encomenda {
  id: number;
  codigo_rastreio: string;
  descricao: string;
  vendedor: string;
  status: string;
  grupo: string;
  entregue_em: string | null;
  criado_em: string;
  atualizado_em: string;
  historico: HistoricoStatus[];
}

export interface EncomendaAdmin extends Encomenda {
  usuario_id: number;
  usuario_email: string;
}

export interface EncomendaCriar {
  codigo_rastreio: string;
  descricao: string;
  vendedor: string;
}

export interface EncomendaAtualizar {
  descricao?: string | null;
  vendedor?: string | null;
}

export interface ErroDominio {
  detalhe: string;
  codigo: string;
}

export const GRUPO_NAO_ENCAMINHADAS = 'nao_encaminhadas';
export const GRUPO_A_CAMINHO = 'a_caminho';
export const GRUPO_ENTREGUES = 'entregues';

export const GRUPOS: { chave: string; rotulo: string }[] = [
  { chave: GRUPO_NAO_ENCAMINHADAS, rotulo: 'Não encaminhadas' },
  { chave: GRUPO_A_CAMINHO, rotulo: 'A caminho' },
  { chave: GRUPO_ENTREGUES, rotulo: 'Entregues' },
];

export const STATUS_ROTULOS: Record<string, string> = {
  REGISTRO_PENDENTE: 'Registrando na transportadora',
  FALHA_NO_REGISTRO: 'Falha no registro',
  AGUARDANDO_ENVIO: 'Aguardando envio',
  POSTADO: 'Postado',
  EM_TRANSITO: 'Em trânsito',
  SAIU_PARA_ENTREGA: 'Saiu para entrega',
  ENTREGUE: 'Entregue',
};

export const STATUS_CSS: Record<string, string> = {
  REGISTRO_PENDENTE: 'selo-registro-pendente',
  FALHA_NO_REGISTRO: 'selo-falha-registro',
  AGUARDANDO_ENVIO: 'selo-aguardando-envio',
  POSTADO: 'selo-postado',
  EM_TRANSITO: 'selo-em-transito',
  SAIU_PARA_ENTREGA: 'selo-saiu-entrega',
  ENTREGUE: 'selo-entregue',
};

export const GRUPO_POR_STATUS: Record<string, string> = {
  REGISTRO_PENDENTE: GRUPO_NAO_ENCAMINHADAS,
  FALHA_NO_REGISTRO: GRUPO_NAO_ENCAMINHADAS,
  AGUARDANDO_ENVIO: GRUPO_NAO_ENCAMINHADAS,
  POSTADO: GRUPO_NAO_ENCAMINHADAS,
  EM_TRANSITO: GRUPO_A_CAMINHO,
  SAIU_PARA_ENTREGA: GRUPO_A_CAMINHO,
  ENTREGUE: GRUPO_ENTREGUES,
};

export const CHAVE_TOKEN = 'hooklog_token';
