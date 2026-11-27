import { useParams } from 'react-router-dom';
import { Alert, Button, Card, Container, Spinner, Table } from 'react-bootstrap';
import { Link } from 'react-router-dom';
import { useAutenticacao } from '../auth/ContextoAutenticacao';
import { useObterEncomendaAdmin, useObterEncomendaUsuario } from '../hooks/useEncomendasAdmin';
import {
  Encomenda,
  HistoricoStatus,
  CAMINHO_STATUS,
  STATUS_ROTULOS,
} from '../types';
import { SeloStatus } from '../components/SeloStatus';
import {
  formatarDataBrasilia,
  formatarDataHoraBrasilia,
  formatarHoraBrasilia,
} from '../utils/datas';
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
              {encomenda.recebido_por && (
                <tr>
                  <td className="fw-bold">Recebido por</td>
                  <td>{encomenda.recebido_por}</td>
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
        <h2 className="h5 mb-3">Acompanhamento da entrega</h2>
        {encomenda.historico.length === 0 ? (
          <p className="text-muted">Nenhuma mudança de status registrada.</p>
        ) : (
          <div className="barra-status">
            {montarPassos(encomenda.historico).map((passo) => (
              <div key={passo.status} className="passo-status">
                <span
                  className={`bolinha-status ${passo.ativo ? 'ativo' : 'pendente'}`}
                  aria-label={passo.rotulo}
                />
                <span
                  className={`rotulo-passo ${
                    passo.ativo ? 'ativo' : 'pendente'
                  }`}
                >
                  {passo.rotulo}
                </span>
                {passo.ativo && passo.ocorridoEm && (
                  <>
                    <span className="data-passo ativo">
                      {formatarDataBrasilia(passo.ocorridoEm)}
                    </span>{' '}
                    <span className="hora-passo ativo">
                      {formatarHoraBrasilia(passo.ocorridoEm)}
                    </span>
                  </>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </Container>
  );
}

function montarPassos(
  historico: HistoricoStatus[]
): {
  status: string;
  rotulo: string;
  ativo: boolean;
  ocorridoEm: string | undefined;
}[] {
  const ocorrenciasPorStatus = new Map<string, string>();
  historico.forEach((item) => {
    ocorrenciasPorStatus.set(item.status_novo, item.ocorrido_em);
  });

  const indiceUltimoAlcancado = CAMINHO_STATUS.reduce((maior, status, indice) => {
    return ocorrenciasPorStatus.has(status) ? indice : maior;
  }, -1);

  const quantidade = Math.min(indiceUltimoAlcancado + 2, CAMINHO_STATUS.length);

  return CAMINHO_STATUS.slice(0, quantidade).map((status) => {
    const ativo = ocorrenciasPorStatus.has(status);
    return {
      status,
      rotulo: STATUS_ROTULOS[status] ?? status,
      ativo,
      ocorridoEm: ativo ? ocorrenciasPorStatus.get(status) : undefined,
    };
  });
}
