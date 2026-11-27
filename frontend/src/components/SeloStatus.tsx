import { STATUS_CSS, STATUS_ROTULOS } from '../types';

export function SeloStatus({ status }: { status: string }): JSX.Element {
  const classe = STATUS_CSS[status] ?? 'selo-padrao';
  const rotulo = STATUS_ROTULOS[status] ?? status;

  return <span className={`badge selo-status ${classe}`}>{rotulo}</span>;
}
