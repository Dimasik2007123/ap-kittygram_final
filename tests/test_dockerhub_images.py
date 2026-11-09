import re
from http import HTTPStatus

import pytest
import requests


pytestmark = pytest.mark.dockerhub


@pytest.mark.parametrize('image', [
    'kittygram_backend', 'kittygram_frontend', 'kittygram_gateway',
])
def test_dockerhub_images_exist(deploy_info_file_content, image):
    username = deploy_info_file_content.get('dockerhub_username')
    assert isinstance(username, str) and re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]*', username), (
        'Укажите логин Docker Hub в tests.yml.'
    )
    url = f'https://hub.docker.com/v2/namespaces/{username}/repositories/{image}/'
    try:
        response = requests.get(url, timeout=15)
    except requests.RequestException as error:
        raise AssertionError(f'Не удалось проверить Docker Hub: {error}')
    assert response.status_code == HTTPStatus.OK, (
        f'Образ `{username}/{image}` должен быть публичным на Docker Hub. '
        f'Получен статус {response.status_code}; при 429 повторите позже.'
    )
