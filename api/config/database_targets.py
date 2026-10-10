"""
Database connection targets — news_intel pool vs identity_spine vs maintenance direct port.
"""

from __future__ import annotations

from config.runtime import get_runtime_config


def news_intel_connect_kwargs() -> dict[str, str | int]:
    cfg = get_runtime_config()
    return {
        "host": cfg["db_host"],
        "port": int(cfg["db_port"]),
        "dbname": cfg["db_name"],
        "user": cfg["db_user"],
        "password": cfg["db_password"],
    }


def news_intel_dsn() -> str:
    kw = news_intel_connect_kwargs()
    return (
        f"host={kw['host']} port={kw['port']} dbname={kw['dbname']} "
        f"user={kw['user']} password={kw['password']}"
    )


def spine_dsn() -> str:
    cfg = get_runtime_config()
    return (
        f"host={cfg['identity_spine_host']} port={cfg['identity_spine_port']} "
        f"dbname={cfg['identity_spine_db']} user={cfg['identity_spine_user']} "
        f"password={cfg['identity_spine_password']}"
    )


def maintenance_connect_kwargs() -> dict[str, str | int]:
    """
    Maintenance scripts bypass PgBouncer when DB_PORT=6432 on localhost.
    """
    cfg = get_runtime_config()
    host = str(cfg["db_host"])
    env_port = int(cfg["db_port"])
    if host in ("127.0.0.1", "localhost") and env_port == 6432:
        port = int(cfg["db_maintenance_port"])
    else:
        port = env_port
    return {
        "host": host,
        "port": port,
        "dbname": cfg["db_name"],
        "user": cfg["db_user"],
        "password": cfg["db_password"],
    }
