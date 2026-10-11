"""Fail closed before opening destructive PostgreSQL test connections."""
import os
from sqlalchemy.engine import make_url


def require_disposable_service(value):
    url = make_url(value)
    if (os.environ.get("POSTGRES_DISPOSABLE") != "1"
            or url.host not in {"localhost", "127.0.0.1", "::1"}
            or url.database != "postgres"
            or url.query):
        raise RuntimeError("Destructive tests require an explicitly disposable loopback PostgreSQL service")
    return url


def verify_major(connection):
    expected = os.environ.get("POSTGRES_EXPECTED_MAJOR")
    if not expected or connection.server_version // 10000 != int(expected):
        connection.close()
        raise RuntimeError("Disposable PostgreSQL major version does not match the expected CI version")
