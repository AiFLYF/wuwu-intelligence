from html.parser import HTMLParser
import json
from pathlib import Path
import re
import unittest
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'


class PageReferences(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.links = []
        self.stack = []
        self.nesting_errors = []

    def handle_starttag(self, tag, attrs):
        if tag not in {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}:
            self.stack.append(tag)
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        for key in ('src', 'href'):
            if attrs.get(key):
                self.links.append(attrs[key])

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1] != tag:
            self.nesting_errors.append((tag, self.stack[-1] if self.stack else None))
        else:
            self.stack.pop()


class ProjectIntegrityTests(unittest.TestCase):
    def test_demo_ids_links_and_assets_resolve(self):
        page = PageReferences()
        page.feed((DOCS / 'index.html').read_text(encoding='utf-8'))
        self.assertEqual(len(page.ids), len(set(page.ids)), 'Duplicate DOM ids')
        self.assertEqual(page.nesting_errors, [], 'HTML tags must remain properly nested')
        self.assertEqual(page.stack, [], 'Unclosed HTML tags')
        for link in page.links:
            parsed = urlsplit(link)
            if parsed.scheme or parsed.netloc:
                continue
            with self.subTest(link=link):
                if parsed.path:
                    self.assertTrue((DOCS / unquote(parsed.path)).is_file())
                elif parsed.fragment:
                    self.assertIn(unquote(parsed.fragment), page.ids)

    def test_local_css_and_module_dependencies_resolve(self):
        for file in (DOCS / 'assets').rglob('*'):
            if file.suffix not in ('.css', '.js') or 'vendor' in file.parts:
                continue
            text = file.read_text(encoding='utf-8')
            refs = re.findall(r'''(?:from\s*|import\(\s*)['"](\.[^'"]+)['"]''', text)
            refs += re.findall(r'''url\(['"]?(\.[^)'"]+)['"]?\)''', text)
            for ref in refs:
                with self.subTest(file=file.name, ref=ref):
                    self.assertTrue((file.parent / ref).resolve().is_file())

    def test_readme_local_links_resolve(self):
        readme = (ROOT / 'README.md').read_text(encoding='utf-8')
        for ref in re.findall(r'\[[^\]]*\]\(([^)]+)\)', readme):
            parsed = urlsplit(ref)
            if not parsed.scheme and parsed.path:
                with self.subTest(ref=ref):
                    self.assertTrue((ROOT / unquote(parsed.path)).is_file())

    def test_marketplace_points_to_a_shipped_skill(self):
        metadata = json.loads((ROOT / '.claude-plugin/marketplace.json').read_text(encoding='utf-8'))
        for plugin in metadata['plugins']:
            for path in plugin['skills']:
                self.assertTrue((ROOT / path / 'SKILL.md').is_file())

    def test_skill_reference_links_resolve_within_the_installed_skill(self):
        skill = ROOT / 'skills/wuwu-intelligence'
        for file in skill.rglob('*.md'):
            for ref in re.findall(r'\[[^\]]*\]\(([^)\s]+)\)', file.read_text(encoding='utf-8')):
                parsed = urlsplit(ref)
                if not parsed.scheme and parsed.path:
                    target = (file.parent / unquote(parsed.path)).resolve()
                    with self.subTest(file=file.name, ref=ref):
                        self.assertTrue(target.is_relative_to(skill.resolve()))
                        self.assertTrue(target.is_file())


if __name__ == '__main__':
    unittest.main()
