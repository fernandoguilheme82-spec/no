#!/usr/bin/env python3
"""Explicit test-only subclass; production cannot select this via configuration."""
import importlib.util
from pathlib import Path
import sys
import time

code = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('smart', code / 'scripts/smart.py')
smart = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smart)

class TestSupervisor(smart.Supervisor):
    def launch_command(self):
        return [sys.executable, str(code / 'tests/fake_server.py')]

root = Path(sys.argv[1])
smart.prepare(root)
if '--slow-backup' in sys.argv:
    original = smart.backup_offline
    def slow_backup(*args, **kwargs):
        time.sleep(2)
        return original(*args, **kwargs)
    smart.backup_offline = slow_backup
sys.exit(TestSupervisor(root).run())
