import { useMemo, useState } from 'react';
import { Alert, Button, Container, Spinner, Table } from 'react-bootstrap';
import { Link } from 'react-router-dom';
import { SeloStatus } from '../components/SeloStatus';
import { useListarTodasEncomendas } from '../hooks/useEncomendasAdmin';
import { GRUPOS } from '../types';

export default function PaginaAdmin(): JSX.Element {
  const [grupoFiltro, setGrupoFiltro] = useState<string | null>(null);
  const { data, isLoading, isError } = useListarTodasEncomendas(grupoFiltro, null);

  const encomendas = useMemo(() => data ?? [], [data]);

  const encomendasFiltradas = useMemo(() => {
    if (!grupoFiltro) {
      return encomendas;
    }
    return encomendas.filter((e) => e.grupo === grupoFiltro);
  }, [encomendas, grupoFiltro]);

  if (isLoading) {
    return (
      <Container className="mt-4 mb-5 text-center py-5">
        <Spinner animation="border" role="status" />
        <p className="mt-3 text-muted mb-0">Carregando encomendas...</p>
      </Container>
    );
  }

  if (isError) {
    return (
      <Container className="mt-4 mb-5">
        <Alert variant="danger">
          <p className="mb-2">Não foi possível carregar as encomendas.</p>
          <Button variant="outline-danger" size="sm">
            Tentar novamente
          </Button>
        </Alert>
      </Container>
    );
  }

  return (
    <Container className="mt-4 mb-5">
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h1 className="h3 mb-0">Todas as encomendas (ADMIN)</h1>
        <select
          className="form-select form-select-sm w-auto"
          value={grupoFiltro ?? ''}
          onChange={(evento) =>
            setGrupoFiltro(evento.target.value === '' ? null : evento.target.value)
          }
        >
          <option value="">Todos os grupos</option>
          {GRUPOS.map(({ chave, rotulo }) => (
            <option key={chave} value={chave}>
              {rotulo}
            </option>
          ))}
        </select>
      </div>

      {encomendasFiltradas.length === 0 && (
        <div className="sem-dados">
          <p className="mb-3">
            Nenhuma encomenda encontrada{grupoFiltro ? ` para o grupo "${grupoFiltro}"` : ''}.
          </p>
        </div>
      )}

      {encomendasFiltradas.length > 0 && (
        <Table responsive hover className="align-middle tabela-encomendas">
          <thead>
            <tr>
              <th>Código</th>
              <th>Descrição</th>
              <th>Vendedor</th>
              <th>Status</th>
              <th>Grupo</th>
              <th>Usuário</th>
              <th className="text-center">Ações</th>
            </tr>
          </thead>
          <tbody>
            {encomendasFiltradas.map((encomenda) => (
              <tr key={encomenda.id}>
                <td className="codigo-rastreio">{encomenda.codigo_rastreio}</td>
                <td>{encomenda.descricao}</td>
                <td>{encomenda.vendedor}</td>
                <td>
                  <SeloStatus status={encomenda.status} />
                </td>
                <td>{encomenda.grupo}</td>
                <td>{encomenda.usuario_email}</td>
                <td className="text-center">
                    <Link
                     to={`/admin/encomendas/${encomenda.id}`}
                     className="btn btn-outline-primary btn-sm"
                   >
                     Ver detalhe
                   </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </Container>
  );
}
