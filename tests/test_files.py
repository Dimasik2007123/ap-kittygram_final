import re
from urllib.parse import urlsplit

import pytest

from tests.checks import (
    load_yaml_mapping,
    published_ports,
    validate_image_name,
    validated_local_url,
)


@pytest.mark.parametrize('relative_path', [
    'backend', 'frontend', 'nginx', 'nginx/nginx.conf',
    'backend/requirements.txt',
])
def test_project_structure(base_dir, relative_path):
    path = base_dir / relative_path
    assert path.is_dir() if '.' not in path.name else path.is_file(), (
        f'Восстановите `{relative_path}` в структуре проекта.'
    )


@pytest.mark.parametrize('directory', ['backend', 'frontend', 'nginx'])
def test_dockerfile_content(base_dir, directory):
    path = base_dir / directory / 'Dockerfile'
    assert path.is_file(), f'Создайте `{directory}/Dockerfile`.'
    instructions = set(re.findall(
        r'^\s*([A-Za-z]+)\s+', path.read_text(encoding='utf-8'), re.M,
    ))
    instructions = {instruction.upper() for instruction in instructions}
    assert 'FROM' in instructions, f'В `{directory}/Dockerfile` нужен FROM.'
    if directory == 'backend':
        assert 'RUN' in instructions, 'Установите зависимости в образ бэкенда.'
        assert instructions & {'CMD', 'ENTRYPOINT'}, (
            'Настройте запуск бэкенда через CMD или ENTRYPOINT.'
        )


def test_tests_yml_values(deploy_info_file_content):
    for key in ['repo_owner', 'dockerhub_username']:
        value = deploy_info_file_content.get(key)
        assert isinstance(value, str) and re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]*', value), (
            f'Укажите свой логин в `{key}` файла `tests.yml`.'
        )


def test_local_urls(deploy_info_file_content):
    kittygram = validated_local_url(deploy_info_file_content, 'kittygram_domain')
    taski = validated_local_url(deploy_info_file_content, 'taski_domain')
    assert urlsplit(kittygram).port != urlsplit(taski).port, (
        'Taski и Kittygram должны использовать разные порты компьютера.'
    )


def test_workflow_file(base_dir):
    workflow = load_yaml_mapping(base_dir / 'kittygram_workflow.yml')
    jobs = workflow.get('jobs')
    assert isinstance(jobs, dict) and jobs, 'Опишите jobs в workflow Kittygram.'
    original = load_yaml_mapping(base_dir / '.github/workflows/main.yml')
    assert workflow == original, (
        'Обновите `kittygram_workflow.yml`: он должен совпадать с '
        '`.github/workflows/main.yml`.'
    )


def test_compose_uses_published_images(base_dir, deploy_info_file_content):
    compose = load_yaml_mapping(base_dir / 'docker-compose.production.yml')
    services = compose.get('services')
    assert isinstance(services, dict), 'Опишите services в production Compose.'
    assert {'db', 'backend', 'frontend', 'gateway'} <= services.keys(), (
        'Нужны сервисы db, backend, frontend и gateway.'
    )
    username = deploy_info_file_content.get('dockerhub_username')
    for name, service in services.items():
        assert isinstance(service, dict), f'Проверьте сервис `{name}`.'
        assert 'build' not in service, 'Production Compose использует image, не build.'
        assert service.get('network_mode') != 'host', 'Не используйте сеть host.'
        if name in {'backend', 'frontend', 'gateway'}:
            validate_image_name(service.get('image'), username, f'kittygram_{name}')


def test_compose_local_ports(base_dir, deploy_info_file_content):
    compose = load_yaml_mapping(base_dir / 'docker-compose.production.yml')
    services = compose.get('services', {})
    assert isinstance(services, dict), 'Опишите services в production Compose.'
    gateway = services.get('gateway')
    assert isinstance(gateway, dict), 'Опишите сервис gateway.'
    port = urlsplit(validated_local_url(deploy_info_file_content, 'kittygram_domain')).port
    bindings = published_ports(gateway)
    assert any(published == port and target == 80 for _, published, target in bindings), (
        'Порт gateway должен вести на 80 контейнера и совпадать с tests.yml.'
    )
    for name, service in services.items():
        assert isinstance(service, dict), f'Проверьте сервис `{name}`.'
        if name != 'gateway':
            assert not service.get('ports'), (
                f'Сервис `{name}` должен быть доступен внутри Compose, без ports.'
            )
        assert service.get('network_mode') != 'host', 'Не используйте сеть host.'
