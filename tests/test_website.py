"""Regressions for photo link stability and publication integrity."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import build_website, website


class WebsiteTests(unittest.TestCase):
    def test_photo_links_do_not_depend_on_gallery_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            photos = root / 'photos'
            photos.mkdir()
            (photos / '1930 - Census as Puirch.jpg').write_bytes(b'image')
            config = {'collections': {'america': {'directory': 'photos'}}}
            with patch.object(build_website, 'ROOT', root), patch.object(build_website, 'CONFIG', config):
                before = build_website.america_link_map()
                (photos / '1900 - Earlier photo.jpg').write_bytes(b'image')
                after = build_website.america_link_map()
            self.assertTrue(before.items() <= after.items())

    def test_slug_distinguishes_same_stem_and_transliterations(self):
        names = ['Zofia.jpg', 'Zofia.png', 'Gościński.jpg', 'Goscinski.jpg']
        self.assertEqual(len({build_website.photo_slug(x) for x in names}), len(names))

    def test_legacy_alias_requires_existing_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = {'legacy_photo_urls': {'09': 'Census.jpg'}}
            with patch.object(build_website, 'DIST', root), patch.object(build_website, 'CONFIG', config):
                with self.assertRaises(FileNotFoundError):
                    build_website.build_legacy_photo_links()
                destination = root / 'america/photos' / build_website.photo_slug('Census.jpg')
                destination.mkdir(parents=True)
                (destination / 'index.html').write_text('photo')
                build_website.build_legacy_photo_links()
                self.assertIn(build_website.photo_slug('Census.jpg'), (root / 'america/photos/09/index.html').read_text())

    def test_link_check_handles_encoded_files_and_missing_targets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'my photo.jpg').write_bytes(b'image')
            page = root / 'index.html'
            page.write_text('<img src="/my%20photo.jpg"><a href="https://example.com">Remote</a>')
            self.assertEqual(website.check_links(root), 1)
            page.write_text('<img src="/missing.jpg">')
            with self.assertRaisesRegex(ValueError, 'missing.jpg'):
                website.check_links(root)

    def test_staging_rejects_stale_build_before_changing_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkout = root / 'site'
            (checkout / '.openai').mkdir(parents=True)
            (checkout / '.openai/hosting.json').write_text(json.dumps({'project_id': 'test', 'static': {'directory': 'dist'}}))
            (checkout / 'dist').mkdir()
            (checkout / 'dist/index.html').write_text('existing')
            config = root / 'site.json'
            config.write_text('{"project_id":"test"}')
            output = root / 'output'
            output.mkdir()
            (output / 'build.json').write_text('{"input_sha256":"old"}')
            with patch.object(website, 'CONFIG_PATH', config), patch.object(website, 'OUTPUT', output), patch.object(website, 'input_digest', return_value='new'):
                with self.assertRaisesRegex(ValueError, 'stale'):
                    website.stage(checkout)
            self.assertEqual((checkout / 'dist/index.html').read_text(), 'existing')


if __name__ == '__main__':
    unittest.main()
