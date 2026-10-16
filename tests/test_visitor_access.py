"""Failure and retry checks for transferring visitor events out of production."""
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import duckdb

from scripts import visitor_access


def event(number=1, **changes):
    row = dict(zip(visitor_access.ARCHIVE_FIELDS, [
        f"00000000-0000-4000-8000-{number:012d}", "=raw@example.test", 1792022400,
        "page", "allowed", "/favicon.ico", None, None, "pl-PL", "pl-PL", "203.0.113.1",
    ]))
    row.update(changes)
    return dict(row, cursor=number, receipt=visitor_access.archive_receipt(row))


def response(value):
    return BytesIO(json.dumps(value, ensure_ascii=False).encode())


class ArchiveTests(unittest.TestCase):
    def test_unicode_receipt_matches_gateway_protocol(self):
        self.assertEqual(event(path='/Józef/')['receipt'], '280a9f867e5b4268caa078117760e623ebb82cafb3c5ed90bf92095c145809a6')

    def test_incompatible_local_table_stops_before_contacting_server(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'existing.duckdb'
            with duckdb.connect(str(database)) as connection:
                connection.execute('CREATE TABLE visitor_events (id VARCHAR)')
            with patch.object(visitor_access, 'api') as api:
                with self.assertRaisesRegex(ValueError, 'primary key'):
                    visitor_access.export_events(database, 'https://example.test', {})
                api.assert_not_called()

    def test_merge_all_fields_into_existing_database_then_acknowledge(self):
        first, second = event(), event(2, path='/photos/', timezone='Europe/Warsaw')
        routes = []
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'existing.duckdb'
            with duckdb.connect(str(database)) as connection:
                connection.execute('CREATE TABLE unrelated (value INTEGER)')
                connection.execute('INSERT INTO unrelated VALUES (42)')

            def api(url, route, values, method='GET', body=None):
                routes.append(route)
                if route == 'events/archive?after=0':
                    return response(dict(version=1, through=2, next_cursor=1, events=[first]))
                if route == 'events/archive?after=1&through=2':
                    return response(dict(version=1, through=2, next_cursor=2, events=[second]))
                if route == 'events/archive?after=2&through=2':
                    return response(dict(version=1, through=2, next_cursor=2, events=[]))
                self.assertEqual((route, method), ('events/archive/ack', 'POST'))
                # A separate connection can see the committed data before deletion.
                with duckdb.connect(str(database)) as connection:
                    self.assertEqual(connection.execute('SELECT count(*) FROM visitor_events').fetchone()[0], 2)
                    self.assertEqual(connection.execute('SELECT * FROM unrelated').fetchone(), (42,))
                self.assertEqual(len(json.loads(body)['events']), 2)
                return response(dict(deleted=2, missing=0, retained=0))

            with patch.object(visitor_access, 'api', side_effect=api):
                visitor_access.export_events(database, 'https://example.test', {})
                visitor_access.export_events(database, 'https://example.test', {})
            with duckdb.connect(str(database)) as connection:
                self.assertEqual(connection.execute('SELECT count(*) FROM visitor_events').fetchone(), (2,))
                self.assertEqual(connection.execute('SELECT email,path,timezone FROM visitor_events ORDER BY id').fetchall(),
                                 [('=raw@example.test', '/favicon.ico', None), ('=raw@example.test', '/photos/', 'Europe/Warsaw')])
            self.assertEqual(database.stat().st_mode & 0o777, 0o600)
        self.assertEqual(routes.count('events/archive/ack'), 2)

    def test_download_failure_rolls_back_and_never_deletes(self):
        calls = []
        def api(url, route, values, *args):
            calls.append(route)
            if len(calls) == 1:
                return response(dict(version=1, through=2, next_cursor=1, events=[event()]))
            raise OSError('Download interrupted')
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'visits.duckdb'
            with patch.object(visitor_access, 'api', side_effect=api), self.assertRaises(OSError):
                visitor_access.export_events(database, 'https://example.test', {})
            with duckdb.connect(str(database)) as connection:
                self.assertEqual(connection.execute("SELECT count(*) FROM information_schema.tables WHERE table_name='visitor_events'").fetchone(), (0,))
        self.assertTrue(all('ack' not in route for route in calls))

    def test_failed_ack_can_be_retried_and_changed_context_is_refreshed(self):
        current = event()
        fail_ack = True
        def api(url, route, values, *args):
            if route == 'events/archive?after=0':
                return response(dict(version=1, through=1, next_cursor=1, events=[current]))
            if route == 'events/archive?after=1&through=1':
                return response(dict(version=1, through=1, next_cursor=1, events=[]))
            if fail_ack:
                raise OSError('Acknowledgement lost')
            return response(dict(deleted=1, missing=0, retained=0))
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'visits.duckdb'
            with patch.object(visitor_access, 'api', side_effect=api):
                with self.assertRaisesRegex(ValueError, 'Local archive is saved'):
                    visitor_access.export_events(database, 'https://example.test', {})
                with duckdb.connect(str(database)) as connection:
                    self.assertEqual(connection.execute('SELECT count(*) FROM visitor_events').fetchone(), (1,))
                current = event(timezone='Europe/Warsaw', language='pl-PL', path='/Józef/')
                fail_ack = False
                visitor_access.export_events(database, 'https://example.test', {})
            with duckdb.connect(str(database)) as connection:
                self.assertEqual(connection.execute('SELECT count(*),max(timezone),max(path) FROM visitor_events').fetchone(), (1, 'Europe/Warsaw', '/Józef/'))

    def test_bad_checksum_or_schema_never_acknowledges(self):
        bad = event()
        bad['path'] = '/tampered/'
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'visits.duckdb'
            with patch.object(visitor_access, 'api', return_value=response(dict(version=1, through=1, next_cursor=1, events=[bad]))) as api:
                with self.assertRaisesRegex(ValueError, 'checksum'):
                    visitor_access.export_events(database, 'https://example.test', {})
                self.assertEqual(api.call_count, 1)

    def test_empty_snapshot_makes_no_delete_request(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'visits.duckdb'
            with patch.object(visitor_access, 'api', return_value=response(dict(version=1, through=0, next_cursor=0, events=[]))) as api:
                visitor_access.export_events(database, 'https://example.test', {})
                self.assertEqual(api.call_count, 1)
            with duckdb.connect(str(database)) as connection:
                self.assertEqual(connection.execute('SELECT count(*) FROM visitor_events').fetchone(), (0,))

    def test_partial_delete_failure_retries_remaining_rows_without_duplicate_inserts(self):
        remote = {row['id']: row for row in (event(number) for number in range(1, 62))}
        fail_second_ack = True
        ack_sizes = []
        def api(url, route, values, method='GET', body=None):
            if route.startswith('events/archive?after=0'):
                return response(dict(version=1, through=61, next_cursor=61, events=list(remote.values())))
            if route.startswith('events/archive?after=61'):
                return response(dict(version=1, through=61, next_cursor=61, events=[]))
            batch = json.loads(body)['events']
            ack_sizes.append(len(batch))
            if fail_second_ack and len(ack_sizes) == 2:
                raise OSError('Network failed during deletion')
            for item in batch:
                remote.pop(item['id'])
            return response(dict(deleted=len(batch), missing=0, retained=0))
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'visits.duckdb'
            with patch.object(visitor_access, 'api', side_effect=api):
                with self.assertRaisesRegex(ValueError, 'Local archive is saved'):
                    visitor_access.export_events(database, 'https://example.test', {})
                self.assertEqual(len(remote), 11)
                fail_second_ack = False
                visitor_access.export_events(database, 'https://example.test', {})
            with duckdb.connect(str(database)) as connection:
                self.assertEqual(connection.execute('SELECT count(*) FROM visitor_events').fetchone(), (61,))
            self.assertEqual(remote, {})
            self.assertEqual(ack_sizes, [50, 11, 11])

    def test_flush_failure_preserves_online_records(self):
        def api(url, route, values, *args):
            if route.endswith('after=0'):
                return response(dict(version=1, through=1, next_cursor=1, events=[event()]))
            return response(dict(version=1, through=1, next_cursor=1, events=[]))
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(visitor_access, 'api', side_effect=api) as mock_api:
                with patch.object(visitor_access.os, 'fsync', side_effect=OSError('Disk flush failed')):
                    with self.assertRaisesRegex(OSError, 'Disk flush failed'):
                        visitor_access.export_events(Path(directory) / 'visits.duckdb', 'https://example.test', {})
                self.assertTrue(all('ack' not in call.args[1] for call in mock_api.call_args_list))
