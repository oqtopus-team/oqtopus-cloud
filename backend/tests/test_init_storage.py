import io
import json
import zipfile

from oqtopus_cloud.common.storages.storage_utils import (
    DEVICE_INFO_FILE,
    get_device_info_key,
)
from scripts.seed import DEVICES
from storage.init_storage import _object_manifest


def test_object_manifest_contains_seeded_device_info() -> None:
    manifest = _object_manifest()

    for device in DEVICES:
        archive = manifest[get_device_info_key(device["id"])]
        with zipfile.ZipFile(io.BytesIO(archive)) as zip_file:
            assert zip_file.namelist() == [DEVICE_INFO_FILE]
            device_info = json.loads(zip_file.read(DEVICE_INFO_FILE))

        assert device_info["device_id"] == device["id"]
        assert [qubit["id"] for qubit in device_info["qubits"]] == list(
            range(device["n_qubits"])
        )