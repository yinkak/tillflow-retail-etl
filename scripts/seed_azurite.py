"""Upload the 100-row sample to the local Azurite emulator, so the pipeline runs without Azure."""

from pathlib import Path

from tillflow_retail_etl.config import get_settings
from tillflow_retail_etl.storage import get_container

SAMPLE = Path("tests/fixtures/sample_100.csv.gz")


def main() -> None:
    settings = get_settings()
    if settings.storage_mode != "azurite":
        raise SystemExit("seed_azurite only runs with STORAGE_MODE=azurite")

    container = get_container(settings, settings.container_landing)
    if not container.exists():
        container.create_container()

    with SAMPLE.open("rb") as fh:
        container.upload_blob(SAMPLE.name, fh, overwrite=True)
    print(f"Uploaded {SAMPLE} to Azurite container '{settings.container_landing}'")


if __name__ == "__main__":
    main()
