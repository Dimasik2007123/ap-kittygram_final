# Финальный проект: Kittygram в контейнерах

## Запуск Kittygram

Скопируйте `.env.example` в `.env` и задайте собственные значения:

- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` — имя базы, пользователь и пароль PostgreSQL;
- `DB_HOST` и `DB_PORT` — адрес и порт базы внутри Compose (для этого проекта `db` и `5432`);
- `SECRET_KEY` — секретный ключ Django;
- `DEBUG` — режим отладки Django, для запуска в контейнерах установите `False`.

Сборка и запуск локальных образов:

```bash
docker compose up -d --build
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py collectstatic --noinput
```

Kittygram доступен на http://localhost:8001/, Taski — на http://localhost:8000/.
Данные базы и загруженные изображения хранятся в отдельных Docker volumes.

## Публикация и обновление

В настройках GitHub Actions добавьте секреты `DOCKER_USERNAME` и
`DOCKER_PASSWORD` с логином и токеном Docker Hub. После успешных тестов
push в ветку `main` собирает и публикует три образа Kittygram.
В `docker-compose.production.yml` замените `your-dockerhub-login` на свой
логин Docker Hub. После публикации образов запустите или обновите проект:

```bash
docker compose -f docker-compose.production.yml pull
docker compose -f docker-compose.production.yml up -d
docker compose -f docker-compose.production.yml exec backend python manage.py migrate
docker compose -f docker-compose.production.yml exec backend python manage.py collectstatic --noinput
```

Для автопроверок скопируйте `tests.yml.example` в `tests.yml` и укажите свои
логины GitHub и Docker Hub. Локальные проверки приложения требуют отдельно
запущенного Taski. Проверки Docker Hub требуют опубликованных образов.

Результаты проверки в текущем окружении: синтаксис обоих Compose-файлов проверен,
13 проверок файлов и конфигурации и один тест Django прошли. Тест фронтенда не
запущен из-за отсутствия зависимостей в проекте. Запуск контейнеров и публикация
образов не проверены: доступ к Docker Engine отсутствует. GitHub Actions требует
настроенных секретов и запуска в собственном репозитории.

Это стартовый репозиторий, а не готовое решение. Настройте Dockerfile бэкенда,
Nginx, базу данных, volumes, Compose и GitHub Actions по заданию курса.

## Новый формат задания

- Taski работает на `http://localhost:8000/`, Kittygram — на `http://localhost:8001/`.
- У каждого проекта собственный gateway; публикуйте его порт только на
  `127.0.0.1`. Базу данных и backend на хост публиковать не нужно.
- В Django разрешите хосты `localhost` и `127.0.0.1`.
- GitHub Actions проверяет приложения, собирает и публикует три образа:
  `username/kittygram_backend`, `username/kittygram_frontend`,
  `username/kittygram_gateway`. После публикации обновите контейнеры локально.
- В `docker-compose.production.yml` используйте `image`, а не `build`.
- Домен, HTTPS, SSH-ключ, общий публичный IP, Telegram-уведомление о деплое
  и `EDU_PROVISIONING_ID` не требуются. Удалённый CD — только теория.

## Подготовка автотестов

Используйте Python 3.10 или новее. Из корня репозитория:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r tests/requirements.txt
cp tests.yml.example tests.yml
```

В PowerShell активируйте окружение командой `.venv\Scripts\Activate.ps1`.
В `tests.yml` замените логины GitHub и Docker Hub на свои, оставьте локальные
адреса или укажите свои порты. Названия `kittygram_domain` и `taski_domain`
сохранены для совместимости, но теперь это локальные HTTP-адреса.
YAML-комментарии и кавычки поддерживаются. Данные доступа и секреты не нужны.

Скопируйте актуальный `.github/workflows/main.yml` в `kittygram_workflow.yml`.
Оба файла должны описывать один и тот же workflow.

## Три группы проверок

**Файлы и конфигурация, без запущенных приложений и без сети:**

```bash
python -m pytest -m "not local and not dockerhub"
```

Эту группу можно запускать в GitHub Actions. Она не заменяет тесты приложений.
Для тестов Django установите `backend/requirements.txt` и из `backend/`
запустите `python manage.py test`. Тесты фронтенда запускаются отдельно
командой `CI=true npm test -- --watchAll=false` из `frontend/` после `npm ci`.

**Работа запущенных приложений, на компьютере студента:**

```bash
python -m pytest -m local
```

Сначала запустите оба проекта в контейнерах, выполните миграции и collectstatic.
Проверяются фронтенды обоих проектов, JS и CSS админки Kittygram и его API.
Запускайте pytest в той же ОС, где доступны эти localhost-адреса.
В WSL/виртуальной машине localhost относится к этому окружению.
Облачный раннер GitHub Actions не видит контейнеры на вашем компьютере:
не запускайте там группу `local` без отдельного развёртывания приложений на раннере.

**Публичные репозитории Docker Hub, после публикации образов:**

```bash
python -m pytest -m dockerhub
```

Эта проверка обращается к Docker Hub через интернет. Не запускайте её до
первой публикации образов. Сетевая ошибка или лимит Docker Hub не означает
ошибку локального приложения: проверьте сообщение и повторите позже.

**Полная проверка:** `python -m pytest` — запускает все три группы, ничего
не пропускает автоматически. Для неё нужны готовые файлы, оба работающих
локальных проекта и опубликованные образы. Пустой стартовый шаблон не должен
проходить эти проверки до выполнения задания.

## Что проверить вручную

Регистрация, вход, создание и редактирование котика, загрузка картинки;
сохранность данных и медиа после `docker compose -f docker-compose.production.yml restart`;
обновление из опубликованных образов. Не удаляйте volumes при проверке сохранности.
В README своего решения опишите переменные окружения без значений секретов,
команды запуска и обновления, локальные адреса и результаты проверки.
Автотесты не подтверждают сохранность данных, сборку образов и успешность
GitHub Actions: эти результаты нужно проверить отдельно.

## Для сопровождающих курса

Регрессионные тесты самой проверяющей системы запускаются командой
`python -m pytest checker_tests/`. Они используют временные конфигурации,
контрольные HTTP-серверы только на loopback и подменяют обращения к Docker Hub.
Это проверка автотестов, а не доказательство работоспособности Docker-проекта.
При переносе проверок в платформу задайте подходящую группу: облачный
проверяющий процесс не может обращаться к localhost компьютера студента.
