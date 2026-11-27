import { useEffect, useState } from 'react';
import { Alert, Button, Form, Modal } from 'react-bootstrap';
import { useAtualizarEncomenda, useCriarEncomenda } from '../hooks/useEncomendas';
import { Encomenda } from '../types';
import { extrairErro } from '../utils/erros';

interface ModalEncomendaProps {
  mostrar: boolean;
  encomenda: Encomenda | null;
  aoFechar: () => void;
  aoConcluir: (encomenda: Encomenda) => void;
}

interface ErrosCampos {
  codigo_rastreio?: string;
  descricao?: string;
  vendedor?: string;
}

const PADRAO_CODIGO = /^[A-Za-z0-9-]+$/;

export function ModalEncomenda({
  mostrar,
  encomenda,
  aoFechar,
  aoConcluir,
}: ModalEncomendaProps): JSX.Element {
  const editando = encomenda !== null;
  const [codigoRastreio, setCodigoRastreio] = useState('');
  const [descricao, setDescricao] = useState('');
  const [vendedor, setVendedor] = useState('');
  const [errosCampos, setErrosCampos] = useState<ErrosCampos>({});
  const [erro, setErro] = useState<string | null>(null);

  const criacao = useCriarEncomenda();
  const atualizacao = useAtualizarEncomenda();
  const salvando = criacao.isPending || atualizacao.isPending;

  useEffect(() => {
    if (!mostrar) {
      return;
    }
    setCodigoRastreio(encomenda?.codigo_rastreio ?? '');
    setDescricao(encomenda?.descricao ?? '');
    setVendedor(encomenda?.vendedor ?? '');
    setErrosCampos({});
    setErro(null);
  }, [mostrar, encomenda]);

  function validarCampos(): ErrosCampos {
    const erros: ErrosCampos = {};
    const codigo = codigoRastreio.trim();
    const textoDescricao = descricao.trim();
    const textoVendedor = vendedor.trim();

    if (!editando) {
      if (codigo.length < 5 || codigo.length > 40) {
        erros.codigo_rastreio = 'O código deve ter entre 5 e 40 caracteres.';
      } else if (!PADRAO_CODIGO.test(codigo)) {
        erros.codigo_rastreio = 'Use apenas letras, números e hífen.';
      }
    }

    if (textoDescricao.length < 1 || textoDescricao.length > 200) {
      erros.descricao = 'A descrição deve ter entre 1 e 200 caracteres.';
    }

    if (textoVendedor.length < 1 || textoVendedor.length > 120) {
      erros.vendedor = 'O vendedor deve ter entre 1 e 120 caracteres.';
    }

    return erros;
  }

  async function manusearEnvio(evento: React.FormEvent<HTMLFormElement>): Promise<void> {
    evento.preventDefault();
    setErro(null);

    const errosEncontrados = validarCampos();
    setErrosCampos(errosEncontrados);
    if (Object.keys(errosEncontrados).length > 0) {
      return;
    }

    try {
      if (editando && encomenda) {
        const atualizada = await atualizacao.mutateAsync({
          id: encomenda.id,
          dados: {
            descricao: descricao.trim(),
            vendedor: vendedor.trim(),
          },
        });
        aoConcluir(atualizada);
      } else {
        const criada = await criacao.mutateAsync({
          codigo_rastreio: codigoRastreio.trim(),
          descricao: descricao.trim(),
          vendedor: vendedor.trim(),
        });
        aoConcluir(criada);
      }
    } catch (erroCapturado) {
      const { codigo, detalhe, status } = extrairErro(erroCapturado);
      if (codigo === 'CODIGO_RASTREIO_DUPLICADO') {
        setErro('Este código de rastreio já está cadastrado.');
      } else if (status === 422) {
        setErro('Verifique os campos informados.');
      } else {
        setErro(detalhe ?? 'Não foi possível salvar a encomenda. Tente novamente.');
      }
    }
  }

  return (
    <Modal
      show={mostrar}
      onHide={() => {
        if (!salvando) {
          aoFechar();
        }
      }}
      centered
    >
      <Form onSubmit={manusearEnvio} noValidate>
        <Modal.Header closeButton>
          <Modal.Title>{editando ? 'Editar encomenda' : 'Nova encomenda'}</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Alert variant="danger" show={!!erro} dismissible onClose={() => setErro(null)}>
            {erro}
          </Alert>

          <Form.Group className="mb-3" controlId="codigo-rastreio">
            <Form.Label>Código de rastreio</Form.Label>
            <Form.Control
              type="text"
              value={codigoRastreio}
              onChange={(evento) => setCodigoRastreio(evento.target.value)}
              isInvalid={!!errosCampos.codigo_rastreio}
              readOnly={editando}
              maxLength={40}
              placeholder="BR123456789"
            />
            {editando && (
              <Form.Text className="text-muted">O código não pode ser alterado.</Form.Text>
            )}
            <Form.Control.Feedback type="invalid">
              {errosCampos.codigo_rastreio}
            </Form.Control.Feedback>
          </Form.Group>

          <Form.Group className="mb-3" controlId="descricao">
            <Form.Label>Descrição</Form.Label>
            <Form.Control
              as="textarea"
              rows={3}
              value={descricao}
              onChange={(evento) => setDescricao(evento.target.value)}
              isInvalid={!!errosCampos.descricao}
              maxLength={200}
              placeholder="Fone de ouvido"
            />
            <Form.Control.Feedback type="invalid">{errosCampos.descricao}</Form.Control.Feedback>
          </Form.Group>

          <Form.Group className="mb-3" controlId="vendedor">
            <Form.Label>Vendedor</Form.Label>
            <Form.Control
              type="text"
              value={vendedor}
              onChange={(evento) => setVendedor(evento.target.value)}
              isInvalid={!!errosCampos.vendedor}
              maxLength={120}
              placeholder="Loja Exemplo LTDA"
            />
            <Form.Control.Feedback type="invalid">{errosCampos.vendedor}</Form.Control.Feedback>
          </Form.Group>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={aoFechar} disabled={salvando}>
            Cancelar
          </Button>
          <Button variant="primary" type="submit" disabled={salvando}>
            {salvando ? 'Salvando...' : editando ? 'Salvar alterações' : 'Cadastrar'}
          </Button>
        </Modal.Footer>
      </Form>
    </Modal>
  );
}
