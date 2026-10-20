"""Run real-backend React DOM tests using an automatically isolated QA server."""

import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from urllib.error import URLError
from urllib.request import urlopen

import uvicorn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def node_runtime():
    node = shutil.which('node')
    if node:
        return Path(node)
    pointer = ROOT / '.tools' / 'node-path.txt'
    if pointer.is_file():
        folder = Path(pointer.read_text(encoding='utf-8-sig').strip())
        if not folder.is_dir():
            folder = ROOT / '.tools' / folder.name
        executable = folder / 'node.exe'
        if executable.is_file():
            return executable
    raise RuntimeError('Node.js is required. Run scripts/setup.ps1 first.')


def main():
    node = node_runtime()
    npm = node.parent / 'node_modules' / 'npm' / 'bin' / 'npm-cli.js'
    if not npm.is_file():
        raise RuntimeError(f'Could not locate npm next to {node}. Run setup first.')
    with tempfile.TemporaryDirectory(prefix='peerbridge-ui-') as temporary:
        with socket.socket() as port_socket:
            port_socket.bind(('127.0.0.1', 0))
            port = port_socket.getsockname()[1]
        qa_environment = {
            'PEERBRIDGE_DB': str(Path(temporary) / 'qa.sqlite3'),
            'PEERBRIDGE_TEST_MODE': '1',
            'PEERBRIDGE_TEST_URL': f'http://127.0.0.1:{port}',
        }
        original_environment = {key: os.environ.get(key) for key in qa_environment}
        os.environ.update(qa_environment)
        env = os.environ.copy()
        env['PATH'] = str(node.parent) + os.pathsep + env.get('PATH', '')
        # Serve HTTP in an owned thread, avoiding Windows venv redirector
        # processes and inherited file handles during temporary-data cleanup.
        server = uvicorn.Server(uvicorn.Config(
            'backend.peerbridge.main:app', host='127.0.0.1', port=port,
            log_level='warning', access_log=False,
        ))
        thread = threading.Thread(target=server.run, name='peerbridge-qa', daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                if not thread.is_alive():
                    raise RuntimeError('The isolated API server exited during startup.')
                try:
                    with urlopen(qa_environment['PEERBRIDGE_TEST_URL'] + '/api/health', timeout=2) as response:
                        health = json.load(response)
                    if health.get('qa_mode') is True:
                        print(f"Isolated UI tests: engine={health['matching_mode']}; temporary database; port={port}", flush=True)
                        break
                except (OSError, URLError, TimeoutError):
                    time.sleep(0.25)
            else:
                raise RuntimeError('The isolated API server did not become ready.')
            result = subprocess.run([str(node), str(npm), 'run', 'test'], cwd=ROOT / 'frontend', env=env)
            return result.returncode
        finally:
            server.should_exit = True
            thread.join(timeout=15)
            if thread.is_alive():
                server.force_exit = True
                thread.join(timeout=5)
            for key, value in original_environment.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            if thread.is_alive():
                raise RuntimeError('The owned QA server did not stop cleanly.')


if __name__ == '__main__':
    sys.exit(main())
