import io
import json
import zipfile

import aiohttp
import pandas as pd

from sg_api_client_base import SGAPIClient, prettify_file_label, to_safe_file_label

DEFAULT_URL = "https://api.solargis.com/tmy/data-request"


class TMYAPIClient(SGAPIClient):
    """
    Client for the TMY API
    """

    def __init__(self, dest_folder: str, token: str, url: str = DEFAULT_URL):
        super().__init__(token=token, dest_folder=dest_folder, url=url)
        self.zipped_files = {}
        self._create_dataframes = False

    async def retrieve_all_data(
        self,
        requests: dict | None = None,
        create_dataframes: bool = False,
        save: bool = True,
    ):
        """
        Retrieve data from the API.

        requests: dict of {"name": request} or None. If you create requests using add_request method, leave this as None.

        create_dataframes: bool. If True, create pandas DataFrames from the API response and hold it in client's
            attribute datasets. If True, the client will ALWAYS download also SOLARGIS_JSON format, even if not
            specified in the request.

        save: bool. If True, save the data and metadata to the destination folder.
        """
        requests = requests or self._requests
        self._create_dataframes = create_dataframes
        if create_dataframes:
            for request in requests.values():
                if "SOLARGIS_JSON" not in request["outputFormats"]:
                    request["outputFormats"].append("SOLARGIS_JSON")
        return await super().retrieve_all_data(requests, save)

    async def read_data(
        self, session: aiohttp.ClientSession, download_url: str, name: str
    ):
        async with session.get(download_url) as response:
            self._file_labels_from_api[name] = prettify_file_label(response.url.name)
            data_bytes_zipped = await response.read()
            self.zipped_files[name] = data_bytes_zipped
            zipfile_obj = zipfile.ZipFile(io.BytesIO(data_bytes_zipped))
            json_filename = next(
                (fname for fname in zipfile_obj.namelist() if fname.endswith(".json")),
                None,
            )
            if self._create_dataframes and json_filename:
                data_bytes = zipfile_obj.read(json_filename)
                data_json = json.loads(data_bytes.decode("utf-8"))
                sg_data = pd.DataFrame.from_dict(data_json.pop("data"))
                sg_data.index = pd.to_datetime(sg_data["DATETIME"])
                sg_data.drop(columns=["DATETIME"], inplace=True)
                metadata = data_json
                return sg_data, metadata
            else:
                return None, None

    def save_data_and_metadata(self, name: str, data, metadata):
        self.dest_folder.mkdir(parents=True, exist_ok=True)
        filename = self._file_labels_from_api.get(name, name)
        try:
            data_path = f"{self.dest_folder}/{filename}"
            with open(data_path, "wb") as f:
                f.write(self.zipped_files[name])
            print(f"Zipped data for {name} saved to {data_path}")
        except Exception as e:
            print(f"Error while saving data for {name}: {e}")

    @staticmethod
    def create_request_dict(
        **kwargs,
    ) -> dict:
        """
        Full request example:
        {
            "fileLabel": "example_file_label",
            "latitude":35.317366,
            "longitude": -117.246094,
            "outputFormats": [
                "SOLARGIS_CSV",
                "SOLARGIS_JSON"
            ],
            "siteName": "Basic example Site",
            "timeStep": "PT60M",
            "tmyScenario": "P50"
        }
        """
        if "site_name" in kwargs:
            kwargs["siteName"] = kwargs.pop("site_name")
        if "siteName" in kwargs and "fileLabel" not in kwargs:
            kwargs["fileLabel"] = kwargs["siteName"]

        if "lat" in kwargs and "latitude" not in kwargs:
            kwargs["latitude"] = kwargs.pop("lat")
        if "long" in kwargs and "longitude" not in kwargs:
            kwargs["longitude"] = kwargs.pop("long")

        kwargs["fileLabel"] = to_safe_file_label_tmy(kwargs["fileLabel"])

        default_values = {
            "outputFormats": ["SOLARGIS_JSON", "SOLARGIS_CSV"],
            "timeStep": "PT60M",
            "tmyScenario": "P50",
        }

        default_values.update(kwargs)

        return default_values


def to_safe_file_label_tmy(file_label: str) -> str:
    safe_but_long = to_safe_file_label(file_label)
    return safe_but_long[:10]

def tmy(token_tmy_api: str, lat: float, long: float, time_step: str, integration_api_call: bool = False, **kwargs):
    import asyncio
    if integration_api_call:
        site_name = f"Pro example Site"
        url = "https://api.solargis.com/tmy-integration/data-request"
    else:
        site_name = f"{lat}_{long}"
        url = "https://api.solargis.com/tmy/data-request"

    client = TMYAPIClient(token=token_tmy_api, dest_folder="", url=url)
    client.add_request(
        site_name=site_name, lat=lat, long=long, timeStep=time_step, **kwargs
    )
    datasets = asyncio.run(client.retrieve_all_data(create_dataframes=True))

    return datasets[site_name]

