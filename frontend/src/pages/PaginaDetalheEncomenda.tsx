import { useParams } from 'react-router-dom';
import { Alert, Button, Card, Container, ListGroup, Spinner, Table } from 'react-bootstrap';
import { Link } from 'react-router-dom';
import { useAutenticacao } from '../auth/ContextoAutenticacao';
import { useObterEncomendaAdmin, useObterEncomendaUsuario } from '../hooks/useEncomendasAdmin';
import { Encomenda, HistoricoStatus } from '../types';
import { SeloStatus } from '../components/SeloStatus';
import { formatarDataHoraBrasilia } from '../utils/datas';
import { extrairErro } from '../utils/erros';

export default function PaginaDetalheEncomenda(): JSX.Element {
  const { id } = useParams();
  const encomendaId = id ? Number(id) : null;
  const { ehAdmin, ehUsuario } = useAutenticacao();

  const queryUsuario = useObterEncomendaUsuario(
    ehUsuario ? encomendaId : null
  );
  const queryAdmin = useObterEncomendaAdmin(ehAdmin ? encomendaId : null);

  const isLoading = queryUsuario.isLoading || queryAdmin.isLoading;
  const isError = queryUsuario.isError || queryAdmin.isError;

  const erroUsuario = extrairErro(queryUsuario.error);
  const erroAdmin = extrairErro(queryAdmin.error);
  const ehNaoEncontrada =
    erroUsuario.status === 404 || erroAdmin.status === 404;

  const encomenda: Encomenda | undefined =
    ehAdmin ? queryAdmin.data : queryUsuario.data;

  const mostrarUsuario = ehAdmin && encomenda !== undefined && 'usuario_email' in encomenda;

  if (isLoading) {
    return (
      <Container className="mt-4 mb-5 text-center py-5">
        <Spinner animation="border" role="status" />
        <p className="mt-3 text-muted mb-0">Carregando detalhes da encomenda...</p>
      </Container>
    );
  }

  if (isError && ehNaoEncontrada) {
    return (
      <Container className="mt-4 mb-5">
        <Alert variant="danger">
          <h4>Encomenda não encontrada.</h4>
          <p className="mb-0">
            Esta encomenda não existe ou você não tem acesso a ela.
          </p>
        </Alert>
        <div className="mt-3">
          <Link to={ehAdmin ? '/admin' : '/encomendas'}>
            <Button variant="primary">Voltar</Button>
          </Link>
        </div>
      </Container>
    );
  }

  if (isError || !encomenda) {
    return (
      <Container className="mt-4 mb-5">
        <Alert variant="danger">
          <h4>Não foi possível carregar a encomenda.</h4>
          <p className="mb-0">Tente novamente mais tarde.</p>
        </Alert>
        <div className="mt-3">
          <Link to={ehAdmin ? '/admin' : '/encomendas'}>
            <Button variant="primary">Voltar</Button>
          </Link>
        </div>
      </Container>
    );
  }

  return (
    <Container className="mt-4 mb-5">
      <div className="d-flex justify-content-between align-items-start mb-3">
        <div>
          <h1 className="h3 mb-0">Detalhe da encomenda</h1>
          <p className="text-muted mb-0">
            Código de rastreio: <strong>{encomenda.codigo_rastreio}</strong>
          </p>
        </div>
        <Link to={ehAdmin ? '/admin' : '/encomendas'}>
          <Button variant="secondary">Voltar</Button>
        </Link>
      </div>

      <Card>
        <Card.Body>
          <Table className="table-borderless align-middle">
            <tbody>
              <tr>
                <td className="fw-bold" style={{ width: '30%' }}>
                  Status
                </td>
                <td>
                  <SeloStatus status={encomenda.status} />
                </td>
              </tr>
              <tr>
                <td className="fw-bold">Descrição</td>
                <td>{encomenda.descricao}</td>
              </tr>
              <tr>
                <td className="fw-bold">Vendedor</td>
                <td>{encomenda.vendedor}</td>
              </tr>
              <tr>
                <td className="fw-bold">Grupo</td>
                <td>{encomenda.grupo}</td>
              </tr>
              <tr>
                <td className="fw-bold">Criado em</td>
                <td>{formatarDataHoraBrasilia(encomenda.criado_em)}</td>
              </tr>
              <tr>
                <td className="fw-bold">Atualizado em</td>
                <td>{formatarDataHoraBrasilia(encomenda.atualizado_em)}</td>
              </tr>
              {encomenda.entregue_em && (
                <tr>
                  <td className="fw-bold">Entregue em</td>
                  <td>{formatarDataHoraBrasilia(encomenda.entregue_em)}</td>
                </tr>
              )}
              {mostrarUsuario && (
                <tr>
                  <td className="fw-bold">Usuário</td>
                  <td>
                    {(encomenda as { usuario_email: string }).usuario_email}
                  </td>
                </tr>
              )}
            </tbody>
          </Table>
        </Card.Body>
      </Card>

      <div className="mt-4">
        <h2 className="h5 mb-3">Histórico de status</h2>
        <ListGroup>
              {encomenda.historico.map((item: HistoricoStatus, indice: number) => (
            <ListGroup.Item key={indice} className="historico-item">
              <div className="d-flex justify-content-between align-items-start">
                <div>
                  <span className="badge me-2">
                    <SeloStatus status={item.status_novo} />
                  </span>{' '}
                  {item.status_anterior && (
                    <span className="text-muted">de {item.status_anterior}</span>
                  )}
                  <span className="ms-2 fw-bold">{item.status_novo}</span>
                </div>
                <span className="text-muted small">
                  {formatarDataHoraBrasilia(item.ocorrido_em)}
                </span>
              </div>
            </ListGroup.Item>
          ))}
          {encomenda.historico.length === 0 && (
            <ListGroup.Item className="text-muted">
              Nenhuma mudança de status registrada.
            </ListGroup.Item>
          )}
        </ListGroup>
      </div>
    </Container>
  );
}
