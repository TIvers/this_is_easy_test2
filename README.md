# Adrobot

Adrobot — приложение на FastAPI и SQLAlchemy для создания кампаний Keitaro и редактирования офферов в потоках существующих кампаний.

## Возможности

- Создаёт кампанию с потоком редиректа в Google для выбранной страны и резервным потоком с оффером.
- Загружает из Keitaro домены, группы кампаний, источники трафика и офферы.
- Показывает актуальные названия сохранённых кампаний и позволяет администраторам удалять кампании в Keitaro.
- Открывает любую существующую кампанию по её ID в Keitaro.
- Сохраняет изменения офферов, названия кампании и названий потоков (кроме первого) как локальные черновики. В Keitaro они отправляются только после явного подтверждения.
- Запрещает удалять и переименовывать первый поток, подсвечивает ожидающие подтверждения изменения жёлтым.
- Автоматически балансирует доли офферов до 100%, учитывая закреплённые доли и минимум 1% для каждого незакреплённого оффера.
- Показывает клики, конверсии, доход и CR для каждого оффера за выбранный период.

Удаление кампании безвозвратно удаляет её из Keitaro, а также очищает локальную запись и черновики редактора. Для операции требуется явное подтверждение в списке кампаний на главной странице.

## Требования

- Python 3.11 (рекомендуется; используйте стабильную версию Python).
- Экземпляр Keitaro и ключ Admin API с доступом к кампаниям, потокам, офферам и отчётам.

## Установка (Windows PowerShell)

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Укажите в `.env` адрес Keitaro в `KEITARO_URL` (без `/admin_api/v1`) и ключ Admin API. Никогда не добавляйте `.env` в репозиторий и не вставляйте действующий ключ в исходный код. При необходимости задайте ID домена, группы и источника по умолчанию; иначе выберите их в форме создания кампании.

## Вход администратора

В приложении используется одна учётная запись администратора, настройки которой хранятся вне исходного кода. Сгенерируйте хэш пароля Argon2:

```powershell
.\.venv\Scripts\python.exe -m app.password_hash
```

Укажите полученный хэш в `ADMIN_PASSWORD_HASH`, задайте `ADMIN_USERNAME` и сохраните постоянный случайный `SESSION_SECRET_KEY` в `.env`. Сгенерировать ключ сессии можно командой:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

Не храните обычный пароль администратора в `.env`. Сессии подписаны, используют HTTP-only cookie с SameSite=Lax и истекают через восемь часов. При работе через HTTPS задайте `SESSION_COOKIE_SECURE=true`; для локальной разработки по HTTP оставьте значение `false`.

## Миграции базы данных

Перед запуском приложения примените миграции:

```powershell
alembic upgrade head
```

Чтобы создать миграцию после изменения моделей SQLAlchemy:

```powershell
alembic revision --autogenerate -m "описание изменений"
alembic upgrade head
```

По умолчанию используется SQLite-база `./adrobot.db`. Чтобы использовать другую базу данных, укажите соответствующий SQLAlchemy URL в `DATABASE_URL`.

## Запуск

```powershell
uvicorn app.main:app --reload
```

Откройте <http://127.0.0.1:8000> и войдите в систему. Интерактивная документация API по адресу <http://127.0.0.1:8000/docs> также защищена авторизацией.

## Развёртывание на `adrobot.iversdev.ru` (Ubuntu + Nginx)

Ветка для развёртывания — `deploy/adrobot-nginx`. После коммита изменений отправьте её в настроенный удалённый репозиторий:

```powershell
git push -u origin deploy/adrobot-nginx
```

В репозитории находятся конфигурация обратного прокси `deploy/nginx/adrobot.iversdev.ru.conf` и unit-файл systemd `deploy/systemd/adrobot.service`. До развёртывания направьте DNS A-запись домена на публичный IP сервера и разрешите входящие подключения к портам 80 и 443.

На сервере Ubuntu выполните:

```bash
sudo apt update
sudo apt install -y git nginx certbot python3-certbot-nginx python3-venv
sudo adduser --system --group --home /opt/adrobot --shell /usr/sbin/nologin adrobot
sudo -u adrobot git clone -b deploy/adrobot-nginx <GIT_REPOSITORY_URL> /opt/adrobot
sudo -u adrobot python3 -m venv /opt/adrobot/.venv
sudo -u adrobot /opt/adrobot/.venv/bin/pip install -r /opt/adrobot/requirements.txt
sudo mkdir -p /etc/adrobot /var/lib/adrobot
sudo chown adrobot:adrobot /var/lib/adrobot
```

Создайте `/etc/adrobot/adrobot.env`, указав адрес Keitaro и ключ API, `ADMIN_USERNAME`, хэш Argon2 в `ADMIN_PASSWORD_HASH` и постоянный случайный `SESSION_SECRET_KEY`. Добавьте:

```text
DATABASE_URL=sqlite:////var/lib/adrobot/adrobot.db
SESSION_COOKIE_SECURE=true
```

Сгенерируйте хэш пароля командой `/opt/adrobot/.venv/bin/python -m app.password_hash` из каталога `/opt/adrobot`, а ключ сессии — командой `python3 -c 'import secrets; print(secrets.token_urlsafe(48))'`. Защитите файл с настройками:

```bash
sudo chown root:adrobot /etc/adrobot/adrobot.env
sudo chmod 640 /etc/adrobot/adrobot.env
```

Установите и включите systemd-сервис и сайт Nginx:

```bash
sudo cp /opt/adrobot/deploy/systemd/adrobot.service /etc/systemd/system/adrobot.service
sudo cp /opt/adrobot/deploy/nginx/adrobot.iversdev.ru.conf /etc/nginx/sites-available/adrobot.iversdev.ru
sudo ln -s /etc/nginx/sites-available/adrobot.iversdev.ru /etc/nginx/sites-enabled/adrobot.iversdev.ru
sudo nginx -t
sudo systemctl daemon-reload
sudo systemctl enable --now adrobot nginx
sudo certbot --nginx -d adrobot.iversdev.ru
sudo systemctl restart adrobot
```

Сервис systemd запускает Uvicorn, привязанный к localhost, применяет миграции Alembic перед запуском и хранит SQLite-базу в `/var/lib/adrobot`. Nginx проксирует запросы, ограничивает частоту попыток входа, а Certbot настраивает HTTPS. Просмотр логов сервиса: `sudo journalctl -u adrobot -f`. Не открывайте порт 8000 для публичного доступа.

## Совместимость с Keitaro API

Взаимодействие с API реализовано в `app/keitaro/client.py`. Версии Keitaro Admin API могут различаться по допустимым полям потоков и отчётов. Если документация вашего экземпляра указывает другие поля или маршруты, измените этот адаптер и соответствующие тесты. Ошибки Keitaro возвращаются как HTTP 502, а не скрываются под видом успешного выполнения.

## Тесты

```powershell
pytest
```
