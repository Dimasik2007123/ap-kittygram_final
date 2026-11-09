from html.parser import HTMLParser
from http import HTTPStatus
from urllib.parse import urljoin, urlsplit

import pytest
import requests

from tests.checks import validated_local_url


pytestmark = pytest.mark.local


class ScriptParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.sources = []

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            source = dict(attrs).get('src')
            if source:
                self.sources.append(source)


def make_request(method, url, **kwargs):
    try:
        with requests.Session() as session:
            session.trust_env = False
            response = session.request(method, url, timeout=15, allow_redirects=False, **kwargs)
    except requests.RequestException as error:
        raise AssertionError(
            f'Нет ответа от `{url}`. Запустите локальные контейнеры '
            f'и запускайте проверки на том же компьютере. Ошибка: {error}'
        )
    return response


def get_ok(url):
    response = make_request('GET', url)
    assert response.status_code == HTTPStatus.OK, (
        f'GET `{url}` должен возвращать 200, получен {response.status_code}.'
    )
    return response


def get_scripts(link, response):
    parser = ScriptParser()
    parser.feed(response.text)
    links = [urljoin(link + '/', source) for source in parser.sources]
    links = [source for source in links if urlsplit(source).path.endswith('.js')]
    assert links, f'В HTML `{link}` не найдены ссылки на JavaScript.'
    expected = urlsplit(link)
    for source in links:
        actual = urlsplit(source)
        assert (actual.scheme, actual.netloc) == (expected.scheme, expected.netloc), (
            'JavaScript приложения должен раздаваться его локальным gateway.'
        )
    return links


def test_link_connection(deploy_info_file_content, link_key):
    link = validated_local_url(deploy_info_file_content, link_key)
    response = get_ok(link)
    project = 'Kittygram' if link_key == 'kittygram_domain' else 'Taski'
    scripts = [get_ok(source) for source in get_scripts(link, response)]
    assert project in response.text or any(project in script.text for script in scripts), (
        f'По адресу `{link}` должен работать проект {project}.'
    )


def test_kittygram_static_is_available(deploy_info_file_content):
    link = validated_local_url(deploy_info_file_content, 'kittygram_domain')
    for source in get_scripts(link, get_ok(link)):
        response = get_ok(source)
        content_type = response.headers.get('Content-Type', '').lower()
        assert 'javascript' in content_type or 'ecmascript' in content_type, (
            'Вместо JavaScript возвращается другой документ. Проверьте статику Nginx.'
        )


def test_kittygram_admin_static_is_available(deploy_info_file_content):
    link = validated_local_url(deploy_info_file_content, 'kittygram_domain')
    response = get_ok(f'{link}/static/admin/css/base.css')
    assert 'text/css' in response.headers.get('Content-Type', '').lower(), (
        'Проверьте collectstatic и раздачу CSS админки через Nginx.'
    )


def test_kittygram_api_available(deploy_info_file_content):
    link = validated_local_url(deploy_info_file_content, 'kittygram_domain')
    response = make_request('POST', f'{link}/api/users/', data={'username': 'newuser', 'password': ''})
    assert response.status_code == HTTPStatus.BAD_REQUEST, (
        'POST /api/users/ с пустым паролем должен возвращать 400.'
    )
    try:
        response_data = response.json()
    except ValueError:
        raise AssertionError('API должен возвращать JSON, а не HTML фронтенда.')
    assert isinstance(response_data, dict) and 'password' in response_data, (
        'API должен сообщать об ошибке в поле password.'
    )
