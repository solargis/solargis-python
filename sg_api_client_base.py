import asyncio
import datetime
import json
import pathlib
import re
from abc import abstractmethod

import aiohttp
import pandas as pd


class SGAPIClient:
    def __init__(self, token: str, dest_folder: str | pathlib.Path, url: str):
        """
        token:
        """
        self.url = url
        self.dest_folder = pathlib.Path(dest_folder)
        self.datasets = {}
        self.metadata = {}
        self._requests = {}
        self._file_labels_from_api = {}
        self._headers = {
            "Authorization": f"Bearer {token}",
        }
        self._request_ids_to_names = {}

    def add_request(self, site_name: str, **kwargs):
        kwargs["site_name"] = site_name
        request = self.create_request_dict(**kwargs)
        self._requests[site_name] = request

    async def retrieve_all_data(self, requests=None, save=True):
        """
        Use this method to retrieve all data from the API, wait until all requests are finished
        and use work with the data in pandas dataframes.

        requests: dict of {"name": request}

        save: bool. If True, save the data and metadata to the destination folder.
        """
        async for name, data, metadata in self.retrieve_data(requests, save=save):
            self.datasets[name] = data
            self.metadata[name] = metadata

        # Return the dict of all datasets
        return self.datasets

    async def retrieve_data(self, requests: dict | None = None, save: bool = True):
        """
        Use this method to asynchronously retrieve data from the API. You can start processing
        result of each request as soon as it is finished while the other requests are still running.

        requests: dict of {"name": request}

        yields (name, data, metadata) for each request
        """

        if not requests:
            requests = self._requests
        else:
            self._requests = requests

        async with aiohttp.ClientSession() as session:
            # Step 1: fetch all request IDs in parallel
            tasks = [
                self.fetch_task_ids(session, request, name)
                for name, request in requests.items()
            ]

            wait_tasks = []
            for finished_task in asyncio.as_completed(tasks):
                request_id = await finished_task
                if request_id is not None:
                    wait_tasks.append(request_id)
                else:
                    name = self._request_ids_to_names.get(request_id)
                    yield name, None, None

            wait_tasks = [
                self.wait_for_data(session, request_id)
                for request_id in self._request_ids_to_names.keys()
            ]

            for finished_task in asyncio.as_completed(wait_tasks):
                download_url, status, request_id = await finished_task
                name = self._request_ids_to_names[request_id]
                if status == "success":
                    data, metadata = await self.read_data(session, download_url, name)
                    if save:
                        self.save_data_and_metadata(name, data, metadata)
                    yield name, data, metadata
                else:
                    print(f"Error while retrieving data for {name}, status: {status}")
                    yield name, None, None

    async def fetch_task_ids(self, session, data_request, name: str):
        print(f"Going to send request to Solargis TS API")
        r = json.dumps(data_request)
        async with session.post(self.url, data=r, headers=self._headers) as response:
            response_json = await response.json()

            if "requestId" in response_json:
                request_id = response_json.get("requestId")
                print(f"request_id {request_id} was created")
                self._request_ids_to_names[request_id] = name
                return request_id
            else:
                print(
                    f"Error while sending request to Solargis TS API: {response_json}"
                )
                return None

    async def wait_for_data(self, session, request_id):
        if request_id is None:
            return None, "invalid request_id", None
        status_endpoint = f"{self.url}/{request_id}"
        status = None
        response_status = {}
        while status != "success":
            async with session.get(status_endpoint, headers=self._headers) as response:
                response_status = await response.json()
                if "status" not in response_status:
                    raise ValueError(
                        f"response_status does not include status key {response_status}"
                    )
                status = response_status["status"]
                if status == "error":
                    return None, status, request_id
                print(
                    f'[{datetime.datetime.now()}] Current status of {request_id}: "{status}"'
                )
                await asyncio.sleep(4)

        if status == "success":
            return response_status.get("downloadUrl"), status, request_id
        else:
            print(f"Error while waiting for data for {request_id}, status: {status}")
            return None, status, request_id

    @abstractmethod
    async def read_data(self, session, download_url, name):
        return None, None

    @abstractmethod
    def save_data_and_metadata(self, name, data, metadata):
        """
        Save the data and metadata for one finished request to the destination folder.
        """
        pass

    @staticmethod
    @abstractmethod
    def create_request_dict(**kwargs):
        return {}


def prettify_file_label(label: str) -> str:
    """
    Remove some SG-specific noise from the file label
    """
    if label.endswith(".json"):
        label = label[:-5]
    if label.endswith("_SOLARGIS_JSON"):
        label = label[:-14]
    return label


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
