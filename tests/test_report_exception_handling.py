import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

from lib.core.exceptions import FileExistsException, InvalidRawRequest
from lib.parse.rawrequest import parse_raw
from lib.report.csv_report import CSVReport
from lib.report.sqlite_report import SQLiteReport


class TestReportExceptionHandling(TestCase):
    def test_csv_report_rejects_wrong_header(self):
        with TemporaryDirectory() as directory:
            report = Path(directory, "report.csv")
            report.write_text("Not,Dirsearch\n")

            with self.assertRaisesRegex(ValueError, "CSV header mismatch.*expected.*got"):
                CSVReport().parse(str(report))

    def test_file_report_validation_chains_parse_error(self):
        with TemporaryDirectory() as directory:
            report = Path(directory, "report.csv")
            report.write_text("Not,Dirsearch\n")

            with self.assertRaises(FileExistsException) as context:
                CSVReport().initiate(str(report))

        self.assertIsInstance(context.exception.__cause__, ValueError)

    def test_sqlite_report_rejects_non_sqlite_file(self):
        with TemporaryDirectory() as directory:
            database = Path(directory, "report.sqlite")
            database.write_text("not sqlite")

            with self.assertRaisesRegex(ValueError, "valid SQLite database") as context:
                SQLiteReport().connect(str(database))

        self.assertIsInstance(context.exception.__cause__, sqlite3.DatabaseError)

    def test_sqlite_report_closes_connection_after_validation_failure(self):
        connection = Mock()
        connection.cursor.return_value.execute.side_effect = sqlite3.DatabaseError

        with TemporaryDirectory() as directory:
            database = str(Path(directory, "report.sqlite"))
            with patch(
                "lib.report.sqlite_report.sqlite3.connect", return_value=connection
            ):
                with self.assertRaisesRegex(ValueError, "valid SQLite database"):
                    SQLiteReport().connect(database)

        connection.close.assert_called_once_with()

    def test_raw_request_malformed_input_preserves_invalid_request_type(self):
        with TemporaryDirectory() as directory:
            request = Path(directory, "request.txt")
            request.write_text("\n")

            with self.assertRaises(InvalidRawRequest) as context:
                parse_raw(str(request))

        self.assertIsInstance(context.exception.__cause__, IndexError)
