"""Connect to blob storage: the local Azurite emulator or a real Azure Data Lake."""

from azure.storage.blob import BlobServiceClient, ContainerClient

from tillflow_retail_etl.config import Settings


def get_blob_service(settings: Settings) -> BlobServiceClient:
    """Return a client for the storage account chosen by STORAGE_MODE."""
    if settings.storage_mode == "azurite":
        return BlobServiceClient.from_connection_string(settings.azurite_connection_string)

    # Real Azure: authenticate as the logged-in developer (az login). No keys involved.
    from azure.identity import DefaultAzureCredential

    if not settings.azure_storage_account:
        raise ValueError("AZURE_STORAGE_ACCOUNT must be set when STORAGE_MODE=azure")

    account_url = f"https://{settings.azure_storage_account}.blob.core.windows.net"
    return BlobServiceClient(account_url, credential=DefaultAzureCredential())


def get_container(settings: Settings, name: str) -> ContainerClient:
    """Return a client for one container, e.g. 'landing'."""
    return get_blob_service(settings).get_container_client(name)
