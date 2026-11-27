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
