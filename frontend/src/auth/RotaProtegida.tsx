import { Navigate, useLocation } from 'react-router-dom';
import { useAutenticacao } from './ContextoAutenticacao';

export function RotaProtegida({
  children,
}: {
  children: React.ReactNode;
}): React.ReactNode {
  const { estaAutenticado, carregando } = useAutenticacao();
  const location = useLocation();

  if (carregando) {
    return null;
  }

  if (!estaAutenticado) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}
