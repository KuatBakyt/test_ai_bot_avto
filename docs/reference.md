# Review Studio — учебная CRM

Отдельный проект для обучения: выполненная работа → Telegram-диалог → подтверждённый отзыв → AI-пост с фотографией → официальный Instagram API.

**По умолчанию DEMO_MODE=true. Без OpenAI и Instagram ключей можно пройти весь сценарий в интерфейсе. Ничего не публикуется.** Это отдельная база и отдельные порты, существующий Flowza CRM менять не нужно.

## Что работает

- Django REST, JWT-вход, Swagger, владелец видит только свои работы.
- Flutter Web: список работ, загрузка фото, приглашение, симулятор клиента, просмотр отзыва/поста, публикация и ошибки.
- Telegram-бот: клиент сам открывает приглашение; сначала согласие на AI, затем 2–4 ответа. В рабочем режиме GPT выбирает уточняющие вопросы по ответам. В деморежиме вопросы фиксированы.
- Клиент подтверждает точный текст отзыва. Его ответы соединяются дословно, AI не переписывает отзыв. Отдельная кнопка разрешает Instagram; можно оставить отзыв только мастеру.
- AI-модуль внутри Django получает факты о работе, разрешённое фото и подтверждённый отзыв, готовит вступление. Отзыв добавляется программно без изменений. Это использование готовой модели OpenAI, собственная модель не обучается.
- Подготовка и публикация через Celery + Redis + Beat. Мастер может включить автоматическую публикацию для конкретной работы либо сначала проверить черновик.
- Один снимок в одном посте; JPEG создаётся из JPEG/PNG/WebP, EXIF удаляется, при неподходящих пропорциях добавляются белые поля без обрезания.
- Фото обычно закрыто JWT. Для Instagram временно доступен непредсказуемый URL только во время обработки разрешённого поста.
- Состояния и ID контейнера/поста сохраняются. Повторная отправка после неизвестного результата запрещена, чтобы не создавать дубль.
- Тестовые работы навсегда помечены как демонстрационные. Переключение .env не превращает их в настоящие публикации.

## Запуск на Windows (PowerShell)

Нужны Git, Docker Desktop и Flutter 3.47.6 или совместимая более новая версия. Папку проекта лучше создать вне OneDrive, например `C:\projects`, чтобы Flutter мог свободно обновлять build.

```powershell
git clone https://github.com/KuatBakyt/test_ai_bot_avto.git
cd test_ai_bot_avto
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

В `.env` вставьте результат в `DJANGO_SECRET_KEY`; задайте свой `OWNER_PASSWORD` (минимум 8 символов; лучше 16 и больше). `OWNER_USERNAME=owner`. Для первого теста оставьте `DEMO_MODE=true`, Instagram отключённым, внешние ключи пустыми. Если Python не установлен, случайный ключ можно сгенерировать внутри Docker после сборки командой `docker compose run --rm api python -c "import secrets; print(secrets.token_urlsafe(48))"`.

```powershell
docker compose up -d --build
docker compose exec api python manage.py create_owner
```

После сообщения `Owner created`:

```powershell
cd frontend
flutter pub get
flutter run -d chrome --web-port 8081 --dart-define=API_URL=http://localhost:8100/api/v1
```

- Приложение: http://localhost:8081
- Swagger: http://localhost:8100/api/docs/
- Админка (просмотр данных): http://localhost:8100/admin/
- Вход: ваш `OWNER_USERNAME` и `OWNER_PASSWORD` из `.env`.

Порты **8100 и 8081**, чтобы не конфликтовать с Flowza на 8000/8080. Первая команда создания владельца не меняет пароль уже существующего пользователя. Изменение OWNER_PASSWORD в .env также не меняет существующий пароль; используйте `docker compose exec api python manage.py changepassword owner`.

### Первый тест без внешних сервисов

1. Добавьте работу: название, реальные факты, город, фото от 320 px; подтвердите право обработки фото и публикации.
2. Для первого теста оставьте автопубликацию выключенной.
3. Создайте приглашение → «Открыть тестовый диалог» → согласие на AI.
4. Отправьте три ответа, подтвердите отзыв, разрешите публикацию.
5. За 15–30 секунд появится черновик (работают worker и beat).
6. Проверьте текст → «Имитировать публикацию». Статус станет «Тест завершён», настоящий Instagram ничего не получит.
7. Добавьте другую работу с автопубликацией и повторите: после разрешения клиента оба шага пройдут автоматически.
8. Отказ от Instagram сохраняет отзыв, но не создаёт пост.

Если черновик не появляется: `docker compose logs --tail=100 worker beat api` из корня репозитория.

## Настоящий Telegram-бот

Создайте нового бота в @BotFather. В корневом `.env` укажите токен и username без @:

```dotenv
TELEGRAM_BOT_TOKEN=your-token
TELEGRAM_BOT_USERNAME=your_bot_username
```

```powershell
docker compose --profile telegram up -d
docker compose exec bot python manage.py run_bot --check
```

Запускайте только один процесс бота с этим токеном. Входящие update_id и очередь ответов хранятся в базе: повторное событие не добавляет ответ клиента дважды. При сбое после успешной отправки, но до фиксации результата Telegram может повторить сообщение бота; сам отзыв и пост не дублируются. `--check` проверяет getMe и username, сообщений не отправляет. В Telegram-диалоге /stop отзывает согласие текущего отзыва на будущие публикации. Уже опубликованный пост владелец удаляет в Instagram вручную.

Ссылка приглашения действует 7 дней; первый клиентский чат закрепляется за отзывом. Ссылка отображается только при создании, база хранит её хэш. Если клиент ещё не начал диалог, можно создать новую ссылку; старая перестанет действовать. Один человек может оставить отзывы по разным работам, но только один активный диалог одновременно.

Telegram подключается к тому же Django-проекту и его базе как отдельный процесс, HTTP-запросы к старому Flowza ему не нужны. Бот не входит в репозиторий старого клиентского бота.

## GPT в рабочем режиме

```dotenv
DEMO_MODE=false
OPENAI_API_KEY=your-project-key
OPENAI_MODEL=gpt-4o-mini
INSTAGRAM_PUBLISH_ENABLED=false
```

Пересоздайте процессы: `docker compose --profile telegram up -d --force-recreate`. Создавайте **новые работы**, прежние остаются тестовыми. Реальный клиент проходит Telegram-диалог; симулятор в рабочем режиме недоступен. Текст и фото отправляются в OpenAI только при записанных согласиях. Нужен API-ключ проекта с доступной моделью и балансом; подписка ChatGPT сама по себе API не оплачивает. Запросы используют Responses API, Structured Outputs и `store=False`; журнал не содержит ключей или исходных ошибок провайдера.

Документация:
- https://developers.openai.com/api/docs/guides/structured-outputs
- https://developers.openai.com/api/docs/guides/images-vision

## Официальная публикация в Instagram

В проекте реализован путь **Instagram API with Instagram Login** — не Facebook Login.

1. Нужен ваш профессиональный Instagram-аккаунт (Business или Creator).
2. В Meta for Developers создайте приложение с Instagram API / Instagram Login, подключите свой аккаунт согласно настройкам приложения. Для собственного тестового аккаунта настройте роли/тестовый доступ; подключение чужих аккаунтов может требовать App Review и Advanced Access.
3. Получите Instagram User access token с разрешениями `instagram_business_basic` и `instagram_business_content_publish`, и Instagram User ID. Facebook Page token сюда не подходит.
4. Разместите Django за публичным HTTPS-доменом; Meta должна получать JPEG без авторизации. `PUBLIC_BASE_URL` — домен Django без /api/v1. Маршрут `/public/photos/` должен вести в Django, не в статическую папку Flutter.
5. Укажите поддерживаемую вашим Meta-приложением версию Graph API (в примере v23.0), проверьте срок токена и права. Автоматическое OAuth-подключение и обновление токенов в этой учебной версии не реализованы: токен устанавливается вручную.
6. После проверки включите:

```dotenv
DEMO_MODE=false
INSTAGRAM_PUBLISH_ENABLED=true
INSTAGRAM_ACCESS_TOKEN=your-instagram-user-token
INSTAGRAM_USER_ID=your-numeric-id
INSTAGRAM_API_VERSION=v23.0
PUBLIC_BASE_URL=https://your-backend-domain.example
```

Механика: POST `/{ig-user-id}/media` → сохранение контейнера → проверка `status_code` → POST `/{ig-user-id}/media_publish` → сохранение ID и permalink. Хост — `https://graph.instagram.com`. При неопределённом результате публикации статус `UNCERTAIN`: проверьте аккаунт вручную; кнопки слепого повтора нет. После явной ошибки до публикации настройки можно исправить и повторить.

**Это обычный пост в ленте, не платная реклама Meta Ads.** В этой версии нет каруселей, Stories, Reels, рекламных кампаний или автоматического создания Instagram-аккаунта.

Документация Meta:
- https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/content-publishing/
- Официальная коллекция Meta: https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api

## Swagger

POST `/api/v1/auth/login/` с `{"username":"owner","password":"ваш пароль"}` → скопировать access → Authorize → Bearer JWT. Для `/jobs/` загрузка фото через multipart/form-data; GET `/jobs/` и карточка показывают этапы отзыва/поста. Согласие настоящего клиента нельзя установить через обычный API владельца.

Можно запланировать черновик POST `/api/v1/jobs/{id}/publish/` с `{"due_at":"2026-10-10T09:00:00+05:00"}` (до 30 дней); без due_at публикация ближайшим циклом. В интерфейсе первой версии кнопка публикации отправляет сразу.

## Обновление и остановка

```powershell
git pull
docker compose --profile telegram up -d --build
# После обновлений Flutter перезапустите flutter run.
docker compose down
```

Не добавляйте `-v` к down: это удаляет базу и фотографии. `.env`, ключи, фотографии и база не попадают в Git. Перед рабочими обновлениями сохраните дамп PostgreSQL и том photos.

## Для размещения вне компьютера

Проект пока не задеплоен. На сервере нужны PostgreSQL, Redis, api/worker/beat/bot и HTTPS reverse proxy. Соберите Flutter командой `flutter build web --dart-define=API_URL=https://your-backend-domain.example/api/v1` и разместите build/web на статическом хостинге. В серверной .env: `DJANGO_DEBUG=false`, свои `DJANGO_ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, отдельные сильные секреты/пароли. Не открывайте PostgreSQL/Redis в интернет; не публикуйте папку media целиком. TLS proxy должен передавать корректный X-Forwarded-Proto, открывать наружу только HTTPS. Нужны резервные копии и контроль срока токена.

## Проверки разработчика

```powershell
python -m pip install -r requirements.txt
$env:DJANGO_SECRET_KEY='test-only-secret-at-least-32-characters'
python -m pytest -q
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py spectacular --file schema.yaml --fail-on-warn
cd frontend
flutter analyze
flutter test
flutter build web
```

Тесты по умолчанию используют отдельную SQLite в памяти. Для PostgreSQL задайте TEST_DATABASE_URL к отдельной тестовой базе; CI использует PostgreSQL и собирает Docker/Flutter. Реальные OpenAI/Telegram/Instagram вызовы требуют ваших ключей и аккаунтов; автоматические тесты проверяют адаптеры на заглушках, а не публикацию в вашем аккаунте.

Учебная версия: без регистрации владельцев, оплаты, полной CRM заявок, автоматической ротации Instagram-токенов, SSO и production-мониторинга. Она предназначена для проверки сценария отзыв → пост; существующая Flowza CRM остаётся отдельным приложением.
