import copy
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/wuwu-intelligence/scripts/device_registry.py'
SPEC = importlib.util.spec_from_file_location('registry_editing', SCRIPT)
registry = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(registry)


class RegistryEditingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='wuwu editing ')
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.path = self.folder / 'devices.json'
        self.device = {
            'name': 'led', 'aliases': ['灯板'], 'project_path': str(self.folder),
            'hardware': {'board': 'simulator', 'custom': 'preserve'},
            'commands': {
                'color': {'desc': 'Color', 'argv': ['{python}', 'cli.py', '{r}'],
                          'args': {'r': {'type': 'integer', 'description': 'red'}}, 'idempotent': True},
                'status': {'desc': 'Status', 'argv': ['{python}', 'cli.py', 'status'], 'read_only': True},
            }, 'custom': {'keep': True},
        }
        self.data = {'version': 1, 'devices': [self.device], 'vendor': {'keep': 'root metadata'}}
        self.path.write_text(json.dumps(self.data, ensure_ascii=False), encoding='utf-8')

    def snapshot(self):
        return registry.show_device(self.path, '灯板')

    def definition(self, name):
        value = copy.deepcopy(self.device)
        value.update(name=name, aliases=[name + '-alias'])
        return value

    def file(self, name, value):
        path = self.folder / name
        path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
        return path

    def launch(self, *arguments):
        process = subprocess.Popen([sys.executable, str(SCRIPT), '--registry', str(self.path), *arguments],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addCleanup(self.cleanup_process, process)
        return process

    @staticmethod
    def stop(process):
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)

    @classmethod
    def cleanup_process(cls, process):
        cls.stop(process)
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None:
                stream.close()

    def test_show_returns_data_and_revision_from_the_same_snapshot(self):
        before = self.path.read_bytes()
        snapshot = self.snapshot()
        self.assertEqual(snapshot['revision'], hashlib.sha256(before).hexdigest())
        self.assertEqual(snapshot['device'], self.device)
        self.assertFalse(self.path.with_name('devices.json.lock').exists())

    def test_register_preserves_other_devices_metadata_and_original_backup(self):
        original = self.path.read_bytes()
        result = registry.register_device(self.path, self.definition('sensor'))
        data = registry.load_registry(self.path)
        self.assertEqual([d['name'] for d in data['devices']], ['led', 'sensor'])
        self.assertEqual(data['vendor'], self.data['vendor'])
        self.assertEqual(data['devices'][0], self.device)
        self.assertEqual(Path(result['backup']).read_bytes(), original)
        self.assertEqual(result['revision'], hashlib.sha256(self.path.read_bytes()).hexdigest())

    def test_invalid_registration_never_changes_data_or_creates_a_backup(self):
        original = self.path.read_bytes()
        other = self.definition('sensor')
        other['aliases'] = ['灯板']
        with self.assertRaises(registry.RegistryError):
            registry.register_device(self.path, other)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertFalse((self.folder / '.wuwu-backups').exists())

    def test_register_preview_does_not_even_create_a_directory(self):
        target = self.folder / 'missing' / 'new.json'
        result = registry.register_device(target, self.definition('sensor'), dry_run=True)
        self.assertEqual(result['status'], 'planned')
        self.assertIsNone(result['revision'])
        self.assertEqual(len(result['next_revision']), 64)
        self.assertFalse(target.parent.exists())

    def test_register_creates_a_complete_new_registry_without_a_backup(self):
        target = self.folder / 'new/sub/devices.json'
        result = registry.register_device(target, self.definition('sensor'))
        self.assertEqual(result['status'], 'registered')
        self.assertIsNone(result['backup'])
        self.assertIsNone(result['previous_revision'])
        self.assertEqual(registry.show_device(target, 'sensor')['revision'], result['revision'])
        self.assertEqual(len(registry.load_registry(target)['devices']), 1)

    def test_update_merges_selected_maps_and_preserves_other_fields(self):
        revision = self.snapshot()['revision']
        result = registry.update_device(self.path, '灯板', {'hardware': {'board': 'new'}, 'description': 'updated'}, revision)
        after = self.snapshot()['device']
        self.assertEqual(after['hardware'], {'board': 'new', 'custom': 'preserve'})
        self.assertEqual(after['commands'], self.device['commands'])
        self.assertEqual(after['custom'], self.device['custom'])
        self.assertEqual(result['status'], 'updated')

    def test_replacing_a_command_does_not_keep_old_args_or_retry_flags(self):
        command = {'desc': 'New operation', 'argv': ['{python}', 'new.py']}
        registry.update_device(self.path, 'led', {'commands': {'color': command}}, self.snapshot()['revision'])
        after = self.snapshot()['device']
        self.assertEqual(after['commands']['color'], command)
        self.assertEqual(after['commands']['status'], self.device['commands']['status'])
        self.assertFalse(registry.make_plan(registry.load_registry(self.path), self.path, 'led', 'color')['idempotent'])

    def test_incomplete_command_replacement_and_rename_are_rejected(self):
        for changes in ({'commands': {'color': {'desc': 'missing argv'}}}, {'name': 'other'}):
            original = self.path.read_bytes()
            with self.subTest(changes=changes), self.assertRaises(registry.RegistryError):
                registry.update_device(self.path, 'led', changes, self.snapshot()['revision'])
            self.assertEqual(self.path.read_bytes(), original)

    def test_stale_revision_cannot_overwrite_a_newer_update(self):
        old = self.snapshot()['revision']
        registry.update_device(self.path, 'led', {'description': 'first'}, old)
        current = self.path.read_bytes()
        with self.assertRaises(registry.RegistryConflict):
            registry.update_device(self.path, 'led', {'description': 'stale'}, old)
        self.assertEqual(self.path.read_bytes(), current)

    def test_a_show_envelope_is_not_silently_stored_as_device_metadata(self):
        snapshot = self.snapshot()
        original = self.path.read_bytes()
        with self.assertRaises(registry.RegistryError):
            registry.update_device(self.path, 'led', snapshot, snapshot['revision'])
        self.assertEqual(self.path.read_bytes(), original)

    def test_noop_and_update_preview_leave_original_bytes_untouched(self):
        original = self.path.read_bytes()
        revision = self.snapshot()['revision']
        plan = registry.update_device(self.path, 'led', {'description': 'preview'}, revision, dry_run=True)
        self.assertEqual(plan['revision'], revision)
        self.assertNotEqual(plan['next_revision'], revision)
        self.assertFalse(self.path.with_name('devices.json.lock').exists())
        result = registry.update_device(self.path, 'led', {}, revision)
        self.assertEqual(result['status'], 'unchanged')
        self.assertEqual(self.path.read_bytes(), original)
        self.assertIsNone(result['backup'])

    def test_failed_atomic_replace_keeps_original_and_cleans_temporary_files(self):
        original = self.path.read_bytes()
        with patch.object(registry.os, 'replace', side_effect=OSError('injected write failure')):
            with self.assertRaises(OSError):
                registry.update_device(self.path, 'led', {'description': 'new'}, self.snapshot()['revision'])
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.folder.glob('*.tmp')), [])
        backup = next((self.folder / '.wuwu-backups').glob('*.bak'))
        self.assertEqual(backup.read_bytes(), original)

    def test_a_transient_windows_publish_error_can_recover(self):
        busy = PermissionError('temporary sharing violation')
        busy.winerror = 32
        original_replace = registry.os.replace
        attempts = []
        def publish(source, destination):
            attempts.append(1)
            if len(attempts) == 1:
                raise busy
            return original_replace(source, destination)
        with patch.object(registry.os, 'replace', side_effect=publish):
            result = registry.update_device(self.path, 'led', {'description': 'recovered'}, self.snapshot()['revision'])
        self.assertEqual(result['status'], 'updated')
        self.assertEqual(len(attempts), 2)
        self.assertEqual(self.snapshot()['device']['description'], 'recovered')

    @unittest.skipUnless(sys.platform == 'win32', 'Windows file sharing behavior')
    def test_real_windows_reader_can_temporarily_block_then_release_a_commit(self):
        import ctypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        create = kernel.CreateFileW
        create.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
                           ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
        create.restype = ctypes.c_void_p
        close = kernel.CloseHandle
        close.argtypes = [ctypes.c_void_p]
        close.restype = ctypes.c_int
        revision = self.snapshot()['revision']
        changes = self.file('sharing-test.json', {'description': 'reader released'})
        # Permit reading/writing, but temporarily deny deletion/rename of this test file.
        handle = create(str(self.path), 0x80000000, 3, None, 3, 0x80, None)
        self.assertNotEqual(handle, ctypes.c_void_p(-1).value)
        try:
            process = self.launch('update', 'led', '--file', str(changes), '--if-revision', revision)
            backup = self.folder / '.wuwu-backups' / f'devices.json.{revision}.bak'
            deadline = time.monotonic() + 10
            while not backup.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertTrue(backup.exists(), 'Writer did not reach its commit')
            time.sleep(.12)
            self.assertIsNone(process.poll(), 'Writer should wait briefly for the reader')
        finally:
            close(handle)
        stdout, stderr = process.communicate(timeout=10)
        self.assertEqual(process.returncode, 0, stderr.decode('utf-8'))
        self.assertEqual(json.loads(stdout)['status'], 'updated')
        self.assertEqual(self.snapshot()['device']['description'], 'reader released')

    def test_publish_retry_does_not_overwrite_an_external_change(self):
        busy = PermissionError('temporary access denial')
        busy.winerror = 5
        external = copy.deepcopy(self.data)
        external['devices'][0]['description'] = 'external edit'
        changed_bytes = json.dumps(external).encode('utf-8')
        def edit_during_publish(*_args):
            self.path.write_bytes(changed_bytes)
            raise busy
        with patch.object(registry.os, 'replace', side_effect=edit_during_publish) as replace:
            with self.assertRaises(registry.RegistryConflict):
                registry.update_device(self.path, 'led', {'description': 'stale'}, self.snapshot()['revision'])
        self.assertEqual(replace.call_count, 1)
        self.assertEqual(self.path.read_bytes(), changed_bytes)

    def test_permanent_publish_error_stops_and_preserves_original(self):
        busy = PermissionError('permanent access denial')
        busy.winerror = 5
        original = self.path.read_bytes()
        ticks = itertools.count(0, .5)
        with patch.object(registry.os, 'replace', side_effect=busy), \
             patch.object(registry.time, 'monotonic', side_effect=lambda: next(ticks)), \
             patch.object(registry.time, 'sleep'):
            with self.assertRaises(PermissionError):
                registry.update_device(self.path, 'led', {'description': 'cannot write'}, self.snapshot()['revision'])
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.folder.glob('*.tmp')), [])

    def test_six_real_processes_can_register_without_lost_devices(self):
        processes = [self.launch('register', '--file', str(self.file(f'{i}.json', self.definition(f'device-{i}'))))
                     for i in range(6)]
        for process in processes:
            stdout, stderr = process.communicate(timeout=20)
            self.assertEqual(process.returncode, 0, stderr.decode('utf-8'))
            self.assertEqual(json.loads(stdout.decode('utf-8'))['status'], 'registered')
        names = {d['name'] for d in registry.load_registry(self.path)['devices']}
        self.assertEqual(names, {'led', *(f'device-{i}' for i in range(6))})

    def test_concurrent_updates_with_one_revision_have_exactly_one_winner(self):
        revision = self.snapshot()['revision']
        processes = [self.launch('update', 'led', '--file', str(self.file(f'patch-{i}.json', {'description': str(i)})),
                                 '--if-revision', revision) for i in range(2)]
        results = [(p, p.communicate(timeout=20)) for p in processes]
        self.assertEqual(sorted(p.returncode for p, _ in results), [0, 2])
        failure = next(output for p, output in results if p.returncode == 2)
        self.assertIn('E_CONFLICT', failure[1].decode('utf-8'))
        self.assertIn(self.snapshot()['device']['description'], ['0', '1'])

    def test_kernel_lock_is_released_when_a_writer_is_terminated(self):
        ready = self.folder / 'ready'
        code = '''import importlib.util,sys,time
from pathlib import Path
spec=importlib.util.spec_from_file_location('locked',sys.argv[1])
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
with module.registry_lock(Path(sys.argv[2])):
    Path(sys.argv[3]).write_text('ready')
    time.sleep(30)
'''
        process = subprocess.Popen([sys.executable, '-c', code, str(SCRIPT), str(self.path), str(ready)],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addCleanup(self.cleanup_process, process)
        deadline = time.monotonic() + 10
        while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(.02)
        self.assertTrue(ready.exists(), 'Lock holder failed to start')
        with self.assertRaises(registry.RegistryConflict):
            with registry.registry_lock(self.path, timeout=.05):
                self.fail('A second writer acquired the lock')
        self.stop(process)
        process.communicate(timeout=5)
        self.assertEqual(registry.register_device(self.path, self.definition('after-crash'))['status'], 'registered')
        self.assertTrue(self.path.with_name('devices.json.lock').exists())


if __name__ == '__main__':
    unittest.main()
