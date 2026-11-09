import re
from pathlib import Path
from urllib.parse import urlsplit

import yaml


def load_yaml_mapping(path: Path) -> dict:
    assert path.is_file(), f'Создайте файл `{path.name}`.'
    try:
        content = yaml.safe_load(path.read_text(encoding='utf-8'))
    except (yaml.YAMLError, UnicodeError) as error:
        raise AssertionError(f'Проверьте YAML-синтаксис `{path.name}`: {error}')
    assert isinstance(content, dict) and content, (
        f'Файл `{path.name}` должен содержать непустой YAML-словарь.'
    )
    return content


def validated_local_url(content: dict, key: str) -> str:
    value = content.get(key)
    assert isinstance(value, str) and value.strip(), (
        f'Укажите непустую строку `{key}` в `tests.yml`.'
    )
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        raise AssertionError(f'Некорректный локальный URL в `{key}`.')
    assert (
        parsed.scheme == 'http'
        and parsed.hostname in {'localhost', '127.0.0.1', '::1'}
        and port is not None
        and 1 <= port <= 65535
        and parsed.username is None
        and parsed.password is None
        and parsed.path in {'', '/'}
        and not parsed.query
        and not parsed.fragment
        and value == value.strip()
        and not any(character.isspace() for character in value)
    ), (
        f'В `{key}` нужен локальный HTTP-адрес с портом, например '
        '`http://localhost:8001/`. Домен, HTTPS и удалённый сервер не нужны.'
    )
    return value.rstrip('/')


def validate_image_name(image: str, username: str, repository: str) -> None:
    assert isinstance(image, str) and re.fullmatch(
        re.escape(f'{username}/{repository}') + r'(?::[\w.-]+|@sha256:[a-f0-9]{64})?',
        image,
    ), f'Укажите образ `{username}/{repository}` с Docker Hub.'


def published_ports(service: dict) -> list[tuple[str, int, int]]:
    ports = service.get('ports', [])
    assert isinstance(ports, list), 'Параметр `ports` должен быть списком.'
    result = []
    for binding in ports:
        try:
            if isinstance(binding, dict):
                host = binding.get('host_ip', '')
                published = int(binding['published'])
                target = int(binding['target'])
                protocol = binding.get('protocol', 'tcp')
            else:
                address, separator, protocol = str(binding).partition('/')
                protocol = protocol if separator else 'tcp'
                host, published, target = address.rsplit(':', 2)
                host = host.strip('[]')
                published, target = int(published), int(target)
            assert protocol == 'tcp'
            assert host in {'127.0.0.1', '::1'}
            assert 1 <= published <= 65535 and 1 <= target <= 65535
        except (KeyError, TypeError, ValueError, AssertionError):
            raise AssertionError(
                'Публикуйте TCP-порт только на loopback-интерфейсе: '
                '`127.0.0.1:8001:80` или эквивалентная длинная форма Compose.'
            )
        result.append((host, published, target))
    return result
