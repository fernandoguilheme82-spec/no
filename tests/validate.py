#!/usr/bin/env python3
"""Repository checks; PyYAML is a CI/test-only dependency."""
from pathlib import Path
import ast
import subprocess
import yaml

root = Path(__file__).resolve().parents[1]
required = ['README.md', 'LICENSE', '.gitignore', 'server.properties', 'install-termux.sh',
            'start-termux.sh', 'stop-server.sh', 'install-linux.sh', 'start-linux.sh',
            'backup.sh', 'restore-backup.sh', 'status.sh', 'smart-engine.sh', 'console.sh',
            'config/memory.conf', 'config/maintenance.conf', 'config/backup.conf',
            'scripts/download-server.sh', 'scripts/check-java.sh', 'scripts/monitor.sh',
            'scripts/safe-restart.sh', 'scripts/health-check.sh', 'scripts/smart.py',
            'systemd/minecraft.service', 'docs/TERMUX.md', 'docs/GITHUB-ACTIONS.md',
            'docs/SELF-HOSTED.md', 'docs/MULTIPLAYER.md', 'docs/TROUBLESHOOTING.md',
            '.github/workflows/minecraft-server.yml', '.github/workflows/self-hosted-server.yml',
            '.github/workflows/validate.yml']
for name in required:
    assert (root / name).is_file(), name
for path in [*root.glob('*.sh'), *root.glob('scripts/*.sh')]:
    subprocess.run(['bash', '-n', str(path)], check=True)
for path in [*root.glob('scripts/*.py'), *root.glob('tests/*.py')]:
    ast.parse(path.read_text(), filename=str(path))
for path in root.glob('.github/workflows/*.yml'):
    data = yaml.load(path.read_text(), Loader=yaml.BaseLoader)
    assert 'on' in data and 'jobs' in data, path
    assert data.get('permissions') == {'contents': 'read'}, path
    for job in data['jobs'].values():
        assert 1 <= int(job['timeout-minutes']) <= 360, path
        for step in job.get('steps', []):
            if 'uses' in step:
                assert len(step['uses'].split('@')[-1]) == 40, 'Actions must be pinned to commit SHAs'
server = (root / 'server.properties').read_text()
assert 'enable-rcon=false' in server and 'online-mode=true' in server
assert not list(root.glob('*.jar')), 'Do not commit/distribute the Minecraft JAR'
assert not (root / 'mods').exists() and not (root / 'plugins').exists()
print(f'Estrutura ({len(required)} arquivos obrigatórios), Bash, Python e YAML: OK')
