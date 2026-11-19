"""Regression coverage for the standalone stream graph's registry payload."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import build_surname_stream
from scripts.build_generation_overview import build_data


class SurnameStreamTests(unittest.TestCase):
    def test_output_preserves_overview_assignments_and_safely_embeds_names(self):
        data = build_data()
        data['people'][0]['first'] = 'Łucja </script><script>alert("x")</script>'
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'nested/stream.html'
            with patch.object(build_surname_stream, 'build_data', return_value=data), \
                 patch('sys.argv', ['build_surname_stream', '--output', str(output)]):
                build_surname_stream.main()
            html = output.read_text(encoding='utf-8')
        embedded = html.split('<script id="stream-data" type="application/json">', 1)[1].split('</script>', 1)[0]
        self.assertNotIn('<', embedded)
        self.assertEqual(json.loads(embedded), data)
        self.assertNotIn('__STREAM_DATA__', html)


if __name__ == '__main__':
    unittest.main()
