import os
import time

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError


def wait_for_mysql(uri: str, timeout: int = 60, interval: float = 2) -> None:
    engine = create_engine(uri)
    start = time.time()
    while True:
        try:
            with engine.connect():
                print("MySQL server is ready.")
                break
        except OperationalError:
            elapsed = time.time() - start
            if elapsed > timeout:
                raise TimeoutError(
                    "MySQL server did not become available within timeout."
                )
            print("Waiting for MySQL server...")
            time.sleep(interval)


def ensure_revision(alembic_cfg):
    rev_dir = os.path.join(
        os.path.dirname(alembic_cfg.config_file_name), "alembic", "versions"
    )

    has_py_files = os.path.isdir(rev_dir) and any(
        f.endswith(".py") for f in os.listdir(rev_dir)
    )

    if not has_py_files:
        print("Creating initial revision...")
        command.revision(alembic_cfg, message="Initial", autogenerate=True)
    else:
        print("Revision(s) already exist.")


def run_migrations():
    cfg = Config("alembic.ini")
    ensure_revision(cfg)
    command.upgrade(cfg, "head")


if __name__ == "__main__":
    host = os.getenv("DB_HOST")
    passwd = os.getenv("DB_PASS")
    user = os.getenv("DB_USER")
    db_name = os.getenv("DB_NAME")
    mysql_uri = f"mysql+pymysql://{user}:{passwd}@{host}:3306/{db_name}"
    wait_for_mysql(mysql_uri)
    run_migrations()
