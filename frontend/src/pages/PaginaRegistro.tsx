import { useState } from 'react';
import { Container, Row, Col, Card, Button, Form, Alert, InputGroup } from 'react-bootstrap';
import { Link } from 'react-router-dom';
import { useAutenticacao } from '../auth/ContextoAutenticacao';
import logoVertical from '../../public/logo-vertical.svg';

const OlhoVisibilidade = ({ visivel }: { visivel: boolean }) => (
  <svg
    width="20"
    height="20"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    {visivel ? (
      <>
        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
        <circle cx="12" cy="12" r="3" />
      </>
    ) : (
      <>
        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
        <path d="M12 7a5 5 0 0 1 5 5 5 5 0 0 1-5 5 5 5 0 0 1-5-5 5 5 0 0 1 5-5z" />
      </>
    )}
  </svg>
);

export function PaginaRegistro(): JSX.Element {
  const [email, setEmail] = useState('');
  const [senha, setSenha] = useState('');
  const [mostrarSenha, setMostrarSenha] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);
  const { registrar } = useAutenticacao();

  const tipoSenha = mostrarSenha ? 'text' : senha ? 'password' : 'text';

  async function manusearRegistro(evento: React.FormEvent): Promise<void> {
    evento.preventDefault();
    setErro(null);
    setCarregando(true);
    try {
      await registrar({ email, senha });
    } catch (erroCapture: any) {
      setErro(
        erroCapture.response?.data?.codigo === 'EMAIL_JA_CADASTRADO'
          ? 'Este e-mail já está cadastrado.'
          : 'Não foi possível criar a conta. Tente novamente.'
      );
    } finally {
      setCarregando(false);
    }
  }

  return (
    <Container className="d-flex min-vh-100 align-items-center justify-content-center">
      <Row className="w-100 justify-content-center">
        <Col className="d-flex justify-content-center">
          <Card className="login-card">
            <div className="text-center mb-4">
              <img src={logoVertical} alt="HookLog" className="logo-vertical" />
            </div>

            <Alert variant="danger" className="alerta-erro" show={!!erro} dismissible>
              {erro}
            </Alert>

            <Form onSubmit={manusearRegistro}>
              <Form.Group className="mb-3">
                <Form.Label>E-mail</Form.Label>
                <Form.Control
                  type="email"
                  placeholder="seu@email.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </Form.Group>
              <Form.Group className="mb-3">
                <Form.Label>Senha (mínimo 8 caracteres)</Form.Label>
                <InputGroup>
                  <Form.Control
                    type={tipoSenha}
                    placeholder="••••••••"
                    value={senha}
                    onChange={(e) => setSenha(e.target.value)}
                    required
                  />
                  <InputGroup.Text>
                    <button
                      type="button"
                      className="btn btn-outline-secondary border-0 bg-transparent p-0"
                      onClick={() => setMostrarSenha(!mostrarSenha)}
                      aria-label={mostrarSenha ? 'Ocultar senha' : 'Mostrar senha'}
                    >
                      <OlhoVisibilidade visivel={mostrarSenha} />
                    </button>
                  </InputGroup.Text>
                </InputGroup>
              </Form.Group>
              <Button type="submit" variant="primary" disabled={carregando} className="w-100">
                {carregando ? 'Cadastrando...' : 'Criar conta'}
              </Button>
            </Form>

            <div className="text-center mt-4 text-muted">
              Já tem uma conta?{' '}
              <Link to="/login" className="btn btn-link p-0 text-decoration-none">
                Entrar
              </Link>
            </div>
          </Card>
        </Col>
      </Row>
    </Container>
  );
}
