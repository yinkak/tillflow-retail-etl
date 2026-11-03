"""Extract against the Azurite emulator: listing, downloading and chunking."""

import uuid
from pathlib import Path

import pytest
from azure.storage.blob import BlobServiceClient

from tillflow_retail_etl.extract import iter_file_chunks, list_landing_files

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_100.csv.gz"
AZURITE = "UseDevelopmentStorage=true"


@pytest.fixture
def landing_container():
    """A fresh, uniquely named container per test, deleted afterwards."""
    service = BlobServiceClient.from_connection_string(AZURITE)
    container = service.get_container_client(f"test-{uuid.uuid4().hex[:8]}")
    container.create_container()
    with FIXTURE.open("rb") as fh:
        container.upload_blob("sample_100.csv.gz", fh)
    container.upload_blob("notes.txt", b"not data")  # should be ignored
    yield container
    container.delete_container()


@pytest.mark.integration
def test_lists_only_csv_gz_files(landing_container):
    files = list_landing_files(landing_container)

    assert [f.name for f in files] == ["sample_100.csv.gz"]
    assert files[0].etag  # fingerprint captured for idempotent loads later


@pytest.mark.integration
def test_reads_every_row_in_chunks(landing_container, tmp_path):
    [landing_file] = list_landing_files(landing_container)

    chunks = list(iter_file_chunks(landing_container, landing_file, 30, tmp_path))

    assert [len(chunk) for chunk in chunks] == [30, 30, 30, 10]
    assert sum(len(chunk) for chunk in chunks) == 100
