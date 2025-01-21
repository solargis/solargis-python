import asyncio
import datetime
import json
import pathlib

import aiohttp
import pandas as pd
import re


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


class SGAPIClient:
    def __init__(
        self, token: str, dest_folder: str | pathlib.Path, url: str | None = None
    ):
        """
        token:
        """
        self.url = url or DEFAULT_URL
        self.dest_folder = pathlib.Path(dest_folder)
        self.datasets = {}
        self.metadata = {}
        self._requests = {}
        self._file_labels_from_api = {}
        self._headers = {
            "Authorization": f"Bearer {token}",
        }

    def add_request(self, site_name: str, **kwargs):
        kwargs["site_name"] = site_name
        request = create_request_dict(**kwargs)
        self._requests[site_name] = request

    async def retrieve_data(self, requests=None, save=True):
        """
        requests: dict of {"name": request}
        """
        if not requests:
            requests = self._requests
        async for name, data, metadata in self._retrieve_data(requests):
            self.datasets[name] = data
            self.metadata[name] = metadata
        if save:
            self.save_data_and_metadata()
        return self.datasets

    async def _retrieve_data(self, requests: dict):
        """
        requests: dict of {"name": request}
        """
        async with aiohttp.ClientSession() as session:
            tasks = [
                self.fetch_task_ids(session, request) for request in requests.values()
            ]
            request_ids = await asyncio.gather(*tasks, return_exceptions=True)

            # Create tasks for waiting for data concurrently
            data_tasks = [
                self.wait_for_data(session, request_id) for request_id in request_ids
            ]
            results = await asyncio.gather(*data_tasks, return_exceptions=True)

            for name, (download_url, status) in zip(requests.keys(), results):
                if status == "success":
                    data, metadata = await self.read_data(session, download_url, name)
                    yield name, data, metadata
                else:
                    print(f"Error while retrieving data for {name}, status: {status}")
                    yield name, None, None

    async def fetch_task_ids(self, session, data_request):
        print(f"Going to send request to Solargis TS API")
        r = json.dumps(data_request)
        async with session.post(self.url, data=r, headers=self._headers) as response:
            response_json = await response.json()

            if "requestId" in response_json:
                request_id = response_json.get("requestId")
                print(f"request_id {request_id} was created")
                return request_id
            else:
                print(
                    f"Error while sending request to Solargis TS API: {response_json}"
                )
                return None

    async def wait_for_data(self, session, request_id):
        if request_id is None:
            return None, "invalid request_id"
        status_endpoint = f"{self.url}/{request_id}"
        status = None
        while status != "success":
            async with session.get(status_endpoint, headers=self._headers) as response:
                response_status = await response.json()
                if "status" not in response_status:
                    raise ValueError(
                        f"response_status does not include status key {response_status}"
                    )
                status = response_status["status"]
                if status == "error":
                    return None, status
                print(
                    f'[{datetime.datetime.now()} ]Current status of {request_id}: "{status}"'
                )
                await asyncio.sleep(4)

        if status == "success":
            return response_status["downloadUrl"], status
        else:
            print(f"Error while waiting for data for {request_id}, status: {status}")
            return None, status

    async def read_data(self, session, download_url, name):
        async with session.get(download_url) as response:
            self._file_labels_from_api[name] = prettify_file_label(response.url.name)
            data_bytes = await response.read()
            data_json = json.loads(data_bytes.decode("utf-8"))

        sg_data = pd.DataFrame.from_dict(data_json.pop("data"))
        sg_data["DATETIME"] = pd.to_datetime(sg_data["DATETIME"])
        sg_data.index = sg_data["DATETIME"]
        sg_data.drop(columns=["DATETIME"], inplace=True)
        metadata = data_json

        return sg_data, metadata

    def save_data_and_metadata(self):
        self.dest_folder.mkdir(parents=True, exist_ok=True)
        for name, data in self.datasets.items():
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
                    json.dump(self.metadata[name], f)
                    print(f"Metadata for {name} saved to {metadata_path}")
            except Exception as e:
                print(f"Error while saving metadata for {name}: {e}")


def create_request_dict(
    lat: float,
    long: float,
    site_name: str,
    parameters: list = None,
    from_date: str = "AUTODETECT",
    to_date: str = "LAST_MONTH",  # TODO: what is a reasonable default?
    time_step: str = "PT15M",
    terrain_shading: bool = True,
    site_elevation: float = None,
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

    if site_elevation:
        fts_data_request["site"]["elevation"] = site_elevation

    fts_data_request.update(kwargs)

    return fts_data_request


def to_safe_file_label(label: str) -> str:
    """
    Make sure the file label matches the regex ^[A-Za-z_][A-Za-z0-9_]*$
    """
    safe_label = label.replace(" ", "_")
    safe_label = safe_label.replace("-", "_")
    # Remove any character that is not alphanumeric or underscore
    safe_label = re.sub(r"\W|^(?=\d)", "", safe_label)
    # Ensure the label starts with a letter or underscore
    if not re.match(r"^[A-Za-z_]", safe_label):
        safe_label = "_" + safe_label
    return safe_label


def prettify_file_label(label: str) -> str:
    """
    Remove some SG-specific noise from the file label
    """
    if label.endswith(".json"):
        label = label[:-5]
    if label.endswith("_SOLARGIS_JSON"):
        label = label[:-14]
    return label
