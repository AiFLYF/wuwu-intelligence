import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/wuwu-intelligence/scripts/device_registry.py'
SPEC = importlib.util.spec_from_file_location('device_registry', SCRIPT)
registry = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(registry)


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='wuwu registry ')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / '注册表.json'
        self.project = Path(self.temp.name) / '设备 项目'
        self.project.mkdir()
        self.data = {'version': 1, 'devices': [{
            'name': 'test-device', 'aliases': ['灯板'], 'project_path': '设备 项目',
            'commands': {'color': {
                'desc': 'Set a color', 'argv': ['{python}', 'echo.py', '{r}'],
                'args': {'r': {'type': 'integer', 'description': 'red',
                               'minimum': 0, 'maximum': 255, 'default': 128}},
                'idempotent': True, 'timeout': 2,
            }}
        }]}

    def plan(self, arguments=None):
        return registry.make_plan(self.data, self.path, '灯板', 'color', arguments)

    def test_init_preserves_existing_bytes_on_repeat(self):
        self.assertTrue(registry.initialize(self.path))
        self.path.write_bytes(b'private user data\r\n')
        self.assertFalse(registry.initialize(self.path))
        self.assertEqual(self.path.read_bytes(), b'private user data\r\n')

    def test_default_data_location_is_outside_the_skill_installation(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(registry.Path, 'home', return_value=Path(self.temp.name)):
            self.assertEqual(registry.default_registry(), Path(self.temp.name) / '.wuwu-intelligence/devices.json')

    def test_registry_selection_respects_explicit_path_and_environment(self):
        configured = Path(self.temp.name) / 'shared.json'
        with patch.dict(os.environ, {'WUWU_DEVICES_FILE': str(configured)}):
            # Windows temporary paths may contain 8.3 aliases such as RUNNER~1.
            self.assertEqual(registry.select_registry()[0], configured.resolve())
            self.assertEqual(registry.select_registry(self.path)[0], self.path.resolve())

    def test_legacy_fallback_does_not_hide_existing_devices_with_an_empty_file(self):
        legacy = Path(self.temp.name) / 'old.json'
        legacy.write_text(json.dumps(self.data), encoding='utf-8')
        destination = Path(self.temp.name) / 'new.json'
        with patch.dict(os.environ, {}, clear=True), patch.object(registry, 'LEGACY_REGISTRY', legacy), patch.object(registry, 'default_registry', return_value=destination):
            self.assertEqual(registry.select_registry(), (legacy, True))
            with self.assertRaisesRegex(registry.RegistryError, 'migrate'):
                registry.select_registry(action='init')
            self.assertFalse(destination.exists())

    def test_migration_preserves_source_and_relative_project_meaning(self):
        self.data['private_note'] = '保留自定义字段'
        self.path.write_text(json.dumps(self.data, ensure_ascii=False), encoding='utf-8')
        original = self.path.read_bytes()
        destination = Path(self.temp.name) / 'external' / 'devices.json'
        self.assertEqual(registry.migrate_registry(self.path, destination), 1)
        migrated = registry.load_registry(destination)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(migrated['private_note'], '保留自定义字段')
        self.assertEqual(migrated['devices'][0]['project_path'], str(self.project.resolve()))
        self.assertEqual(registry.make_plan(migrated, destination, '灯板', 'color')['cwd'], str(self.project.resolve()))
        with self.assertRaisesRegex(registry.RegistryError, '未覆盖'):
            registry.migrate_registry(self.path, destination)

    def test_storage_migration_preserves_old_command_formats(self):
        device = self.data['devices'][0]
        device['quick_examples'] = device.pop('commands')
        self.path.write_text(json.dumps(self.data), encoding='utf-8')
        destination = Path(self.temp.name) / 'saved.json'
        registry.migrate_registry(self.path, destination)
        self.assertIn('quick_examples', registry.load_registry(destination)['devices'][0])

    def test_migration_of_a_moved_backup_uses_the_original_base_directory(self):
        backup = Path(self.temp.name) / 'backup/old.json'
        backup.parent.mkdir()
        backup.write_text(json.dumps(self.data), encoding='utf-8')
        destination = Path(self.temp.name) / 'saved.json'
        registry.migrate_registry(backup, destination, base_dir=self.path.parent)
        self.assertEqual(registry.load_registry(destination)['devices'][0]['project_path'], str(self.project.resolve()))

    def test_empty_registry_does_not_execute_template(self):
        data = {'devices': [], '_template': self.data['devices'][0]}
        self.assertEqual(registry.validate_registry(data), [])
        with self.assertRaises(registry.RegistryError):
            registry.make_plan(data, self.path, '灯板', 'color')

    def test_default_and_explicit_zero_are_distinct(self):
        self.assertEqual(self.plan()['argv'][-1], '128')
        self.assertEqual(self.plan({'r': 0})['argv'][-1], '0')

    def test_plan_resolves_project_relative_to_registry_not_cwd(self):
        plan = self.plan()
        self.assertEqual(Path(plan['cwd']), self.project.resolve())
        self.assertEqual(plan['argv'][0], sys.executable)
        self.assertFalse((self.project / 'result.json').exists())

    def test_missing_required_unknown_and_out_of_range_args_fail(self):
        del self.data['devices'][0]['commands']['color']['args']['r']['default']
        for arguments in ({}, {'r': 256}, {'r': -1}, {'r': True}, {'r': '1'}, {'r': 1, 'extra': 3}):
            with self.subTest(arguments=arguments), self.assertRaises(registry.RegistryError):
                self.plan(arguments)

    def test_ambiguous_aliases_fail_case_insensitively(self):
        second = copy.deepcopy(self.data['devices'][0])
        second['name'] = 'other-device'
        second['aliases'] = [' TEST-DEVICE ']
        self.data['devices'].append(second)
        with self.assertRaisesRegex(registry.RegistryError, '重复'):
            self.plan()

    def test_malformed_json_duplicate_keys_and_nonfinite_values_fail(self):
        for text in ('{"devices":', '{"devices":[],"devices":[]}', '{"value": NaN}', '{"value": Infinity}'):
            with self.subTest(text=text), self.assertRaises(registry.RegistryError):
                registry.parse_json(text)

    def test_windows_bom_is_supported(self):
        self.path.write_text(json.dumps(self.data, ensure_ascii=False), encoding='utf-8-sig')
        self.assertEqual(registry.load_registry(self.path), self.data)

    def test_invalid_argument_schema_is_reported(self):
        command = self.data['devices'][0]['commands']['color']
        for change in ({'type': 'array'}, {'minimum': '0'}, {'maximum': -1}, {'default': 300}, {'enum': []}, {'max': 100}):
            bad = copy.deepcopy(self.data)
            bad['devices'][0]['commands']['color']['args']['r'].update(change)
            with self.subTest(change=change), self.assertRaises(registry.RegistryError):
                registry.validate_registry(bad)
        command['argv'][-1] = '--red={r}'
        with self.assertRaises(registry.RegistryError):
            self.plan()

    def test_legacy_run_warns_and_is_never_implicitly_executed(self):
        self.data['devices'][0]['commands']['color'] = {'desc': 'legacy', 'run': 'echo hello'}
        self.assertEqual(len(registry.validate_registry(self.data)), 1)
        with self.assertRaisesRegex(registry.RegistryError, '旧格式'):
            self.plan()

    def test_old_quick_examples_get_an_actionable_migration_error(self):
        device = self.data['devices'][0]
        del device['commands']
        device['quick_examples'] = {'red': 'python pc/cli.py color 255 0 0'}
        with self.assertRaisesRegex(registry.RegistryError, 'quick_examples.*迁移'):
            registry.validate_registry(self.data)

    def test_execution_preserves_unicode_spaces_and_shell_characters(self):
        text = '中文 value & ; $(echo unsafe) "quoted" \\ path'
        script = self.project / 'echo.py'
        script.write_text(
            "import json,sys\nfrom pathlib import Path\n"
            "Path('result.json').write_text(json.dumps(sys.argv[1:], ensure_ascii=False), encoding='utf-8')\n",
            encoding='utf-8')
        command = self.data['devices'][0]['commands']['color']
        command['args']['r'] = {'type': 'string', 'description': 'literal text'}
        plan = self.plan({'r': text})
        self.assertFalse((self.project / 'result.json').exists())
        self.assertEqual(registry.execute_plan(plan), 0)
        self.assertEqual(json.loads((self.project / 'result.json').read_text(encoding='utf-8')), [text])

    def test_timeout_never_retries_even_for_idempotent_commands(self):
        with patch.object(registry.subprocess, 'run', side_effect=subprocess.TimeoutExpired('test', 2)) as run:
            with self.assertRaisesRegex(registry.RegistryError, '状态未知'):
                registry.execute_plan(self.plan())
            self.assertEqual(run.call_count, 1)
            self.assertIs(run.call_args.kwargs['shell'], False)

    def test_child_failure_exit_code_is_preserved(self):
        with patch.object(registry.subprocess, 'run', return_value=subprocess.CompletedProcess([], 7)):
            self.assertEqual(registry.execute_plan(self.plan()), 7)

    def test_cli_json_is_utf8_even_when_inherited_encoding_is_ascii(self):
        self.path.write_text(json.dumps(self.data, ensure_ascii=False), encoding='utf-8')
        result = subprocess.run(
            [sys.executable, str(SCRIPT), '--registry', str(self.path), 'list'],
            capture_output=True, env={**os.environ, 'PYTHONIOENCODING': 'ascii'}, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout.decode('utf-8'))[0]['aliases'], ['灯板'])

    def test_child_python_output_is_utf8_through_the_real_run_command(self):
        (self.project / 'echo.py').write_text("print('灯板已响应 ✓')\n", encoding='utf-8')
        self.path.write_text(json.dumps(self.data, ensure_ascii=False), encoding='utf-8')
        result = subprocess.run(
            [sys.executable, str(SCRIPT), '--registry', str(self.path), 'run', '灯板', 'color'],
            capture_output=True, env={**os.environ, 'PYTHONIOENCODING': 'ascii'}, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.decode('utf-8').strip(), '灯板已响应 ✓')

    def test_no_project_directory_is_created_by_run(self):
        self.data['devices'][0]['project_path'] = 'missing'
        with self.assertRaisesRegex(registry.RegistryError, '不存在'):
            registry.execute_plan(self.plan())
        self.assertFalse((self.path.parent / 'missing').exists())

    def test_missing_registry_returns_diagnostic_not_traceback(self):
        with contextlib.redirect_stderr(io.StringIO()) as output:
            self.assertEqual(registry.main(['--registry', str(self.path), 'validate']), 2)
        self.assertIn('无法读取', output.getvalue())
        self.assertNotIn('Traceback', output.getvalue())

    def test_shipped_example_and_template_are_valid(self):
        example = registry.load_registry(ROOT / 'skills/wuwu-intelligence/devices.json.example')
        self.assertEqual(registry.validate_registry(example), [])
        self.assertEqual(registry.validate_registry({'devices': [example['_template']]}), [])


if __name__ == '__main__':
    unittest.main()
