import { Navigate, Routes, Route, useLocation } from 'react-router-dom';
import { ProvedorAutenticacao, useAutenticacao } from './auth/ContextoAutenticacao';
import { RotaProtegida } from './auth/RotaProtegida';
import { RotaAdmin } from './auth/RotaAdmin';
import { NavbarApp } from './components/Navbar';
import { PaginaLogin } from './pages/PaginaLogin';
import { PaginaRegistro } from './pages/PaginaRegistro';
import PaginaEncomendas from './pages/PaginaEncomendas';
import PaginaAdmin from './pages/PaginaAdmin';
import PaginaDetalheEncomenda from './pages/PaginaDetalheEncomenda';

function RedirectOnLoad(): React.ReactNode {
  const { usuario, carregando, ehAdmin, ehUsuario } = useAutenticacao();
  const { pathname } = useLocation();

  if (carregando) {
    return null;
  }

  if (!usuario) {
    return null;
  }

  if (ehAdmin && (pathname === '/admin' || pathname.startsWith('/admin/'))) {
    return null;
  }

  if (ehAdmin) {
    return <Navigate to="/admin" replace />;
  }

  if (ehUsuario && (pathname === '/encomendas' || pathname.startsWith('/encomendas/'))) {
    return null;
  }

  if (ehUsuario) {
    return <Navigate to="/encomendas" replace />;
  }

  return null;
}

export default function App(): JSX.Element {
  return (
    <ProvedorAutenticacao>
      <RedirectOnLoad />
      <NavbarApp />
      <Routes>
        <Route path="/" element={<Navigate to="/encomendas" replace />} />
        <Route path="/login" element={<PaginaLogin />} />
        <Route path="/registro" element={<PaginaRegistro />} />
        <Route
          path="/encomendas"
          element={
            <RotaProtegida>
              <PaginaEncomendas />
            </RotaProtegida>
          }
        />
        <Route
          path="/encomendas/:id"
          element={
            <RotaProtegida>
              <PaginaDetalheEncomenda />
            </RotaProtegida>
          }
        />
        <Route
          path="/admin"
          element={
            <RotaProtegida>
              <RotaAdmin>
                <PaginaAdmin />
              </RotaAdmin>
            </RotaProtegida>
          }
        />
        <Route
          path="/admin/encomendas/:id"
          element={
            <RotaProtegida>
              <RotaAdmin>
                <PaginaDetalheEncomenda />
              </RotaAdmin>
            </RotaProtegida>
          }
        />
      </Routes>
    </ProvedorAutenticacao>
  );
}
