"""Regressions for photo link stability and publication integrity."""
import json
from pathlib import Path
import tempfile
import unittest
from urllib.parse import quote
from unittest.mock import patch

from scripts import build_website, website, visitor_access


class WebsiteTests(unittest.TestCase):
    def test_generated_icon_formats_and_versioned_links(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            with patch.object(build_website, 'DIST', output):
                build_website.build_assets()
            with Image.open(output / 'favicon.ico') as icon:
                self.assertEqual(icon.format, 'ICO')
            with Image.open(output / 'apple-touch-icon.png') as icon:
                self.assertEqual(icon.format, 'PNG')
                self.assertEqual(icon.size, (180, 180))
            self.assertEqual((output / 'apple-touch-icon.png').read_bytes(),
                             (output / 'apple-touch-icon-precomposed.png').read_bytes())
            self.assertIn('/assets/favicon.svg?v=', build_website.page('Example', '<p>Page</p>'))

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

    def test_encoded_source_links_resolve_to_stable_photo_pages(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            photos = root / 'photos'
            photos.mkdir()
            name = '1905 - Józef? (line 5).gif'
            (photos / name).write_bytes(b'image')
            config = {'collections': {'america': {'directory': 'photos'}}}
            with patch.object(build_website, 'ROOT', root), patch.object(build_website, 'CONFIG', config):
                mapping = build_website.america_link_map()
            source = '../../media/SophieJoseph/' + name
            _, rendered = build_website.markdown(f'[Manifest]({quote(source, safe="/")})', mapping)
            self.assertEqual(rendered, f'<p><a href="/america/photos/{build_website.photo_slug(name)}/">Manifest</a></p>')

    def test_display_captions_preserve_photo_routes_and_scan_resolution(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            photos = root / 'photos'
            photos.mkdir()
            name = 'Original scan.tif'
            Image.new('RGB', (1800, 100), 'white').save(photos / name)
            output = root / 'dist'
            with patch.object(build_website, 'DIST', output):
                mapping = build_website.image_gallery(
                    photos, 'assets/scans', 'Scans', 'america/photos/index.html',
                    convert=True, detail_pages=True,
                    photo_captions={name: 'Readable <caption>'},
                    photo_notes={name: 'An uncertain & preserved account'},
                )
            self.assertEqual(mapping[name], f'/america/photos/{build_website.photo_slug(name)}/')
            detail = (output / mapping[name].strip('/') / 'index.html').read_text(encoding='utf-8')
            self.assertIn('Readable &lt;caption&gt;', detail)
            self.assertIn('Original scan.tif', detail)
            self.assertIn('An uncertain &amp; preserved account', detail)
            self.assertIn('Open full-size image', detail)
            self.assertIn('Return to the America story', detail)
            with Image.open(next((output / 'assets/scans').glob('*.jpg'))) as image:
                self.assertEqual(image.size, (1800, 100))

    def test_gallery_description_renders_before_photo_grid(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            photos = root / 'photos'
            photos.mkdir()
            output = root / 'dist'
            description = '<p>Explore <a href="https://muszyna.pl/">Muszyna</a> and <a href="https://www.youtube.com/@muszynatv">Muszyna.TV</a>.</p>'
            with patch.object(build_website, 'DIST', output):
                build_website.image_gallery(photos, 'assets/photos/muszyna', 'Pictures from Muszyna',
                                            'photos/index.html', description_html=description)
            page = (output / 'photos/index.html').read_text(encoding='utf-8')
            self.assertIn(description, page)
            self.assertLess(page.index(description), page.index('<div class="media-grid'))

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

    def test_photo_navigation_stays_in_its_gallery(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            photos = root / 'photos'
            photos.mkdir()
            names = ['01.jpg', '02.jpg', '03.jpg']
            for name in names:
                (photos / name).write_bytes(b'image')
            output = root / 'dist'
            for route in ['photos', 'america/photos']:
                with self.subTest(route=route), patch.object(build_website, 'DIST', output):
                    first_photo = '03.jpg' if route == 'photos' else None
                    ordered = ['03.jpg', '01.jpg', '02.jpg'] if first_photo else names
                    links = build_website.image_gallery(photos, f'assets/{route}', 'Photos',
                                                         f'{route}/index.html', detail_pages=True,
                                                         first_photo=first_photo)
                    self.assertEqual(list(links), ordered)
                    pages = [(output / route / build_website.photo_slug(name) / 'index.html')
                             .read_text(encoding='utf-8') for name in ordered]
                    for content in pages:
                        self.assertIn(f'<a href="/{route}/">All photos</a>', content)
                    self.assertNotIn('>Previous</a>', pages[0])
                    self.assertIn(f'<a href="{links[ordered[1]]}">Next</a>', pages[0])
                    self.assertIn(f'<a href="{links[ordered[0]]}">Previous</a>', pages[1])
                    self.assertIn(f'<a href="{links[ordered[2]]}">Next</a>', pages[1])
                    self.assertNotIn('>Next</a>', pages[2])

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

    def test_production_staging_contains_code_but_no_public_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            static = root / 'preview'
            static.mkdir()
            original = '<html><body>Protected family content</body></html>'
            (static / 'index.html').write_text(original, encoding='utf-8')
            checkout = root / 'site'
            (checkout / '.openai').mkdir(parents=True)
            visitor_access.stage_gateway(checkout, static, {'project_id': 'test', 'static': {'directory': 'dist'}})
            hosting = json.loads((checkout / '.openai/hosting.json').read_text())
            self.assertNotIn('static', hosting)
            self.assertEqual(hosting['d1'], 'DB')
            self.assertEqual(hosting['r2'], 'BUCKET')
            self.assertFalse((checkout / 'dist/index.html').exists())
            worker = (checkout / 'dist/server/index.js').read_text()
            self.assertNotIn('Protected family content', worker)
            self.assertNotIn('email.csv', worker)
            self.assertIn('export default createGateway(', worker)
            # Preview bytes remain unchanged and contain no identification form or script.
            self.assertEqual((static / 'index.html').read_text(), original)
            self.assertEqual((checkout / 'archive-assets/index.html').read_text(), original)

    def test_private_csv_import_validates_without_publishing_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'visitors.csv'
            path.write_text('Name,Email Address\nJózef, FAMILY@example.test \n', encoding='utf-8')
            self.assertEqual(visitor_access.load_visitors(path), [{'name': 'Józef', 'email': 'family@example.test'}])
            path.write_text('Name,Email Address\nOne,a@example.test\nTwo,A@example.test\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Duplicate email at visitor CSV row 3'):
                visitor_access.load_visitors(path)

    def test_production_contact_links_use_archive_owner_address_without_changing_preview(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            static = root / 'preview'
            static.mkdir()
            original = '<a href="mailto:owner@example.test">Comments</a>'
            (static / 'index.html').write_text(original)
            checkout = root / 'site'
            (checkout / '.openai').mkdir(parents=True)
            visitor_access.stage_gateway(checkout, static, {'project_id': 'test'})
            self.assertIn('<a href="mailto:rekarpyrce@gmail.com">Contact the archive owner</a>',
                          (checkout / 'archive-assets/index.html').read_text())
            self.assertEqual((static / 'index.html').read_text(), original)


if __name__ == '__main__':
    unittest.main()
