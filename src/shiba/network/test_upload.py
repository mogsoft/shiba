import pathlib
import toolviper
import shiba.network.api as api


path = pathlib.Path().cwd()
toolviper.utils.data.update(path=str(path))

entry = {
    "file": str(path.joinpath("random.ms.zarr.zip")),
    "path": "astrohack",
    "dtype": "CASA image",
    "telescope": "VLA",
    "mode": "Simulated"
}

toolviper.utils.tools.add_entry(
        entries=[entry],
        manifest=str(path.joinpath("file.download.json")),
        versioning="patch"
)

api.upload(
    files=["random.ms.zarr.zip"],
    manifest=str(path.joinpath("file.download.json"))
)