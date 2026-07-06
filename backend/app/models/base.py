from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from uuid import uuid4
import uuid as _uuid


class Base(DeclarativeBase):
    pass


class UUIDMixin:
    id: Mapped[_uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
