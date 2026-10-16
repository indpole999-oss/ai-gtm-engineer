"""Shared fixed-window auth admission, using database time and atomic counters."""
import hashlib
import hmac
from sqlalchemy import Column, String, BigInteger, Integer, Index, delete, text
from backend.database import Base, engine
from backend.config import settings


class AuthAdmissionBucket(Base):
    __tablename__ = "auth_admission_buckets"
    key = Column(String(64), primary_key=True)
    window = Column(BigInteger, primary_key=True)
    attempts = Column(Integer, nullable=False)
    __table_args__ = (Index("ix_auth_admission_window", "window"),)


async def database_window(connection):
    query = "SELECT extract(epoch FROM clock_timestamp())" if connection.dialect.name == "postgresql" else "SELECT strftime('%s','now')"
    return int(await connection.scalar(text(query))) // 60


async def allow_auth(peer, *, database=None, peer_limit=None, global_limit=None):
    database = database or engine
    peer_limit = peer_limit or settings.AUTH_PEER_LIMIT
    global_limit = global_limit or settings.AUTH_GLOBAL_LIMIT
    identity = hmac.new(settings.SECRET_KEY.encode(), peer.encode(), hashlib.sha256).hexdigest()
    table = AuthAdmissionBucket.__table__
    async with database.begin() as connection:
        if connection.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
        elif connection.dialect.name == "sqlite":
            from sqlalchemy.dialects.sqlite import insert
        else:
            raise RuntimeError("Unsupported admission store")
        window = await database_window(connection)
        # Ephemeral abuse counters only, never customer/audit evidence. The global
        # bucket bounds new keys to the configured global rate per minute.
        await connection.execute(delete(table).where(table.c.window < window - 1))
        for key, limit in (("global", global_limit), (identity, peer_limit)):
            stmt = insert(table).values(key=key, window=window, attempts=1)
            stmt = stmt.on_conflict_do_update(index_elements=[table.c.key, table.c.window],
                set_={"attempts": table.c.attempts + 1}, where=table.c.attempts < limit).returning(table.c.attempts)
            if (await connection.execute(stmt)).scalar_one_or_none() is None:
                return False
    return True
