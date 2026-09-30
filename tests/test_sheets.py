import unittest

from moon.sheets import GoogleSheetsPeriodStore, SheetsError


class FakeRequest:
    def __init__(self, value=None, error=None):
        self.value = value
        self.error = error

    def execute(self):
        if self.error:
            raise self.error
        return self.value or {}


class FakeValues:
    def __init__(self, rows=None, headers=None):
        self.rows = rows or []
        self.headers = headers
        self.appended = []
        self.updated = []

    def get(self, spreadsheetId, range):
        if range.endswith("A1:E1"):
            return FakeRequest({"values": [self.headers] if self.headers is not None else []})
        return FakeRequest({"values": self.rows})

    def update(self, **kwargs):
        self.updated.append(kwargs)
        return FakeRequest()

    def append(self, **kwargs):
        self.appended.append(kwargs)
        return FakeRequest()


class FakeSpreadsheets:
    def __init__(self, values, worksheet_exists=True, error=None):
        self.values_resource = values
        self.worksheet_exists = worksheet_exists
        self.error = error
        self.added = []

    def get(self, **kwargs):
        if self.error:
            return FakeRequest(error=self.error)
        sheets = [{"properties": {"sheetId": 7, "title": "Period Records"}}] if self.worksheet_exists else []
        return FakeRequest({"sheets": sheets})

    def batchUpdate(self, **kwargs):
        self.added.append(kwargs)
        return FakeRequest({"replies": [{"addSheet": {"properties": {"sheetId": 8}}}]})

    def values(self):
        return self.values_resource


class FakeService:
    def __init__(self, values, worksheet_exists=True, error=None):
        self.spreadsheets_resource = FakeSpreadsheets(values, worksheet_exists, error)

    def spreadsheets(self):
        return self.spreadsheets_resource


def make_store(rows=None, headers=None, worksheet_exists=True, error=None):
    values = FakeValues(rows=rows, headers=headers)
    service = FakeService(values, worksheet_exists=worksheet_exists, error=error)
    return GoogleSheetsPeriodStore("unused.json", "spreadsheet", "Period Records", service=service), values, service


class SheetsStoreTests(unittest.TestCase):
    def test_successful_save_creates_headers_and_appends(self):
        store, values, service = make_store(worksheet_exists=False)

        result = store.save({"date": "2026-09-27", "time": "08:30", "note": "Started", "feedback": "Mild"})

        self.assertEqual(result, "saved")
        self.assertEqual(len(service.spreadsheets_resource.added), 1)
        self.assertEqual(values.appended[0]["body"]["values"][0][:4], ["2026-09-27", "08:30", "Started", "Mild"])
        self.assertEqual(values.updated[0]["body"]["values"], [["Date", "Time", "Note", "Feedback", "Recorded At"]])

    def test_duplicate_date_and_time_updates_existing_row(self):
        store, values, _ = make_store(rows=[["2026-09-27", "08:30", "Old", "Old feedback", "old"]])

        result = store.save({"date": "2026-09-27", "time": "08:30", "note": "New", "feedback": "Better"})

        self.assertEqual(result, "updated")
        self.assertEqual(values.appended, [])
        self.assertEqual(values.updated[-1]["range"], "'Period Records'!A2:E2")
        self.assertEqual(values.updated[-1]["body"]["values"][0][2:4], ["New", "Better"])

    def test_report_filters_by_date(self):
        store, _, _ = make_store(rows=[
            ["2026-09-27", "08:30", "Match", "", "recorded"],
            ["2026-09-28", "09:00", "Other", "", "recorded"],
        ])

        report = store.report("2026-09-27")

        self.assertEqual(len(report), 1)
        self.assertEqual(report[0]["note"], "Match")

    def test_api_errors_are_clear_and_not_reported_as_saved(self):
        store, _, _ = make_store(error=RuntimeError("permission denied"))

        with self.assertRaisesRegex(SheetsError, "Google Sheets API error: permission denied"):
            store.save({"date": "2026-09-27", "time": "08:30"})


if __name__ == "__main__":
    unittest.main()