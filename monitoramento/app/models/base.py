from sqlalchemy.orm import DeclarativeBase

from app.core.banco_dados import METADATA


class Base(DeclarativeBase):
    metadata = METADATA
