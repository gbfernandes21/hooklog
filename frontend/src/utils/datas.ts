const FORMATADOR_BRASILIA = new Intl.DateTimeFormat('pt-BR', {
  timeZone: 'America/Sao_Paulo',
  dateStyle: 'short',
  timeStyle: 'medium',
});

export function formatarDataHoraBrasilia(dataIso: string | null | undefined): string {
  if (!dataIso) {
    return '—';
  }

  const data = new Date(dataIso);
  if (Number.isNaN(data.getTime())) {
    return '—';
  }

  return FORMATADOR_BRASILIA.format(data);
}

export function formatarDataBrasilia(
  dataIso: string | null | undefined
): string {
  if (!dataIso) {
    return '—';
  }
  const data = new Date(dataIso);
  if (Number.isNaN(data.getTime())) {
    return '—';
  }
  return data.toLocaleDateString('pt-BR', { timeZone: 'America/Sao_Paulo' });
}

export function formatarHoraBrasilia(
  dataIso: string | null | undefined
): string {
  if (!dataIso) {
    return '—';
  }
  const data = new Date(dataIso);
  if (Number.isNaN(data.getTime())) {
    return '—';
  }
  return data.toLocaleTimeString('pt-BR', {
    timeZone: 'America/Sao_Paulo',
    hour: '2-digit',
    minute: '2-digit',
  });
}
