import asyncio
import json
import logging
import pathlib
from typing import Dict, Optional

import aiohttp

# Configure logging
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


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
    logger.info("Sending request to Solargis TS API...")
    logger.debug(f"API URL: {api_url}")
    logger.debug(f"Request payload: {json.dumps(request_dict, indent=2)}")

    try:
        async with session.post(
            api_url, data=json.dumps(request_dict), headers=headers
        ) as response:
            logger.debug(f"Response status code: {response.status}")
            response_json = await response.json()
            logger.debug(f"Response JSON: {response_json}")

            if "requestId" in response_json:
                request_id = response_json["requestId"]
                logger.info(f"Request ID {request_id} created successfully")
                return request_id
            else:
                logger.error(f"Error submitting request: {response_json}")
                return None
    except Exception as e:
        logger.exception(f"Exception occurred while submitting request: {e}")
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
    logger.info(f"Starting to poll for download URL (request_id={request_id})")
    logger.debug(f"Status URL: {status_url}")
    poll_count = 0

    try:
        while True:
            poll_count += 1
            logger.debug(f"Poll attempt #{poll_count} for request {request_id}...")

            async with session.get(status_url, headers=headers) as response:
                logger.debug(f"Poll response status code: {response.status}")
                response_json = await response.json()
                logger.debug(f"Poll response JSON: {response_json}")

                if "status" not in response_json:
                    logger.error(
                        f"Invalid response (missing 'status' field): {response_json}"
                    )
                    return None

                status = response_json["status"]
                logger.info(f"Request {request_id} status: {status}")

                if status == "success":
                    download_url = response_json.get("downloadUrl")
                    if download_url:
                        logger.info(
                            f"Data ready! Download URL obtained for request {request_id}"
                        )
                        logger.debug(f"Download URL: {download_url}")
                        return download_url
                    else:
                        logger.error(
                            "Success status but no download URL found in response"
                        )
                        return None

                elif status == "error":
                    logger.error(f"Request {request_id} failed with error status")
                    error_msg = response_json.get("error", "No error message provided")
                    logger.debug(f"Error details: {error_msg}")
                    return None

                # Status is still processing, wait and try again
                logger.debug(
                    f"Request {request_id} still processing. Waiting {poll_interval}s before next poll..."
                )
                await asyncio.sleep(poll_interval)
    except Exception as e:
        logger.exception(f"Exception occurred while waiting for download URL: {e}")
        return None


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
    try:
        output_path = pathlib.Path(output_dir)
        logger.debug(f"Creating output directory: {output_path.absolute()}")
        output_path.mkdir(parents=True, exist_ok=True)

        filename = output_path / f"{request_id}.txt"
        logger.info(f"Saving download URL to file: {filename.absolute()}")

        with open(filename, "w") as f:
            f.write(download_url)

        logger.info(f"Download URL successfully saved to {filename.absolute()}")
    except Exception as e:
        logger.exception(f"Exception occurred while saving download URL: {e}")


async def process_ts_request(
    request_dict: Dict,
    token: str,
    api_url: str = "https://api.solargis.com/ts/data-request",
    output_dir: str = "download_urls",
    poll_interval: int = 4,
    inject_request_id: bool = False,
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
    logger.info("Starting TS API request workflow")
    logger.debug(f"Output directory: {output_dir}, Poll interval: {poll_interval}s")

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    try:
        async with aiohttp.ClientSession() as session:
            # Step 1: Submit request
            logger.info("Step 1: Submitting TS API request")
            request_id = await submit_ts_request(
                session, request_dict, api_url, headers
            )
            if not request_id:
                logger.error("Failed to obtain request ID - workflow aborted")
                return None

            if inject_request_id:
                request_dict["requestId"] = request_id
                logger.debug(
                    f"Injected request ID {request_id} into request dictionary"
                )
            # Step 2: Wait for completion
            logger.info(f"Step 2: Waiting for request {request_id} to complete")
            download_url = await wait_for_download_url(
                session, request_id, api_url, headers, poll_interval
            )
            if not download_url:
                logger.error(
                    f"Failed to obtain download URL for request {request_id} - workflow aborted"
                )
                return None

            # Step 3: Save download URL
            logger.info(f"Step 3: Saving download URL for request {request_id}")
            save_download_url(request_id, download_url, output_dir)

            logger.info(
                f"TS API request workflow completed successfully for request {request_id}"
            )
            return download_url
    except Exception as e:
        logger.exception(f"Exception occurred during TS API request workflow: {e}")
        return None


async def process_ts_requests(
    request_dicts: list[Dict],
    token: str,
    api_url: str = "https://api.solargis.com/ts/data-request",
    output_dir: str = "download_urls",
    poll_interval: int = 4,
    inject_request_id: bool = False,
) -> list[Optional[str]]:
    """
    Wrapper to process a list of TS API request dictionaries asynchronously using process_ts_request.
    Returns a list of download URLs (or None for failed requests).
    """
    logger.info(f"Starting batch processing of {len(request_dicts)} TS API requests")
    logger.debug(
        f"Processing parameters - API URL: {api_url}, Output dir: {output_dir}, Poll interval: {poll_interval}s"
    )

    try:
        tasks = [
            asyncio.create_task(
                process_ts_request(
                    req,
                    token,
                    api_url=api_url,
                    output_dir=output_dir,
                    poll_interval=poll_interval,
                    inject_request_id=inject_request_id,
                )
            )
            for req in request_dicts
        ]
        logger.debug(f"Created {len(tasks)} async tasks for processing")

        results = await asyncio.gather(*tasks)

        successful = sum(1 for r in results if r is not None)
        failed = len(results) - successful
        logger.info(
            f"Batch processing completed: {successful} successful, {failed} failed out of {len(results)} total"
        )

        return results
    except Exception as e:
        logger.exception(f"Exception occurred during batch request processing: {e}")
        return [None] * len(request_dicts)
