"""Transform: run the SQL files that build silver (staging) and gold (marts) tables."""

import logging
from pathlib import Path

import psycopg

from tillflow_retail_etl.config import get_settings
from tillflow_retail_etl.load import connect

logger = logging.getLogger(__name__)

SQL_DIR = Path(__file__).resolve().parents[2] / "sql"
LAYERS = ["staging", "marts"]  # order matters: marts are built from staging


def sql_files() -> list[Path]:
    """Every transform file, layer by layer, in filename order."""
    return [path for layer in LAYERS for path in sorted((SQL_DIR / layer).glob("*.sql"))]


def run_transforms(conn: psycopg.Connection) -> None:
    """Run all transforms in ONE transaction: every table updates together, or none do."""
    with conn.transaction():
        for path in sql_files():
            logger.info("Running %s", path.relative_to(SQL_DIR))
            conn.execute(path.read_text())


def main() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    with connect(settings) as conn:
        run_transforms(conn)
    logger.info("Transforms complete")


if __name__ == "__main__":
    main()
