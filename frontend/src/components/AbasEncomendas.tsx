import { Nav } from 'react-bootstrap';
import { GRUPOS } from '../types';

interface AbasEncomendasProps {
  grupoAtivo: string;
  contagens: Record<string, number>;
  aoTrocar: (grupo: string) => void;
}

export function AbasEncomendas({
  grupoAtivo,
  contagens,
  aoTrocar,
}: AbasEncomendasProps): JSX.Element {
  return (
    <Nav
      variant="tabs"
      activeKey={grupoAtivo}
      onSelect={(chave) => {
        if (chave) {
          aoTrocar(chave);
        }
      }}
      className="abas-encomendas mb-3"
    >
      {GRUPOS.map(({ chave, rotulo }) => (
        <Nav.Item key={chave}>
          <Nav.Link eventKey={chave}>
            {rotulo}
            <span className="contagem-aba">{contagens[chave] ?? 0}</span>
          </Nav.Link>
        </Nav.Item>
      ))}
    </Nav>
  );
}
