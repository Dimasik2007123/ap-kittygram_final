import importlib
import json
import shutil
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
import requests


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.checks import load_yaml_mapping, published_ports, validated_local_url


files = importlib.import_module('tests.test_files')
connection = importlib.import_module('tests.test_connection')
dockerhub = importlib.import_module('tests.test_dockerhub_images')


@pytest.mark.parametrize('url', [
    'http://localhost:8001/', 'http://127.0.0.1:8001', 'http://[::1]:8001/',
])
def test_local_addresses_accepted(url):
    assert validated_local_url({'url': url}, 'url') == url.rstrip('/')


@pytest.mark.parametrize('url', [
    'https://localhost:8001', 'http://example.com:8001',
    'http://localhost', 'http://localhost:0', 'http://localhost:65536',
    'http://localhost:abc', 'http://localhost:8001/path',
    'http://localhost:8001/?x=1', 'http://localhost:8001/#fragment',
    'http://user:password@localhost:8001', ' http://localhost:8001',
    'http://127.0.0.1.example.com:8001', None, 8001, '',
])
def test_nonlocal_or_invalid_addresses_rejected(url):
    with pytest.raises(AssertionError):
        validated_local_url({'url': url}, 'url')


def test_yaml_quotes_and_comments(tmp_path):
    path = tmp_path / 'tests.yml'
    path.write_text('# Локальная проверка\nkittygram_domain: "http://localhost:8001/"\n')
    assert load_yaml_mapping(path)['kittygram_domain'] == 'http://localhost:8001/'


@pytest.mark.parametrize('text', ['', '- item', '[]', 'value: ['])
def test_invalid_yaml_rejected(tmp_path, text):
    path = tmp_path / 'tests.yml'
    path.write_text(text)
    with pytest.raises(AssertionError):
        load_yaml_mapping(path)


@pytest.mark.parametrize('binding', [
    '127.0.0.1:8001:80', '127.0.0.1:8001:80/tcp',
    {'host_ip': '127.0.0.1', 'published': '8001', 'target': 80},
    '[::1]:8001:80',
])
def test_loopback_bindings_accepted(binding):
    assert published_ports({'ports': [binding]})[0][1:] == (8001, 80)


@pytest.mark.parametrize('binding', [
    '8001:80', '0.0.0.0:8001:80', '127.0.0.1:8001:80/udp',
    '127.0.0.1:8001', {'published': 8001, 'target': 80},
    {'host_ip': '127.0.0.1', 'target': 80},
])
def test_public_or_invalid_bindings_rejected(binding):
    with pytest.raises(AssertionError):
        published_ports({'ports': [binding]})


@pytest.fixture
def student_solution(tmp_path):
    for directory in ['backend', 'frontend', 'nginx', '.github/workflows']:
        (tmp_path / directory).mkdir(parents=True)
    for directory in ['backend', 'frontend', 'nginx']:
        (tmp_path / directory / 'Dockerfile').write_text(
            'FROM python:3.11\nRUN echo validation-fixture\nCMD ["true"]\n'
        )
    (tmp_path / 'nginx/nginx.conf').write_text('server {}\n')
    (tmp_path / 'backend/requirements.txt').write_text('Django==5.1.1\n')
    workflow = 'name: test\non: push\njobs:\n  tests:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo validation-fixture\n'
    (tmp_path / 'kittygram_workflow.yml').write_text(workflow)
    (tmp_path / '.github/workflows/main.yml').write_text(workflow)
    services = {
        name: {'image': f'student/kittygram_{name}'}
        for name in ['backend', 'frontend', 'gateway']
    }
    services['gateway']['ports'] = ['127.0.0.1:8001:80']
    services['db'] = {'image': 'postgres:13'}
    compose = {'services': services}
    (tmp_path / 'docker-compose.production.yml').write_text(json.dumps(compose))
    config = {
        'repo_owner': 'student', 'dockerhub_username': 'student',
        'kittygram_domain': 'http://localhost:8001/',
        'taski_domain': 'http://localhost:8000/',
    }
    return tmp_path, config, compose


def test_offline_suite_accepts_local_configuration_without_server_id(student_solution):
    root, config, _ = student_solution
    for relative in ['backend', 'frontend', 'nginx', 'nginx/nginx.conf', 'backend/requirements.txt']:
        files.test_project_structure(root, relative)
    for directory in ['backend', 'frontend', 'nginx']:
        files.test_dockerfile_content(root, directory)
    files.test_tests_yml_values(config)
    files.test_local_urls(config)
    files.test_workflow_file(root)
    files.test_compose_uses_published_images(root, config)
    files.test_compose_local_ports(root, config)


def test_pytest_collection_and_offline_mode(student_solution):
    root, config, _ = student_solution
    source = Path(__file__).resolve().parents[1]
    shutil.copytree(source / 'tests', root / 'tests', ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copyfile(source / 'pytest.ini', root / 'pytest.ini')
    (root / 'tests.yml').write_text(json.dumps(config))
    result = subprocess.run(
        [sys.executable, '-m', 'pytest', '-m', 'not local and not dockerhub',
         '-q', '--override-ini', 'addopts='],
        cwd=root, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert '13 passed, 8 deselected' in result.stdout


@pytest.mark.parametrize('fault', ['build', 'missing_image', 'wrong_image', 'public_port', 'db_port', 'host_network', 'wrong_port', 'no_gateway'])
def test_compose_regressions_rejected(student_solution, fault):
    root, config, compose = student_solution
    services = compose['services']
    if fault == 'build':
        services['backend']['build'] = './backend'
    elif fault == 'missing_image':
        del services['backend']['image']
    elif fault == 'wrong_image':
        services['backend']['image'] = 'other/kittygram_backend'
    elif fault == 'public_port':
        services['gateway']['ports'] = ['8001:80']
    elif fault == 'db_port':
        services['db']['ports'] = ['5432:5432']
    elif fault == 'host_network':
        services['backend']['network_mode'] = 'host'
    elif fault == 'wrong_port':
        services['gateway']['ports'] = ['127.0.0.1:9000:80']
    else:
        del services['gateway']
    (root / 'docker-compose.production.yml').write_text(json.dumps(compose))
    with pytest.raises(AssertionError):
        files.test_compose_uses_published_images(root, config)
        files.test_compose_local_ports(root, config)


def test_same_ports_rejected(student_solution):
    _, config, _ = student_solution
    config['taski_domain'] = config['kittygram_domain']
    with pytest.raises(AssertionError):
        files.test_local_urls(config)


def test_stale_workflow_copy_rejected(student_solution):
    root, _, _ = student_solution
    (root / '.github/workflows/main.yml').write_text('jobs: {}\n')
    with pytest.raises(AssertionError):
        files.test_workflow_file(root)


@pytest.fixture
def local_apps():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/':
                body = '<title>Kittygram</title><script src="/static/js/main.js"></script>'
                content_type = 'text/html'
            elif self.path == '/static/js/main.js':
                body, content_type = 'Taski Kittygram', self.server.script_type
            elif self.path == '/static/admin/css/base.css':
                body, content_type = 'body {}', 'text/css'
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.end_headers()
            self.wfile.write(body.encode())

        def do_POST(self):
            self.rfile.read(int(self.headers.get('Content-Length', 0)))
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"password": ["This field may not be blank."]}')

        def log_message(self, *args):
            pass

    servers = [ThreadingHTTPServer(('127.0.0.1', 0), Handler) for _ in range(2)]
    threads = []
    for server in servers:
        server.script_type = 'application/javascript'
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        threads.append(thread)
    config = dict(zip(
        ['kittygram_domain', 'taski_domain'],
        [f'http://127.0.0.1:{server.server_port}/' for server in servers],
    ))
    try:
        yield config, servers
    finally:
        for server, thread in zip(servers, threads):
            server.shutdown()
            server.server_close()
            thread.join()


def test_local_http_checks_with_controlled_servers(local_apps):
    config, _ = local_apps
    for key in ['kittygram_domain', 'taski_domain']:
        connection.test_link_connection(config, key)
    connection.test_kittygram_static_is_available(config)
    connection.test_kittygram_admin_static_is_available(config)
    connection.test_kittygram_api_available(config)


def test_spa_html_instead_of_javascript_rejected(local_apps):
    config, servers = local_apps
    servers[0].script_type = 'text/html'
    with pytest.raises(AssertionError, match='JavaScript'):
        connection.test_kittygram_static_is_available(config)


def test_timeouts_have_actionable_error(monkeypatch):
    def timeout(*args, **kwargs):
        raise requests.Timeout('test timeout')
    monkeypatch.setattr(requests.Session, 'request', timeout)
    with pytest.raises(AssertionError, match='Запустите локальные контейнеры'):
        connection.make_request('GET', 'http://localhost:8001/')


def test_dockerhub_checks_are_mocked_not_external_requests(monkeypatch):
    seen = []

    def response(url, **kwargs):
        seen.append((url, kwargs))
        result = requests.Response()
        result.status_code = 200
        return result

    monkeypatch.setattr(requests, 'get', response)
    for image in ['kittygram_backend', 'kittygram_frontend', 'kittygram_gateway']:
        dockerhub.test_dockerhub_images_exist({'dockerhub_username': 'student'}, image)
    assert len(seen) == 3
    assert all(options['timeout'] == 15 for _, options in seen)
