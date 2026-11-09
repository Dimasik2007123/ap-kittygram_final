from pathlib import Path

import pytest

from tests.checks import load_yaml_mapping


BASE_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture(scope='session')
def base_dir() -> Path:
    return BASE_DIR


@pytest.fixture(scope='session')
def deploy_file_info(base_dir) -> tuple[Path, str]:
    path = base_dir / 'tests.yml'
    assert path.is_file(), 'Создайте `tests.yml` по образцу `tests.yml.example`.'
    return path, path.name


@pytest.fixture(scope='session')
def deploy_info_file_content(deploy_file_info) -> dict:
    return load_yaml_mapping(deploy_file_info[0])


@pytest.fixture(params=('taski_domain', 'kittygram_domain'))
def link_key(request) -> str:
    return request.param
