#!/usr/bin/env python3
"""Official JAR test. A world is started ONLY with the explicit --accept-eula flag."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time

CODE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('smart', CODE / 'scripts/smart.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


def varint(value):
    out = bytearray()
    while True:
        byte = value & 127
        value >>= 7
        out.append(byte | (128 if value else 0))
        if not value:
            return bytes(out)


def read_int(sock):
    result = 0
    for pos in range(5):
        b = sock.recv(1)
        if not b:
            raise RuntimeError('Conexão fechou durante varint')
        result |= (b[0] & 127) << (7 * pos)
        if not b[0] & 128:
            return result
    raise RuntimeError('Varint inválido')


def status_packet(port):
    host = b'localhost'
    packet = b'\x00' + varint(340) + varint(len(host)) + host + struct.pack('>H', port) + b'\x01'
    with socket.create_connection(('127.0.0.1', port), timeout=10) as client:
        client.sendall(varint(len(packet)) + packet + b'\x01\x00')
        size = read_int(client)
        assert 0 < size < 1024 * 1024
        assert read_int(client) == 0
        length = read_int(client)
        assert 0 < length < 1024 * 1024
        data = b''
        while len(data) < length:
            chunk = client.recv(length - len(data))
            if not chunk:
                raise RuntimeError('Resposta de status incompleta')
            data += chunk
        return json.loads(data)


def wait_online(root, process, previous=None):
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f'Engine encerrou: {process.returncode}')
        try:
            data = s.request(root, 'status')
            if data['state'] == 'online' and data['tcp_local'] and data['java_pid'] != previous:
                return data
        except (s.SmartError, OSError):
            pass
        time.sleep(1)
    raise RuntimeError('Servidor não ficou pronto em 240 segundos')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--accept-eula', action='store_true')
    parser.add_argument('--minutes', type=int, default=0)
    args = parser.parse_args()
    assert 0 <= args.minutes <= 15
    assert s.digest(CODE / 'server.jar', 'sha1') == s.SERVER_SHA1
    java = s.find_java(CODE)
    (CODE / 'logs').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='sv-real-') as temp:
        root = Path(temp)
        shutil.copy(CODE / 'server.properties', root / 'server.properties')
        shutil.copytree(CODE / 'config', root / 'config')
        s.prepare(root)
        shutil.copy(CODE / 'server.jar', root / 'server.jar')
        # The Java selected by setup-java/installer remains discoverable in the child.
        import os
        env = {**os.environ, 'SMART_JAVA': java}
        sock = socket.socket()
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
        sock.close()
        p = root / 'server.properties'
        p.write_text(p.read_text().replace('server-port=25565', f'server-port={port}')
                     .replace('server-ip=\n', 'server-ip=127.0.0.1\n').replace('view-distance=6', 'view-distance=3'))
        if not args.accept_eula:
            (root / 'eula.txt').write_text('eula=false\n')
            result = subprocess.run([java, '-Xms128M', '-Xmx512M', '-jar', str(root / 'server.jar'), 'nogui'],
                                    cwd=root, capture_output=True, text=True, timeout=90, env=env)
            output = result.stdout + result.stderr
            (CODE / 'logs/ci-real-pre-eula.log').write_text(output)
            assert 'You need to agree to the EULA' in output, output
            assert not (root / 'world/level.dat').exists()
            print('JAR oficial executou em Java 8 e respeitou eula=false. Nenhum mundo foi iniciado.')
            return
        s.ensure_eula(root, True)
        with open(root / 'config/maintenance.conf', 'a') as out:
            out.write('\nBACKUP_WARNING_SECONDS=0\n')
        (root / 'config/backup.conf').write_text('BACKUP_INTERVAL_SECONDS=0\nBACKUP_ON_STOP=false\nKEEP_BACKUPS=3\n')
        process = None
        try:
            with open(CODE / 'logs/ci-real-session.log', 'w') as log:
                process = subprocess.Popen([sys.executable, str(CODE / 'scripts/smart.py'), '--root', str(root), 'run'], stdout=log, stderr=subprocess.STDOUT, env=env)
                state = wait_online(root, process)
                response = status_packet(port)
                assert response['version']['protocol'] == 340, response
                assert response['version']['name'] == '1.12.2', response
                print('Minecraft Java 1.12.2 real confirmado pelo protocolo 340.', flush=True)
                s.request(root, 'save')
                deadline = time.monotonic() + args.minutes * 60
                while time.monotonic() < deadline:
                    time.sleep(min(10, deadline - time.monotonic()))
                    current = s.request(root, 'status')
                    assert current['state'] == 'online'
                    print(json.dumps(current, ensure_ascii=False), flush=True)
                archive = s.request(root, 'backup')
                wait_online(root, process, previous=state['java_pid'])
                s.request(root, 'stop')
                assert process.wait(timeout=180) == 0
                (root / 'world/post-backup-marker').write_text('previous-world')
                s.restore(root, archive, True)
                assert not (root / 'world/post-backup-marker').exists()
                assert (root / 'world/level.dat').exists()
                print('Save, stop, backup offline, reinício e restauração do mundo real: OK.', flush=True)
                shutil.copy(archive, CODE / 'logs' / Path(archive).name)
                shutil.copy(archive + '.sha256', CODE / 'logs' / (Path(archive).name + '.sha256'))
        finally:
            if process and process.poll() is None:
                try:
                    s.request(root, 'stop')
                    process.wait(timeout=180)
                except Exception:
                    process.terminate()
                    process.wait(timeout=180)
            if (root / 'logs').exists():
                shutil.copytree(root / 'logs', CODE / 'logs/ci-real-engine', dirs_exist_ok=True)

if __name__ == '__main__':
    main()
