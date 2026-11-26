import { Navigate } from 'react-router-dom';
import { useAutenticacao } from './ContextoAutenticacao';

export function RotaAdmin({
  children,
}: {
  children: React.ReactNode;
}): React.ReactNode {
  const { ehAdmin, carregando } = useAutenticacao();

  if (carregando) {
    return null;
  }

  if (!ehAdmin) {
    return <Navigate to="/encomendas" replace />;
  }

  return <>{children}</>;
}
