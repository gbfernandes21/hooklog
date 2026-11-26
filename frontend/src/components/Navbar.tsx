import { NavLink, useLocation } from 'react-router-dom';
import { Navbar, Nav, Container } from 'react-bootstrap';
import { useAutenticacao } from '../auth/ContextoAutenticacao';
import logoInvertido from '../../public/logo-invertido.svg';

export function NavbarApp(): JSX.Element | null {
  const { estaAutenticado, ehAdmin, ehUsuario, logout } = useAutenticacao();
  const location = useLocation();

  if (!estaAutenticado) {
    return null;
  }

  return (
    <Navbar bg="dark" variant="dark" expand="lg" className="mb-4">
      <Container>
        <Navbar.Brand as="a" href="/">
          <img src={logoInvertido} alt="HookLog" className="logo-vertical" />
        </Navbar.Brand>
        <Navbar.Toggle aria-controls="nav-hooklog" />
        <Navbar.Collapse id="nav-hooklog">
          <Nav className="me-auto">
            {ehUsuario && (
              <Nav.Item>
                <NavLink
                  to="/encomendas"
                  end={location.pathname === '/encomendas'}
                  className={({ isActive }) =>
                    isActive ? 'nav-link active' : 'nav-link'
                  }
                >
                  Minhas encomendas
                </NavLink>
              </Nav.Item>
            )}
            {ehAdmin && (
              <>
                <Nav.Item>
                  <NavLink
                    to="/admin"
                    end={location.pathname === '/admin'}
                    className={({ isActive }) =>
                      isActive ? 'nav-link active' : 'nav-link'
                    }
                  >
                    Todas as encomendas
                  </NavLink>
                </Nav.Item>
                <Nav.Item>
                  <a
                    href="/transportadora/"
                    className="nav-link"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Transportadora
                  </a>
                </Nav.Item>
              </>
            )}
          </Nav>
          <Nav>
            <Nav.Item>
              <button
                type="button"
                className="btn btn-link text-white text-decoration-none p-0"
                onClick={logout}
              >
                Sair
              </button>
            </Nav.Item>
          </Nav>
        </Navbar.Collapse>
      </Container>
    </Navbar>
  );
}
