import os
from typing import Any

import requests

from app.core.config import get_settings


class ConveraError(Exception):
    pass


class ConveraAuthenticationError(ConveraError):
    pass


class ConveraPermissionError(ConveraError):
    pass


class ConveraUnavailableError(ConveraError):
    pass


class ConveraClient:

    def __init__(self):
        # Read via the app's Settings/.env loader, not raw
        # os.getenv() — pydantic-settings loads .env values into the
        # Settings model, it doesn't mutate the real process
        # environment, so os.getenv() alone would never see them.
        settings = get_settings()

        self.base_url = (
            settings.convera_api_url or "http://localhost:8000"
        ).rstrip("/")

        self.api_key = settings.convera_api_key

        self.timeout = settings.convera_timeout_seconds

        if not self.api_key:
            raise RuntimeError(
                "CONVERA_API_KEY is not configured."
            )

    @property
    def headers(self):
        return {
            "Authorization":
                f"Bearer {self.api_key}"
        }

    def health(self) -> dict[str, Any]:

        try:
            response = requests.get(
                f"{self.base_url}/health",
                timeout=10,
            )

            response.raise_for_status()

            return response.json()

        except requests.RequestException as exc:
            raise ConveraUnavailableError(
                f"Unable to reach Convera: {exc}"
            ) from exc

    def extract_document(
        self,
        file_path: str,
    ) -> dict[str, Any]:

        try:
            with open(file_path, "rb") as file_handle:

                response = requests.post(
                    (
                        f"{self.base_url}"
                        "/v1/documents/extract"
                    ),

                    headers=self.headers,

                    files={
                        "file": (
                            os.path.basename(file_path),
                            file_handle,
                            "application/pdf",
                        )
                    },

                    timeout=self.timeout,
                )

        except requests.RequestException as exc:
            raise ConveraUnavailableError(
                str(exc)
            ) from exc

        if response.status_code == 401:
            raise ConveraAuthenticationError(
                "Convera rejected the API key."
            )

        if response.status_code == 403:
            raise ConveraPermissionError(
                response.text
            )

        if response.status_code >= 500:
            raise ConveraUnavailableError(
                response.text
            )

        if not response.ok:
            raise ConveraError(
                f"Convera returned "
                f"{response.status_code}: "
                f"{response.text}"
            )

        return response.json()