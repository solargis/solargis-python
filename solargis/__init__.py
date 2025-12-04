"""Solargis Python API Client

A simple Python client for communication with Solargis API.
Supports time-series (TS) and typical meteorological year (TMY) data.
"""

__version__ = "0.1.0"

from .ts_api_client_simple import (
    submit_ts_request,
    wait_for_download_url,
    save_download_url,
    process_ts_request,
    process_ts_requests,
)

__all__ = [
    "submit_ts_request",
    "wait_for_download_url",
    "save_download_url",
    "process_ts_request",
    "process_ts_requests",
]
