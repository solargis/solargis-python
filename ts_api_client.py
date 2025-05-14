import json

import pandas as pd

from sg_api_client_base import SGAPIClient, prettify_file_label, to_safe_file_label

DEFAULT_PARAM_LIST = [
    "GHI",
    "DNI",
    "DIF",
    "GHI_NOSHD",
    "DNI_NOSHD",
    "DIF_NOSHD",
    "CI_FLAG",
    "SUN_ELEVATION",
    "SUN_AZIMUTH",
    "TEMP",
    "WS",
    "WD",
    "WG",
    "RH",
    "AP",
    "PWAT",
    "PREC",
    "TD",
    "WBT",
    "SDWE",
    "SFWE",
]

TIME_ALIGNMENT_MAPPING = {
    "PT15M": "CENTER",
    "P1H": "CENTER",
    "P1D": "START",
    "P1M": "START",
    "P1Y": "START",
}

DEFAULT_URL = "https://api.solargis.com/ts/data-request"


class TSAPIClient(SGAPIClient):
    """
    Client for the TS API
    """

    def __init__(self, dest_folder: str, token: str, url: str = DEFAULT_URL):
        super().__init__(dest_folder=dest_folder, token=token, url=url)

    async def read_data(
        self, session: aiohttp.ClientSession, download_url: str, name: str
    ):
        async with session.get(download_url) as response:
            self._file_labels_from_api[name] = prettify_file_label(response.url.name)
            data_bytes = await response.read()
            data_json = json.loads(data_bytes.decode("utf-8"))

        sg_data = pd.DataFrame.from_dict(data_json.pop("data"))
        sg_data.index = pd.to_datetime(sg_data["DATETIME"])
        sg_data.drop(columns=["DATETIME"], inplace=True)
        metadata = data_json

        return sg_data, metadata

    @staticmethod
    def create_request_dict(
        lat: float,
        long: float,
        site_name: str,
        parameters: list | None = None,
        from_date: str = "AUTODETECT",
        to_date: str = "LAST_MONTH",
        time_step: str = "PT15M",
        terrain_shading: bool = True,
        site_elevation: float | None = None,
        utc_offset: str = "+00:00",
        **kwargs,
    ) -> dict:
        """
        Creation of request we're going to create for TS API
        """
        if not parameters:
            parameters = DEFAULT_PARAM_LIST

        fts_data_request: dict = {
            "requestType": "TIMESERIES",
            "site": {
                "latitude": lat,
                "longitude": long,
                "name": site_name,
            },
            "timeStep": time_step,
            "columns": parameters,
            "fromDate": from_date,
            "toDate": to_date,
            "utcOffset": utc_offset,
            "timeAlignment": TIME_ALIGNMENT_MAPPING.get(time_step, "CENTER"),
            "fileLabel": to_safe_file_label(site_name),
            "terrainShading": terrain_shading,
            "outputFormat": "SOLARGIS_JSON",
            "compressOutput": False,
        }

        if site_elevation is not None:
            fts_data_request["site"]["elevation"] = site_elevation

        fts_data_request.update(kwargs)

        return fts_data_request

    def save_data_and_metadata(self, name: str, data: pd.DataFrame, metadata: dict):
        self.dest_folder.mkdir(parents=True, exist_ok=True)
        filename = self._file_labels_from_api.get(name, name)
        try:
            data_path = f"{self.dest_folder}/{filename}.csv"
            data.to_csv(data_path)
            print(f"Data for {name} saved to {data_path}")
        except Exception as e:
            print(f"Error while saving data for {name}: {e}")
        try:
            metadata_path = f"{self.dest_folder}/{filename}_metadata.json"
            with open(metadata_path, "w") as f:
                json.dump(metadata, f)
                print(f"Metadata for {name} saved to {metadata_path}")
        except Exception as e:
            print(f"Error while saving metadata for {name}: {e}")
