#!/usr/bin/env python3
"""Deterministic TEST FIXTURE, not Minecraft and never used by production launchers."""
from pathlib import Path
import os
import socket
import sys
import threading

cfg = dict(line.split('=', 1) for line in Path('server.properties').read_text().splitlines() if '=' in line and not line.startswith('#'))
world = Path(cfg.get('level-name', 'world'))
world.mkdir(exist_ok=True)
(world / 'level.dat').write_text('FAKE TEST WORLD\n')
server = socket.socket()
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(('127.0.0.1', int(cfg['server-port'])))
server.listen()

def accept():
    while True:
        try:
            client, _ = server.accept()
            client.close()
        except OSError:
            return

threading.Thread(target=accept, daemon=True).start()
print('TEST FIXTURE: not a Minecraft server', flush=True)
print('Starting minecraft server version 1.12.2', flush=True)
print('Done (0.1s)! For help, type "help" or "?"', flush=True)
for line in sys.stdin:
    cmd = line.strip()
    if cmd == 'save-all flush':
        (world / 'saved-marker').write_text('saved')
        print('Flushed all saves', flush=True)
    elif cmd == 'stop':
        print('Stopping server', flush=True)
        break
    elif cmd == 'crash':
        print('TEST: simulated OutOfMemoryError', flush=True)
        os._exit(23)
    else:
        print('TEST command: ' + cmd, flush=True)
server.close()
