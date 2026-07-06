import logging
from uuid import UUID

from sqlalchemy import select, or_, text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.backends.base import MemoryBackend
from app.memory.errors import PostgresUnavailableError
from app.memory.types import MemoryDocument, MemoryQuery

logger = logging.getLogger(__name__)


class PostgresFullTextBackend(MemoryBackend):
    def __init__(self, session_factory, *args, **kwargs):
        self.session_factory = session_factory

    async def search(self, query: MemoryQuery) -> list[MemoryDocument]:
        try:
            async with self.session_factory() as session:
                from app.models.memory_document import MemoryDocument as ORMModel

                stmt = (
                    select(ORMModel)
                    .where(ORMModel.user_id == query.user_id)
                    .order_by(
                        sa_text(
                            "ts_rank(to_tsvector('english', content), plainto_tsquery('english', :q)) DESC"
                        ).bindparams(q=query.text)
                    )
                    .limit(query.top_k)
                )

                result = await session.execute(stmt)
                rows = result.scalars().all()

                return [
                    MemoryDocument(
                        id=row.id,
                        title=row.title,
                        content=row.content,
                        user_id=row.user_id,
                        created_at=row.created_at,
                        score=None,
                        metadata={},
                    )
                    for row in rows
                ]

        except Exception as e:
            logger.warning("PostgreSQL full-text search failed: %s", e)
            raise PostgresUnavailableError(
                f"PostgreSQL full-text search failed: {e}"
            ) from e

    async def store(self, document: MemoryDocument) -> None:
        try:
            async with self.session_factory() as session:
                from app.models.memory_document import MemoryDocument as ORMModel

                existing = await session.get(ORMModel, document.id)
                if existing:
                    existing.title = document.title
                    existing.content = document.content
                else:
                    session.add(
                        ORMModel(
                            id=document.id,
                            user_id=document.user_id,
                            title=document.title,
                            content=document.content,
                        )
                    )
                await session.commit()

        except Exception as e:
            logger.warning("PostgreSQL store failed: %s", e)
            raise PostgresUnavailableError(
                f"PostgreSQL store failed: {e}"
            ) from e

    async def delete(self, document_id: UUID) -> None:
        try:
            async with self.session_factory() as session:
                from app.models.memory_document import MemoryDocument as ORMModel

                obj = await session.get(ORMModel, document_id)
                if obj:
                    await session.delete(obj)
                    await session.commit()

        except Exception as e:
            logger.warning("PostgreSQL delete failed: %s", e)
            raise PostgresUnavailableError(
                f"PostgreSQL delete failed: {e}"
            ) from e

    async def health(self) -> bool:
        try:
            async with self.session_factory() as session:
                await session.execute(sa_text("SELECT 1"))
                return True
        except Exception:
            return False
