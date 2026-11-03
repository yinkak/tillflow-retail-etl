"""Extract: list files in the landing container and read them in chunks."""

import logging
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from azure.storage.blob import ContainerClient

from tillflow_retail_etl.config import get_settings
from tillflow_retail_etl.storage import get_container

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LandingFile:
    """One file in the landing container."""

    name: str
    size_bytes: int
    etag: str  # changes whenever the file changes; used later to skip files already loaded


def list_landing_files(container: ContainerClient) -> list[LandingFile]:
    """Return every .csv.gz file in the container, sorted by name."""
    files = [
        LandingFile(name=blob.name, size_bytes=blob.size, etag=blob.etag.strip('"'))
        for blob in container.list_blobs()
        if blob.name.endswith(".csv.gz")
    ]
    return sorted(files, key=lambda f: f.name)


def download_to_disk(container: ContainerClient, blob_name: str, dest_dir: Path) -> Path:
    """Stream a blob to a local file without loading it all into memory."""
    dest = dest_dir / Path(blob_name).name
    with dest.open("wb") as fh:
        container.download_blob(blob_name).readinto(fh)
    return dest


def read_chunks(path: Path, chunk_size: int) -> Iterator[pd.DataFrame]:
    """Yield the CSV in chunks, every value as text. Only truly empty cells become missing."""
    yield from pd.read_csv(
        path,
        compression="gzip",
        dtype=str,
        keep_default_na=False,
        na_values=[""],
        chunksize=chunk_size,
    )


def iter_file_chunks(
    container: ContainerClient, landing_file: LandingFile, chunk_size: int, work_dir: Path
) -> Iterator[pd.DataFrame]:
    """Download one landing file and yield it chunk by chunk, logging progress."""
    path = download_to_disk(container, landing_file.name, work_dir)
    total = 0
    for i, chunk in enumerate(read_chunks(path, chunk_size), start=1):
        total += len(chunk)
        logger.info(
            "%s chunk %d: %d rows (running total %d)", landing_file.name, i, len(chunk), total
        )
        yield chunk
    logger.info("%s finished: %d rows", landing_file.name, total)


def main() -> None:
    """Extract every landing file and report row counts (debug run, nothing is loaded yet)."""
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    logging.getLogger("azure").setLevel(logging.WARNING)  # silence per-request HTTP logs

    container = get_container(settings, settings.container_landing)
    files = list_landing_files(container)
    logger.info("Found %d landing files in %s mode", len(files), settings.storage_mode)

    grand_total = 0
    with tempfile.TemporaryDirectory() as tmp:
        for landing_file in files:
            logger.info(
                "Extracting %s (%.1f MB, etag %s)",
                landing_file.name,
                landing_file.size_bytes / 1_000_000,
                landing_file.etag,
            )
            for chunk in iter_file_chunks(container, landing_file, settings.chunk_size, Path(tmp)):
                grand_total += len(chunk)

    logger.info("Extract complete: %d files, %d rows", len(files), grand_total)


if __name__ == "__main__":
    main()
