import asyncio
import json
import pathlib
from typing import Dict, Optional

import aiohttp


async def submit_ts_request(
    session: aiohttp.ClientSession,
    request_dict: Dict,
    api_url: str,
    headers: Dict[str, str],
) -> Optional[str]:
    """
    Submit a TS API request and return the request ID.

    Args:
        session: aiohttp session
        request_dict: The request dictionary to send
        api_url: The API endpoint URL
        headers: HTTP headers including authorization

    Returns:
        request_id if successful, None if failed
    """
    print("Sending request to Solargis TS API...")

    async with session.post(
        api_url, data=json.dumps(request_dict), headers=headers
    ) as response:
        response_json = await response.json()

        if "requestId" in response_json:
            request_id = response_json["requestId"]
            print(f"Request ID {request_id} created successfully")
            return request_id
        else:
            print(f"Error submitting request: {response_json}")
            return None


async def wait_for_download_url(
    session: aiohttp.ClientSession,
    request_id: str,
    api_url: str,
    headers: Dict[str, str],
    poll_interval: int = 4,
) -> Optional[str]:
    """
    Poll the API until data is ready and return download URL.

    Args:
        session: aiohttp session
        request_id: The request ID to check
        api_url: The base API URL
        headers: HTTP headers including authorization
        poll_interval: Seconds to wait between polls

    Returns:
        download_url if successful, None if failed
    """
    status_url = f"{api_url}/{request_id}"

    while True:
        print(f"Checking status for request {request_id}...")

        async with session.get(status_url, headers=headers) as response:
            response_json = await response.json()

            if "status" not in response_json:
                print(f"Invalid response: {response_json}")
                return None

            status = response_json["status"]
            print(f"Status: {status}")

            if status == "success":
                download_url = response_json.get("downloadUrl")
                if download_url:
                    print(f"Data ready! Download URL: {download_url}")
                    return download_url
                else:
                    print("Success status but no download URL found")
                    return None

            elif status == "error":
                print(f"Request failed with error status")
                return None

            # Status is still processing, wait and try again
            await asyncio.sleep(poll_interval)


def save_download_url(
    request_id: str, download_url: str, output_dir: str = "."
) -> None:
    """
    Save the download URL to a text file.

    Args:
        request_id: The request ID
        download_url: The download URL to save
        output_dir: Directory to save the file
    """
    output_path = pathlib.Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    filename = output_path / f"{request_id}.txt"

    with open(filename, "w") as f:
        f.write(download_url)

    print(f"Download URL saved to {filename}")


async def process_ts_request(
    request_dict: Dict,
    token: str,
    api_url: str = "https://api.solargis.com/ts/data-request",
    output_dir: str = "download_urls",
    poll_interval: int = 4,
) -> Optional[str]:
    """
    Complete workflow: submit request, wait for completion, save download URL.

    Args:
        request_dict: The TS API request dictionary
        token: API authentication token
        api_url: The TS API endpoint
        output_dir: Directory to save download URL files
        poll_interval: Seconds between status checks

    Returns:
        download_url if successful, None if failed
    """
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async with aiohttp.ClientSession() as session:
        # Step 1: Submit request
        request_id = await submit_ts_request(session, request_dict, api_url, headers)
        if not request_id:
            return None

        # Step 2: Wait for completion
        download_url = await wait_for_download_url(
            session, request_id, api_url, headers, poll_interval
        )
        if not download_url:
            return None

        # Step 3: Save download URL
        save_download_url(request_id, download_url, output_dir)

        return download_url


async def process_ts_requests(
    request_dicts: list[Dict],
    token: str,
    api_url: str = "https://api.solargis.com/ts/data-request",
    output_dir: str = "download_urls",
    poll_interval: int = 4,
) -> list[Optional[str]]:
    """
    Wrapper to process a list of TS API request dictionaries asynchronously using process_ts_request.
    Returns a list of download URLs (or None for failed requests).
    """
    tasks = [
        asyncio.create_task(
            process_ts_request(
                req,
                token,
                api_url=api_url,
                output_dir=output_dir,
                poll_interval=poll_interval,
            )
        )
        for req in request_dicts
    ]
    return await asyncio.gather(*tasks)
