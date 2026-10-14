import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('validate_skill', ROOT / 'tools/validate_skill.py')
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class SkillValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.skill = Path(self.temp.name) / 'example-skill'
        self.skill.mkdir()

    def write(self, frontmatter='', body=''):
        (self.skill / 'SKILL.md').write_text(
            f'---\nname: example-skill\ndescription: Useful device workflow\n{frontmatter}---\n{body}',
            encoding='utf-8')

    def test_multiline_yaml_description_and_metadata(self):
        metadata, error = validator.parse_frontmatter(
            '---\nname: example-skill\ndescription: >-\n  First line\n  second line\n'
            'metadata:\n  version: "1.0"\n---')
        self.assertIsNone(error)
        self.assertEqual(metadata['description'], 'First line second line')
        self.assertEqual(metadata['metadata']['version'], '1.0')

    def test_duplicate_or_nonstring_yaml_keys_fail(self):
        for text in ('name: one\nname: two', '1: test', 'metadata:\n  author: a\n  author: b'):
            with self.subTest(text=text):
                self.assertIsNotNone(validator.parse_frontmatter(f'---\n{text}\n---\n')[1])

    def test_optional_metadata_types_are_validated(self):
        for field in ('compatibility: [python]\n', 'license: 12\n', 'metadata:\n  version: 1.0\n'):
            with self.subTest(field=field):
                self.write(field)
                self.assertTrue(validator.check(self.skill)[0])

    def test_markdown_and_inline_resource_links_are_checked(self):
        self.write(body='[Guide](references/missing.md) and `scripts/missing.py`')
        self.assertEqual(len(validator.check(self.skill)[0]), 2)

    def test_external_links_and_hypothetical_project_paths_are_allowed(self):
        self.write(body='[Spec](https://agentskills.io/specification)\n`pc/cli.py`\n`devices.json`')
        self.assertEqual(validator.check(self.skill)[0], [])

    def test_resource_paths_cannot_escape_skill(self):
        self.write(body='[Other](../README.md)')
        self.assertIn('超出', validator.check(self.skill)[0][0])

    def test_container_does_not_silently_skip_broken_skill(self):
        self.write()
        broken = self.skill.parent / 'broken-skill'
        broken.mkdir()
        with contextlib.redirect_stdout(io.StringIO()) as output:
            status = validator.main([str(self.skill.parent)])
        self.assertEqual(status, 1)
        self.assertIn('broken-skill', output.getvalue())

    def test_empty_and_nonexistent_targets_fail(self):
        for path in (self.skill, self.skill / 'missing'):
            with self.subTest(path=path), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(validator.main([str(path)]), 1)

    def test_root_and_default_target_both_work(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(validator.main([str(ROOT)]), 0)
            self.assertEqual(validator.main([]), 0)


if __name__ == '__main__':
    unittest.main()
