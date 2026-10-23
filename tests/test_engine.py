#!/usr/bin/env python3
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import unittest
from unittest import mock

CODE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('smart', CODE / 'scripts/smart.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)

class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='sv-')
        self.root = Path(self.tmp.name)
        shutil.copy(CODE / 'server.properties', self.root / 'server.properties')
        shutil.copytree(CODE / 'config', self.root / 'config')
        s.prepare(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def world(self):
        world = self.root / 'world'
        world.mkdir(exist_ok=True)
        (world / 'level.dat').write_bytes(b'test-level')
        (world / 'playerdata').mkdir(exist_ok=True)
        (world / 'playerdata/player.dat').write_bytes(b'inventory')
        return world

class MemoryTests(unittest.TestCase):
    def test_profiles_stay_below_current_budget(self):
        heaps = []
        for profile in ('economico', 'equilibrado', 'desempenho'):
            plan = s.memory_plan({'PROFILE': profile, 'MAX_AUTO_HEAP_MB': '4096'}, 8192, 6500)
            self.assertLessEqual(plan['xmx_mb'], min(4096, 6500 - 1024 - 256))
            self.assertLessEqual(plan['xms_mb'], plan['xmx_mb'])
            heaps.append(plan['xmx_mb'])
        self.assertEqual(heaps, sorted(set(heaps)))

    def test_low_ram_rejected(self):
        with self.assertRaises(s.SmartError):
            s.memory_plan({}, 2048, 600)

    def test_explicit_excess_rejected(self):
        with self.assertRaises(s.SmartError):
            s.memory_plan({'HEAP_MAX_MB': '4096'}, 8192, 3000)

    def test_explicit_heap_and_xms_capped(self):
        plan = s.memory_plan({'HEAP_MAX_MB': '768', 'HEAP_MIN_MB': '2048'}, 8192, 4000)
        self.assertEqual((plan['xmx_mb'], plan['xms_mb']), (768, 768))

    def test_bad_profile(self):
        with self.assertRaises(s.SmartError):
            s.memory_plan({'PROFILE': 'magic'}, 8192, 4000)

    def test_negative_reserve(self):
        with self.assertRaises(s.SmartError):
            s.memory_plan({'RESERVED_MB': '-1'}, 8192, 4000)

    def test_real_memory_detection(self):
        total, available = s.ram()
        self.assertGreater(total, 0)
        self.assertLessEqual(available, total)

class StorageTests(Fixture):
    def test_backup_restore_inventories_and_preserve_previous(self):
        world = self.world()
        archive = s.backup_offline(self.root)
        (world / 'playerdata/player.dat').write_bytes(b'changed')
        s.restore(self.root, archive, True)
        self.assertEqual((world / 'playerdata/player.dat').read_bytes(), b'inventory')
        old = list((self.root / 'backups').glob('restore-previous-*/world/playerdata/player.dat'))
        self.assertEqual(len(old), 1)
        self.assertEqual(old[0].read_bytes(), b'changed')

    def test_corruption_refused_without_touching_world(self):
        world = self.world()
        archive = Path(s.backup_offline(self.root))
        archive.write_bytes(b'corrupted')
        with self.assertRaises(s.SmartError):
            s.restore(self.root, archive, True)
        self.assertEqual((world / 'level.dat').read_bytes(), b'test-level')

    def test_path_traversal_refused(self):
        self.world()
        archive = self.root / 'backups/evil.tar.gz'
        with tarfile.open(archive, 'w:gz') as tar:
            item = tarfile.TarInfo('../escaped')
            item.size = 3
            tar.addfile(item, io.BytesIO(b'bad'))
        Path(str(archive) + '.sha256').write_text(s.digest(archive) + '\n')
        with self.assertRaises(s.SmartError):
            s.restore(self.root, archive, True)
        self.assertFalse((self.root.parent / 'escaped').exists())
        self.assertTrue((self.root / 'world/level.dat').exists())

    def test_symlink_restore_refused(self):
        self.world()
        archive = self.root / 'backups/link.tar.gz'
        with tarfile.open(archive, 'w:gz') as tar:
            item = tarfile.TarInfo('world/evil')
            item.type = tarfile.SYMTYPE
            item.linkname = '/etc'
            tar.addfile(item)
        Path(str(archive) + '.sha256').write_text(s.digest(archive) + '\n')
        with self.assertRaises(s.SmartError):
            s.restore(self.root, archive, True)

    def test_world_symlink_backup_refused(self):
        world = self.world()
        (world / 'link').symlink_to('/etc/passwd')
        with self.assertRaises(s.SmartError):
            s.backup_offline(self.root)

    def test_no_space_does_not_prune_old_backup(self):
        self.world()
        old = s.backup_offline(self.root)
        with mock.patch.object(s, 'free_mb', return_value=0):
            with self.assertRaises(s.SmartError):
                s.backup_offline(self.root)
        self.assertTrue(Path(old).exists())

    def test_rotation_and_concurrent_backup(self):
        self.world()
        (self.root / 'config/backup.conf').write_text('KEEP_BACKUPS=2\n')
        for _ in range(3):
            s.backup_offline(self.root)
        self.assertEqual(len(list((self.root / 'backups').glob('smartvanilla-*.tar.gz'))), 2)
        with s.lock(self.root / '.run/backup.lock'):
            with self.assertRaises(s.SmartError):
                s.backup_offline(self.root)

    def test_restore_confirmation_and_engine_lock(self):
        self.world()
        archive = s.backup_offline(self.root)
        with self.assertRaises(s.SmartError):
            s.restore(self.root, archive, False)
        with s.lock(self.root / '.run/engine.lock'):
            with self.assertRaises(s.SmartError):
                s.restore(self.root, archive, True)

    def test_setup_is_repeatable_and_preserves_configuration(self):
        world = self.world()
        original = (self.root / 'server.properties').read_bytes()
        s.ensure_eula(self.root, True)  # Test fixture only; never a real game process.
        for _ in range(2):
            s.prepare(self.root)
            s.props(self.root)
            s.ensure_eula(self.root)
        self.assertEqual((world / 'level.dat').read_bytes(), b'test-level')
        self.assertEqual((self.root / 'server.properties').read_bytes(), original)

    def test_eula_never_accepted_implicitly(self):
        with mock.patch('sys.stdin.isatty', return_value=False):
            with self.assertRaises(s.SmartError):
                s.ensure_eula(self.root)
        self.assertEqual(s.settings(self.root / 'eula.txt')['eula'], 'false')

    def test_existing_invalid_jar_preserved(self):
        jar = self.root / 'server.jar'
        jar.write_bytes(b'bad-existing-file')
        with self.assertRaises(s.SmartError):
            s.download(self.root)
        self.assertEqual(jar.read_bytes(), b'bad-existing-file')

    def test_configuration_is_data_not_shell(self):
        path = self.root / 'config/memory.conf'
        path.write_text('PROFILE=$(touch /tmp/SMART_SHOULD_NOT_EXIST)\n')
        with self.assertRaises(s.SmartError):
            s.memory_plan(s.settings(path), 8192, 5000)

    def test_vanilla_multiplayer_defaults(self):
        p = s.props(self.root)
        expected = {'server-port': '25565', 'server-ip': '', 'online-mode': 'true',
                    'enable-rcon': 'false', 'gamemode': '0', 'difficulty': '2',
                    'max-players': '10', 'view-distance': '6', 'allow-nether': 'true',
                    'generate-structures': 'true', 'white-list': 'false'}
        for key, value in expected.items():
            self.assertEqual(p[key], value)
        self.assertFalse((self.root / 'mods').exists())
        self.assertFalse((self.root / 'plugins').exists())

    def test_rcon_and_unsafe_world_path_rejected(self):
        path = self.root / 'server.properties'
        path.write_text('level-name=../../data\n')
        with self.assertRaises(s.SmartError):
            s.props(self.root)
        path.write_text('enable-rcon=true\n')
        with self.assertRaises(s.SmartError):
            s.props(self.root)

def unix_available():
    try:
        with socket.socket(socket.AF_UNIX):
            return True
    except OSError:
        return False


@unittest.skipUnless(unix_available(), 'Ambiente bloqueia AF_UNIX; os testes completos rodam no GitHub Actions')
class SupervisorTests(Fixture):
    def setUp(self):
        super().setUp()
        sock = socket.socket()
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
        sock.close()
        path = self.root / 'server.properties'
        path.write_text(path.read_text().replace('server-port=25565', f'server-port={port}'))
        with open(self.root / 'config/maintenance.conf', 'a') as out:
            out.write('\nRESTART_DELAY_SECONDS=1\nMAX_RESTART_ATTEMPTS=2\nBACKUP_WARNING_SECONDS=0\nSTOP_TIMEOUT_SECONDS=5\n')
        (self.root / 'config/backup.conf').write_text('BACKUP_INTERVAL_SECONDS=0\nBACKUP_ON_STOP=false\nKEEP_BACKUPS=3\n')
        self.process = None
        self.output = None

    def start(self, *flags):
        self.output = open(self.root / 'test-engine-output.txt', 'w')
        self.process = subprocess.Popen([sys.executable, str(CODE / 'tests/fake_runner.py'), str(self.root), *flags], stdout=self.output, stderr=subprocess.STDOUT)
        self.wait_state(lambda st: st['state'] == 'online')

    def wait_state(self, predicate, timeout=15):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            try:
                state = s.request(self.root, 'status')
                if predicate(state):
                    return state
            except (s.SmartError, OSError):
                pass
            if self.process and self.process.poll() is not None:
                self.fail((self.root / 'test-engine-output.txt').read_text())
            time.sleep(0.1)
        self.fail('Timed out waiting for supervisor\n' + (self.root / 'test-engine-output.txt').read_text())

    def tearDown(self):
        if self.process and self.process.poll() is None:
            try:
                s.request(self.root, 'stop')
                self.process.wait(timeout=12)
            except Exception:
                self.process.terminate()
                self.process.wait(timeout=15)
        if self.output:
            self.output.close()
        super().tearDown()

    def test_start_save_console_stop_and_status(self):
        self.start()
        state = s.request(self.root, 'status')
        self.assertTrue(state['tcp_local'])
        self.assertIsNotNone(state['java_pid'])
        s.request(self.root, 'save')
        self.assertTrue((self.root / 'world/saved-marker').exists())
        self.assertIsNotNone(s.request(self.root, 'status')['last_save'])
        s.request(self.root, 'command', command='say test')
        s.request(self.root, 'stop')
        self.assertEqual(self.process.wait(timeout=12), 0)
        self.assertFalse(s.tcp_open(self.root))
        self.assertFalse((self.root / '.run/control.sock').exists())

    def test_manual_console_stop_is_never_restarted(self):
        self.start()
        s.request(self.root, 'command', command='stop')
        self.assertEqual(self.process.wait(timeout=12), 0)
        log = (self.root / 'logs/engine.log').read_text()
        self.assertEqual(log.count('Iniciando Java 8'), 1)

    def test_live_backup_restarts_only_after_offline_snapshot(self):
        self.start()
        before = s.request(self.root, 'status')['java_pid']
        archive = s.request(self.root, 'backup')
        self.assertTrue(Path(archive).exists())
        self.wait_state(lambda st: st['state'] == 'online' and st['java_pid'] != before)
        with tarfile.open(archive) as tar:
            meta = json.load(tar.extractfile('smart-backup.json'))
            self.assertEqual(meta['consistent'], 'java-stopped')
            self.assertIn('world/saved-marker', tar.getnames())

    def test_stop_during_backup_prevents_restart(self):
        self.start('--slow-backup')
        result = []
        thread = threading.Thread(target=lambda: result.append(s.request(self.root, 'backup')))
        thread.start()
        self.wait_state(lambda st: st['state'] == 'backup offline')
        s.request(self.root, 'stop')
        thread.join(timeout=15)
        self.assertEqual(len(result), 1)
        self.assertEqual(self.process.wait(timeout=15), 0)
        self.assertEqual((self.root / 'logs/engine.log').read_text().count('Iniciando Java 8'), 1)

    def test_crash_recovers_but_budget_is_finite(self):
        self.start()
        for attempt in range(3):
            old = s.request(self.root, 'status')['java_pid']
            s.request(self.root, 'command', command='crash')
            if attempt < 2:
                self.wait_state(lambda st: st['state'] == 'online' and st['java_pid'] != old)
        self.assertEqual(self.process.wait(timeout=15), 1)
        log = (self.root / 'logs/engine.log').read_text()
        self.assertIn('Limite de reinícios atingido', log)
        self.assertEqual(log.count('Iniciando Java 8'), 3)

    def test_recovery_can_be_disabled(self):
        with open(self.root / 'config/maintenance.conf', 'a') as out:
            out.write('\nAUTO_RECOVERY=false\n')
        self.start()
        s.request(self.root, 'command', command='crash')
        self.assertEqual(self.process.wait(timeout=12), 1)
        self.assertEqual((self.root / 'logs/engine.log').read_text().count('Iniciando Java 8'), 1)

    def test_signal_stops_without_restart(self):
        self.start()
        self.process.terminate()
        self.assertEqual(self.process.wait(timeout=12), 0)
        self.assertFalse(s.tcp_open(self.root))

    def test_engine_reserves_save_controls(self):
        self.start()
        with self.assertRaises(s.SmartError):
            s.request(self.root, 'command', command='save-off')
        result = s.request(self.root, 'audit-items')
        self.assertIn('Nenhum item', result)

if __name__ == '__main__':
    unittest.main(verbosity=2)
