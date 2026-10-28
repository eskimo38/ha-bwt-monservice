"""Async API client for BWT Mon Service cloud."""
import logging
import json
import re
import html as html_lib
from datetime import datetime

import aiohttp
from bs4 import BeautifulSoup

from homeassistant.util import dt as dt_util

from .const import (
    BWT_BASE_URL,
    BWT_LOGIN_URL,
    BWT_DASHBOARD_URL,
    BWT_SUMMARY_URL,
    BWT_LOAD_CONSO_URL,
)

_LOGGER = logging.getLogger(__name__)

CONNECT_TIMEOUT = aiohttp.ClientTimeout(connect=10, total=30)


class BwtApiError(Exception):
    """Base exception for BWT API errors."""


class BwtAuthError(BwtApiError):
    """Authentication failed."""


class BwtConnectionError(BwtApiError):
    """Connection to BWT service failed."""


class BwtCloudApi:
    """Async client for the BWT Mon Service cloud API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
        serial_number: str,
    ) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._serial_number = serial_number
        self._authenticated = False

    async def authenticate(self) -> str:
        """Login and return the receipt_line_key for the configured device.

        Raises BwtAuthError on bad credentials, BwtConnectionError on network issues.
        """
        try:
            resp = await self._session.post(
                BWT_LOGIN_URL,
                data={"_username": self._username, "_password": self._password},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=CONNECT_TIMEOUT,
            )
        except (aiohttp.ClientError, TimeoutError) as err:
            raise BwtConnectionError(f"Cannot connect to BWT service: {err}") from err

        if resp.status in (401, 403):
            raise BwtAuthError("Authentication failed: invalid credentials")
        if resp.status != 200:
            raise BwtApiError(f"Unexpected status {resp.status} during login")

        self._authenticated = True
        _LOGGER.info("BWT authentication successful")

        # Fetch dashboard to find receipt_line_key for our serial number
        try:
            resp = await self._session.get(
                BWT_DASHBOARD_URL, timeout=CONNECT_TIMEOUT
            )
        except (aiohttp.ClientError, TimeoutError) as err:
            raise BwtConnectionError(f"Cannot fetch dashboard: {err}") from err

        text = await resp.text()
        soup = BeautifulSoup(text, "html.parser")

        links = soup.find_all("a", href=re.compile(r"/device\?receiptLineKey="))
        for link in links:
            info_div = link.find("div", class_="informations")
            if info_div:
                serial_span = info_div.find(
                    "span", string=re.compile(self._serial_number)
                )
                if serial_span:
                    href = link.get("href")
                    match = re.search(r"receiptLineKey=([^&]+)", href)
                    if match:
                        key = match.group(1)
                        _LOGGER.info("Receipt line key found: %s", key)
                        return key

        raise BwtApiError(
            f"Serial number {self._serial_number} not found in dashboard"
        )

    async def get_main_data(self, receipt_line_key: str) -> dict:
        """Fetch main device data from the product-summary endpoint."""
        url = f"{BWT_SUMMARY_URL}/{receipt_line_key}"

        try:
            resp = await self._session.get(url, timeout=CONNECT_TIMEOUT)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise BwtConnectionError(f"Cannot fetch main data: {err}") from err

        if resp.status in (401, 403):
            self._authenticated = False
            raise BwtAuthError("Session expired")
        if resp.status != 200:
            raise BwtApiError(f"Main data request failed with status {resp.status}")

        data = await resp.json()

        result = {
            "online": data.get("online", False),
            "standby": data.get("data", {}).get("standBy", False),
            "salt": data.get("data", {}).get("salt"),
        }

        code_mapping = {
            "resinVol": "resin_vol",
            "inHardness": "in_hardness",
            "outHardness": "out_hardness",
            "pressure": "pressure",
            "salt": "salt",
            "volOK": "vol_ok",
            "rssiLevel": "wifi_signal",
            "cpuSoftVer": "firmware_cpu",
            "iotSoftVer": "firmware_iot",
            "saltType": "salt_type",
            "reservVol": "reserve_volume",
            "regenHour": "regen_hour",
            "regenMin": "regen_min",
        }

        categories = data.get("dataCategories", {})
        for _category_name, category_data in categories.items():
            if isinstance(category_data, list):
                for item in category_data:
                    code = item.get("code")
                    value = item.get("value")
                    if code and value is not None and code in code_mapping:
                        result[code_mapping[code]] = value
                        _LOGGER.debug(
                            "Mapped '%s' -> '%s': %s", code, code_mapping[code], value
                        )

        # Combine start hour/minute into a single HH:MM value
        regen_hour = result.pop("regen_hour", None)
        regen_min = result.pop("regen_min", None)
        if regen_hour is not None and regen_min is not None:
            try:
                result["regen_time"] = f"{int(regen_hour):02d}:{int(regen_min):02d}"
            except (TypeError, ValueError):
                pass

        _LOGGER.debug("Main data retrieved: %s", result)
        return result

    async def get_consumption_data(self, receipt_line_key: str) -> dict:
        """Fetch consumption data by scraping the device page and calling loadConso."""
        device_url = f"{BWT_BASE_URL}/device?receiptLineKey={receipt_line_key}"

        try:
            resp = await self._session.get(device_url, timeout=CONNECT_TIMEOUT)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise BwtConnectionError(
                f"Cannot fetch device page: {err}"
            ) from err

        if resp.status in (401, 403):
            self._authenticated = False
            raise BwtAuthError("Session expired")
        if resp.status != 200:
            raise BwtApiError(
                f"Device page returned status {resp.status}"
            )

        page_bytes = await resp.read()
        soup = BeautifulSoup(page_bytes, "html.parser")
        live_div = soup.find("div", {"data-controller": "live"})

        if not live_div:
            _LOGGER.warning(
                "Live div not found on device page (length=%d, url=%s)",
                len(page_bytes),
                str(resp.url),
            )
            raise BwtApiError("Live div not found on device page")

        props_value = live_div.get("data-live-props-value", "")
        props_decoded = html_lib.unescape(props_value)

        try:
            props = json.loads(props_decoded)
        except ValueError as err:
            raise BwtApiError(f"Cannot parse device page props: {err}") from err

        payload_data = {
            "props": props,
            "updated": {},
            "args": {},
        }

        try:
            resp = await self._session.post(
                BWT_LOAD_CONSO_URL,
                data={"data": json.dumps(payload_data)},
                headers={
                    "Accept": "application/vnd.live-component+html",
                    "Content-Type": "application/x-www-form-urlencoded",
                    # BWT now answers 404 to live-component POSTs without this
                    "X-Requested-With": "XMLHttpRequest",
                },
                allow_redirects=True,
                timeout=CONNECT_TIMEOUT,
            )
        except (aiohttp.ClientError, TimeoutError) as err:
            raise BwtConnectionError(f"Cannot fetch consumption data: {err}") from err

        if resp.status in (401, 403):
            self._authenticated = False
            raise BwtAuthError("Session expired")
        if resp.status != 200:
            raise BwtApiError(
                f"loadConso returned status {resp.status}"
            )

        conso_bytes = await resp.read()
        soup = BeautifulSoup(conso_bytes, "html.parser")
        graph_div = soup.find("div", id="graph_device")

        if not graph_div:
            # Usually an expired session (login page served with HTTP 200) or
            # a changed page layout. Raise so the entities are flagged
            # unavailable instead of silently keeping stale values.
            raise BwtApiError(
                "graph_device div not found in loadConso response "
                f"(length={len(conso_bytes)}, snippet={conso_bytes[:200]!r})"
            )

        dataset = graph_div.get("data-chart-dataset-value", "{}")
        salt_value = graph_div.get("data-chart-salt-value", "0")

        try:
            dataset_json = json.loads(html_lib.unescape(dataset))
            result: dict = {"salt_per_regen": int(salt_value)}
        except (ValueError, TypeError) as err:
            raise BwtApiError(f"Cannot parse consumption data: {err}") from err

        # Parse first line of data (most recent)
        lines = dataset_json.get("lines", [])
        _LOGGER.debug("Consumption dataset keys: %s, lines count: %d",
                       list(dataset_json.keys()), len(lines))
        if lines:
            first_line = lines[0]
            if len(first_line) >= 5:
                result["last_date"] = first_line[0]
                result["regen_count"] = int(first_line[1]) if first_line[1] else 0
                result["power_outage"] = (
                    first_line[2] if isinstance(first_line[2], bool) else False
                )
                result["water_consumption"] = (
                    int(first_line[3]) if first_line[3] else 0
                )
                result["salt_alarm"] = (
                    first_line[4] if isinstance(first_line[4], bool) else False
                )
                result["salt_consumption"] = (
                    result["regen_count"] * result["salt_per_regen"]
                )

                try:
                    naive_dt = datetime.strptime(result["last_date"], "%Y-%m-%d")
                    result["last_update"] = dt_util.as_utc(naive_dt)
                except (ValueError, TypeError) as exc:
                    _LOGGER.warning(
                        "Failed to parse last_date '%s': %s",
                        result.get("last_date"),
                        exc,
                    )
                    result["last_update"] = None

        _LOGGER.debug("Consumption data retrieved: %s", result)
        return result

    @property
    def authenticated(self) -> bool:
        return self._authenticated

