"""Read-only access to a Google Sheets worksheet."""
import csv
import io
from typing import List, Optional
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from ..config import Settings


class GoogleSheetsError(RuntimeError):
    pass


class GoogleSheetsClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def fetch_values(self, tab: Optional[str] = None) -> List[List[str]]:
        settings = self.settings
        if settings.google_sheets_credentials_file:
            # Import only for authenticated sheets; public sheets need no credentials.
            from google.auth.transport.requests import AuthorizedSession
            from google.oauth2.service_account import Credentials

            credentials = Credentials.from_service_account_file(
                str(settings.google_sheets_credentials_file),
                scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
            )
            sheet_range = "'" + (tab or settings.google_sheets_tab).replace("'", "''") + "'!A:AZ"
            url = (
                "https://sheets.googleapis.com/v4/spreadsheets/"
                + quote(settings.google_sheets_id, safe="")
                + "/values/" + quote(sheet_range, safe="")
            )
            with AuthorizedSession(credentials, refresh_timeout=30) as session:
                response = session.get(
                    url, params={"valueRenderOption": "FORMATTED_VALUE"}, timeout=30
                )
                if response.status_code != 200:
                    raise GoogleSheetsError(
                        f"Google Sheets API returned HTTP {response.status_code}. "
                        "Check the sheet ID, tab name, API activation, and service-account access."
                    )
                return response.json().get("values", [])

        # Public read access; restrict the export to the configured worksheet gid.
        url = (
            "https://docs.google.com/spreadsheets/d/"
            + quote(settings.google_sheets_id, safe="")
            + "/export?" + urlencode({"format": "csv", "gid": settings.google_sheets_gid})
        )
        if tab is not None:
            url = ("https://docs.google.com/spreadsheets/d/" + quote(settings.google_sheets_id, safe="")
                   + "/gviz/tq?" + urlencode({"tqx": "out:csv", "sheet": tab, "headers": "1"}))
        try:
            request = Request(url, headers={"User-Agent": "CMCB-Market-Insights/1.0"})
            with urlopen(request, timeout=15 if tab is not None else 60) as response:
                payload = response.read().decode("utf-8-sig")
                content_type = response.headers.get("Content-Type", "")
        except Exception as error:
            # Avoid logging response bodies, credentials, or sheet contents.
            raise GoogleSheetsError(
                "Could not read Google Sheets CSV. For a private sheet, configure "
                "GOOGLE_SHEETS_CREDENTIALS_FILE and share the sheet with that service account."
            ) from error
        if "text/html" in content_type or payload.lstrip().lower().startswith(
            ("<!doctype", "<html", "<head", "<script")
        ):
            raise GoogleSheetsError(
                "Google returned a sign-in page instead of CSV. Configure service-account access."
            )
        csv.field_size_limit(10_000_000)
        try:
            return list(csv.reader(io.StringIO(payload)))
        except csv.Error as error:
            raise GoogleSheetsError("Google Sheets returned an invalid CSV export.") from error
