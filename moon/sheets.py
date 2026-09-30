from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path


HEADERS = ("Date", "Time", "Note", "Feedback", "Recorded At")


class SheetsError(RuntimeError):
    """A user-facing Google Sheets configuration or API error."""


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def get_period_store() -> "GoogleSheetsPeriodStore | None":
    _load_dotenv()
    credentials = os.environ.get("GOOGLE_SHEETS_CREDENTIALS", "").strip()
    spreadsheet_id = os.environ.get("MOON_PERIOD_SPREADSHEET_ID", "").strip()
    worksheet = os.environ.get("MOON_PERIOD_WORKSHEET", "").strip()
    configured = (credentials, spreadsheet_id, worksheet)
    if not any(configured):
        return None
    if not all(configured):
        raise SheetsError(
            "Google Sheets configuration is incomplete. Set "
            "GOOGLE_SHEETS_CREDENTIALS, MOON_PERIOD_SPREADSHEET_ID, and "
            "MOON_PERIOD_WORKSHEET, or remove all three to use local JSON."
        )
    return GoogleSheetsPeriodStore(credentials, spreadsheet_id, worksheet)


class GoogleSheetsPeriodStore:
    def __init__(self, credentials_path: str, spreadsheet_id: str, worksheet: str, service=None):
        self.spreadsheet_id = spreadsheet_id
        self.worksheet = worksheet
        self.service = service or self._build_service(credentials_path)
        self._worksheet_id = None

    @staticmethod
    def _build_service(credentials_path: str):
        path = Path(credentials_path).expanduser()
        if not path.is_file():
            raise SheetsError(f"Google credentials file was not found: {path}")
        try:
            from google.oauth2.service_account import Credentials
            from googleapiclient.discovery import build

            credentials = Credentials.from_service_account_file(
                str(path), scopes=["https://www.googleapis.com/auth/spreadsheets"]
            )
            return build("sheets", "v4", credentials=credentials, cache_discovery=False)
        except SheetsError:
            raise
        except ImportError as exc:
            raise SheetsError(
                "Google Sheets support is not installed. Install the 'sheets' extra."
            ) from exc
        except Exception as exc:
            raise SheetsError(f"Could not load Google Sheets credentials: {exc}") from exc

    def _api(self, operation):
        try:
            return operation()
        except SheetsError:
            raise
        except Exception as exc:
            raise SheetsError(f"Google Sheets API error: {exc}") from exc

    def _range(self, suffix: str) -> str:
        escaped = self.worksheet.replace("'", "''")
        return f"'{escaped}'!{suffix}"

    def _ensure_worksheet(self) -> None:
        metadata = self._api(
            lambda: self.service.spreadsheets()
            .get(spreadsheetId=self.spreadsheet_id, fields="sheets(properties(sheetId,title))")
            .execute()
        )
        sheets = metadata.get("sheets", [])
        for sheet in sheets:
            properties = sheet.get("properties", {})
            if properties.get("title") == self.worksheet:
                self._worksheet_id = properties.get("sheetId")
                break
        if self._worksheet_id is None:
            response = self._api(
                lambda: self.service.spreadsheets()
                .batchUpdate(
                    spreadsheetId=self.spreadsheet_id,
                    body={"requests": [{"addSheet": {"properties": {"title": self.worksheet}}}]},
                )
                .execute()
            )
            replies = response.get("replies", [])
            if not replies:
                raise SheetsError("Google Sheets did not create the requested worksheet.")
            self._worksheet_id = replies[0].get("addSheet", {}).get("properties", {}).get("sheetId")

        header_response = self._api(
            lambda: self.service.spreadsheets()
            .values()
            .get(spreadsheetId=self.spreadsheet_id, range=self._range("A1:E1"))
            .execute()
        )
        headers = (header_response.get("values") or [[]])[0]
        if headers != list(HEADERS):
            self._api(
                lambda: self.service.spreadsheets()
                .values()
                .update(
                    spreadsheetId=self.spreadsheet_id,
                    range=self._range("A1:E1"),
                    valueInputOption="RAW",
                    body={"values": [list(HEADERS)]},
                )
                .execute()
            )

    def _rows(self):
        response = self._api(
            lambda: self.service.spreadsheets()
            .values()
            .get(spreadsheetId=self.spreadsheet_id, range=self._range("A2:E"))
            .execute()
        )
        return response.get("values", [])

    def save(self, entry: dict) -> str:
        self._ensure_worksheet()
        row = [
            entry["date"],
            entry["time"],
            entry.get("note", ""),
            entry.get("feedback", ""),
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
        ]
        existing_rows = self._rows()
        matching_row = next(
            (index for index, values in enumerate(existing_rows, start=2)
             if len(values) >= 2 and values[0] == entry["date"] and values[1] == entry["time"]),
            None,
        )
        if matching_row is None:
            self._api(
                lambda: self.service.spreadsheets()
                .values()
                .append(
                    spreadsheetId=self.spreadsheet_id,
                    range=self._range("A:E"),
                    valueInputOption="RAW",
                    insertDataOption="INSERT_ROWS",
                    body={"values": [row]},
                )
                .execute()
            )
            return "saved"
        self._api(
            lambda: self.service.spreadsheets()
            .values()
            .update(
                spreadsheetId=self.spreadsheet_id,
                range=self._range(f"A{matching_row}:E{matching_row}"),
                valueInputOption="RAW",
                body={"values": [row]},
            )
            .execute()
        )
        return "updated"

    def report(self, entry_date: str) -> list[dict]:
        self._ensure_worksheet()
        entries = []
        for values in self._rows():
            values = list(values) + [""] * (len(HEADERS) - len(values))
            if values[0] == entry_date:
                entries.append(dict(zip(("date", "time", "note", "feedback", "recorded_at"), values)))
        return entries