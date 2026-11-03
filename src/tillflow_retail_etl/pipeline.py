"""Pipeline: extract -> validate -> load for every file in the landing container."""

import logging
import tempfile
from pathlib import Path

from tillflow_retail_etl.config import get_settings
from tillflow_retail_etl.extract import iter_file_chunks, list_landing_files
from tillflow_retail_etl.load import (
    already_loaded,
    connect,
    load_file,
    mark_failed,
    record_skip,
    start_load,
)
from tillflow_retail_etl.storage import get_container
from tillflow_retail_etl.validate import split_valid_invalid

logger = logging.getLogger(__name__)


def run() -> None:
    settings = get_settings()
    container = get_container(settings, settings.container_landing)
    files = list_landing_files(container)
    logger.info("Found %d landing files in %s mode", len(files), settings.storage_mode)

    loaded = quarantined = skipped = 0
    with connect(settings) as conn, tempfile.TemporaryDirectory() as tmp:
        for landing_file in files:
            if already_loaded(conn, landing_file.name, landing_file.etag):
                record_skip(conn, landing_file.name, landing_file.etag)
                logger.info(
                    "Skipping %s: this exact version (etag %s) is already loaded",
                    landing_file.name,
                    landing_file.etag,
                )
                skipped += 1
                continue

            load_id = start_load(conn, landing_file.name, landing_file.etag)
            chunks = iter_file_chunks(container, landing_file, settings.chunk_size, Path(tmp))
            validated = (split_valid_invalid(chunk) for chunk in chunks)
            try:
                result = load_file(conn, landing_file.name, load_id, validated)
            except Exception as exc:
                conn.rollback()
                mark_failed(conn, load_id, repr(exc))
                logger.exception(
                    "Load %d of %s failed; nothing from it was kept", load_id, landing_file.name
                )
                raise

            logger.info(
                "Loaded %s: %d rows loaded, %d quarantined (load_id %d)",
                landing_file.name,
                result.rows_loaded,
                result.rows_quarantined,
                load_id,
            )
            loaded += result.rows_loaded
            quarantined += result.rows_quarantined

    logger.info(
        "Pipeline complete: %d rows loaded, %d quarantined, %d files skipped",
        loaded,
        quarantined,
        skipped,
    )


def main() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    logging.getLogger("azure").setLevel(logging.WARNING)
    run()


if __name__ == "__main__":
    main()
