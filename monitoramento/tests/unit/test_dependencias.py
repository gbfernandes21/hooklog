import pytest

from app.core.dependencias import exigir_admin, exigir_usuario
from app.core.erros import ErroDeDominio
from app.core.seguranca import UsuarioAutenticado
from app.models.enums import Papel


async def test_exigir_usuario_permite_user() -> None:
    usuario = UsuarioAutenticado(id=1, papel=Papel.USER)

    resultado = await exigir_usuario(usuario)

    assert resultado.papel == Papel.USER
    assert resultado.id == 1


async def test_exigir_usuario_recusa_admin_com_403() -> None:
    usuario = UsuarioAutenticado(id=None, papel=Papel.ADMIN)

    with pytest.raises(ErroDeDominio) as excinfo:
        await exigir_usuario(usuario)

    assert excinfo.value.status_code == 403
    assert excinfo.value.codigo == "ACESSO_NEGADO"


async def test_exigir_admin_permite_admin() -> None:
    usuario = UsuarioAutenticado(id=None, papel=Papel.ADMIN)

    resultado = await exigir_admin(usuario)

    assert resultado.papel == Papel.ADMIN
    assert resultado.id is None


async def test_exigir_admin_recusa_user_com_403() -> None:
    usuario = UsuarioAutenticado(id=1, papel=Papel.USER)

    with pytest.raises(ErroDeDominio) as excinfo:
        await exigir_admin(usuario)

    assert excinfo.value.status_code == 403
    assert excinfo.value.codigo == "ACESSO_NEGADO"
