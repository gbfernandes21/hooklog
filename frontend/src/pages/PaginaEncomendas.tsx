import { useMemo, useState } from 'react';
import { Alert, Button, Container, Modal, Spinner, Table } from 'react-bootstrap';
import { Link } from 'react-router-dom';
import { AbasEncomendas } from '../components/AbasEncomendas';
import { ModalEncomenda } from '../components/ModalEncomenda';
import { SeloStatus } from '../components/SeloStatus';
import {
  useEncomendas,
  useExcluirEncomenda,
  useRegistrarEncomenda,
} from '../hooks/useEncomendas';
import {
  Encomenda,
  GRUPOS,
  GRUPO_A_CAMINHO,
  GRUPO_ENTREGUES,
  GRUPO_NAO_ENCAMINHADAS,
} from '../types';
import { formatarDataHoraBrasilia } from '../utils/datas';
import { extrairErro } from '../utils/erros';

function mensagemVazia(grupo: string): string {
  if (grupo === GRUPO_A_CAMINHO) {
    return 'Nenhuma encomenda a caminho.';
  }
  if (grupo === GRUPO_ENTREGUES) {
    return 'Nenhuma encomenda entregue ainda.';
  }
  return 'Você ainda não cadastrou encomendas.';
}

export default function PaginaEncomendas(): JSX.Element {
  const { data, isLoading, isError, refetch } = useEncomendas();
  const exclusao = useExcluirEncomenda();
  const registro = useRegistrarEncomenda();

  const [grupoAtivo, setGrupoAtivo] = useState<string>(GRUPO_NAO_ENCAMINHADAS);
  const [modalAberto, setModalAberto] = useState(false);
  const [encomendaEmEdicao, setEncomendaEmEdicao] = useState<Encomenda | null>(null);
  const [encomendaParaExcluir, setEncomendaParaExcluir] = useState<Encomenda | null>(null);
  const [erroAcao, setErroAcao] = useState<string | null>(null);

  const encomendas = useMemo(() => data ?? [], [data]);
  const ehAbaEntregues = grupoAtivo === GRUPO_ENTREGUES;

  const contagens = useMemo(() => {
    const resultado: Record<string, number> = {};
    for (const grupo of GRUPOS) {
      resultado[grupo.chave] = 0;
    }
    for (const encomenda of encomendas) {
      resultado[encomenda.grupo] = (resultado[encomenda.grupo] ?? 0) + 1;
    }
    return resultado;
  }, [encomendas]);

  const encomendasDaAba = useMemo(
    () => encomendas.filter((encomenda) => encomenda.grupo === grupoAtivo),
    [encomendas, grupoAtivo]
  );

  function abrirCriacao(): void {
    setErroAcao(null);
    setEncomendaEmEdicao(null);
    setModalAberto(true);
  }

  function abrirEdicao(encomenda: Encomenda): void {
    setErroAcao(null);
    setEncomendaEmEdicao(encomenda);
    setModalAberto(true);
  }

  function fecharModal(): void {
    setModalAberto(false);
    setEncomendaEmEdicao(null);
  }

  function concluirModal(encomenda: Encomenda): void {
    setModalAberto(false);
    setEncomendaEmEdicao(null);
    setGrupoAtivo(encomenda.grupo);
  }

  async function confirmarExclusao(): Promise<void> {
    if (!encomendaParaExcluir) {
      return;
    }
    setErroAcao(null);
    try {
      await exclusao.mutateAsync(encomendaParaExcluir.id);
      setEncomendaParaExcluir(null);
    } catch (erroCapturado) {
      const { detalhe } = extrairErro(erroCapturado);
      setErroAcao(detalhe ?? 'Não foi possível excluir a encomenda.');
      setEncomendaParaExcluir(null);
    }
  }

  async function tentarRegistrar(encomenda: Encomenda): Promise<void> {
    setErroAcao(null);
    try {
      await registro.mutateAsync(encomenda.id);
    } catch (erroCapturado) {
      const { codigo, detalhe } = extrairErro(erroCapturado);
      if (codigo === 'ESTADO_INVALIDO') {
        setErroAcao('Esta encomenda não está mais em falha no registro.');
      } else {
        setErroAcao(detalhe ?? 'Não foi possível solicitar o novo registro.');
      }
    }
  }

  function renderAcoes(encomenda: Encomenda): JSX.Element {
    return (
      <div className="d-flex flex-wrap gap-2">
        {encomenda.status === 'FALHA_NO_REGISTRO' && (
          <Button
            variant="outline-primary"
            size="sm"
            onClick={() => void tentarRegistrar(encomenda)}
            disabled={registro.isPending}
          >
            Tentar registrar novamente
          </Button>
        )}
        <Link to={`/encomendas/${encomenda.id}`}>
          <Button variant="outline-secondary" size="sm">
            Ver detalhe
          </Button>
        </Link>
        <Button variant="outline-secondary" size="sm" onClick={() => abrirEdicao(encomenda)}>
          Editar
        </Button>
        <Button
          variant="outline-danger"
          size="sm"
          onClick={() => setEncomendaParaExcluir(encomenda)}
        >
          Excluir
        </Button>
      </div>
    );
  }

  return (
    <Container className="mt-4 mb-5">
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h1 className="h3 mb-0">Minhas encomendas</h1>
        <Button variant="primary" onClick={abrirCriacao}>
          Nova encomenda
        </Button>
      </div>

      <AbasEncomendas
        grupoAtivo={grupoAtivo}
        contagens={contagens}
        aoTrocar={setGrupoAtivo}
      />

      <Alert variant="danger" show={!!erroAcao} dismissible onClose={() => setErroAcao(null)}>
        {erroAcao}
      </Alert>

      {isLoading && (
        <div className="text-center py-5">
          <Spinner animation="border" role="status" />
          <p className="mt-3 text-muted mb-0">Carregando encomendas...</p>
        </div>
      )}

      {!isLoading && isError && (
        <Alert variant="danger">
          <p className="mb-2">Não foi possível carregar as encomendas.</p>
          <Button variant="outline-danger" size="sm" onClick={() => void refetch()}>
            Tentar novamente
          </Button>
        </Alert>
      )}

      {!isLoading && !isError && encomendasDaAba.length === 0 && (
        <div className="sem-dados">
          <p className="mb-3">{mensagemVazia(grupoAtivo)}</p>
          {grupoAtivo === GRUPO_NAO_ENCAMINHADAS && (
            <Button variant="primary" onClick={abrirCriacao}>
              Cadastrar encomenda
            </Button>
          )}
        </div>
      )}

      {!isLoading && !isError && encomendasDaAba.length > 0 && (
        <Table responsive hover className="align-middle tabela-encomendas">
          <thead>
            <tr>
              <th>Código</th>
              {ehAbaEntregues ? <th>Vendedor</th> : <th>Descrição</th>}
              {!ehAbaEntregues && <th>Vendedor</th>}
              {ehAbaEntregues && <th>Entregue em</th>}
              <th>Status</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            {encomendasDaAba.map((encomenda) => (
              <tr key={encomenda.id}>
                <td className="codigo-rastreio">{encomenda.codigo_rastreio}</td>
                {ehAbaEntregues ? (
                  <>
                    <td>{encomenda.vendedor}</td>
                    <td>{formatarDataHoraBrasilia(encomenda.entregue_em)}</td>
                  </>
                ) : (
                  <>
                    <td>{encomenda.descricao}</td>
                    <td>{encomenda.vendedor}</td>
                  </>
                )}
                <td>
                  <SeloStatus status={encomenda.status} />
                </td>
                <td>{renderAcoes(encomenda)}</td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}

      <ModalEncomenda
        mostrar={modalAberto}
        encomenda={encomendaEmEdicao}
        aoFechar={fecharModal}
        aoConcluir={concluirModal}
      />

      <Modal
        show={!!encomendaParaExcluir}
        onHide={() => setEncomendaParaExcluir(null)}
        centered
      >
        <Modal.Header closeButton>
          <Modal.Title>Excluir encomenda</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          Tem certeza de que deseja excluir a encomenda{' '}
          <strong>{encomendaParaExcluir?.codigo_rastreio}</strong>? Esta ação não pode ser
          desfeita.
        </Modal.Body>
        <Modal.Footer>
          <Button
            variant="secondary"
            onClick={() => setEncomendaParaExcluir(null)}
            disabled={exclusao.isPending}
          >
            Cancelar
          </Button>
          <Button
            variant="danger"
            onClick={() => void confirmarExclusao()}
            disabled={exclusao.isPending}
          >
            {exclusao.isPending ? 'Excluindo...' : 'Excluir'}
          </Button>
        </Modal.Footer>
      </Modal>
    </Container>
  );
}
