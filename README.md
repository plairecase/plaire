# Plaire Auto-Edit

Автомонтаж роликов Plaire. Каждое утро GitHub Actions берёт исходники с Google Диска и кладёт в папку `Done` готовые ролики 9:16, обложки и подписи. Полная инструкция для Claude лежит в `.claude/skills/plaire-autoedit/SKILL.md`.

## Где мы сейчас

**Фаза 1, шаг 1:** доступ к Google Диску и проверка путей.

| шаг | что | статус |
|---|---|---|
| 1 | доступ к Диску, дерево папок, подтверждение путей | в работе |
| 2 | `brand.json`, валидатор текста, `texts.json` | — |
| 3 | индекс исходников с разметкой зрением | — |
| 4 | шаблоны `p_one_line` и `n_statement` | — |
| 5 | обложки, подписи, `manifest.json`, проверка качества, отчёт | — |
| 6 | ежедневный запуск по расписанию, 7 дней без сбоев | — |

## Доступ к Google Диску

### 1. Сервисный аккаунт (10 минут)

1. Откройте https://console.cloud.google.com → вверху выбор проекта → **New project** → имя `plaire-autoedit` → **Create**.
2. Меню → **APIs & Services → Library** → найдите **Google Drive API** → **Enable**.
3. Меню → **IAM & Admin → Service Accounts** → **Create service account** → имя `plaire-autoedit` → **Done** (роли не нужны).
4. Откройте созданный аккаунт → вкладка **Keys** → **Add key → Create new key → JSON**. Скачается файл `.json`. Это ключ: никому его не пересылайте и не кладите в репозиторий.
5. Скопируйте email аккаунта (вида `plaire-autoedit@….iam.gserviceaccount.com`).
6. На Google Диске: правый клик по папке **Plaire** → **Поделиться** → вставьте этот email → права **Редактор** → снимите галочку «Уведомить» → **Отправить**.
7. Откройте папку Plaire. В адресе после `/folders/` стоит её ID, например `https://drive.google.com/drive/folders/`**`1AbC…xyz`**. Скопируйте его.

### 2. Секреты в GitHub

Репозиторий → **Settings → Secrets and variables → Actions → New repository secret**:

| имя | что вставить |
|---|---|
| `GDRIVE_SA_JSON` | всё содержимое скачанного `.json` (откройте в Блокноте, скопируйте целиком) |
| `GDRIVE_ROOT_ID` | ID папки Plaire из пункта 7 |
| `ANTHROPIC_API_KEY` | ключ с https://console.anthropic.com (нужен с шага 3, можно добавить сразу) |

### 3. Проверка

**Actions → «Проверка Диска» → Run workflow.** Через минуту в отчёте запуска появятся дерево папки Plaire, найденные папки и результат проверки записи. Скрипт ничего не удаляет и не меняет: он только создаёт файл `_autoedit_state/healthcheck.txt`.

### Если запись не работает (`storageQuotaExceeded`)

У сервисного аккаунта Google нет своего места на Диске. Читать вашу папку он может, а создавать файлы в обычном «Моём диске» Google ему не даёт. Есть два выхода:

**А. Общий диск (Shared Drive).** Только если у вас Google Workspace. Перенесите папку Plaire на общий диск и добавьте туда email сервисного аккаунта с ролью «Редактор контента». Больше ничего менять не нужно.

**Б. Вход через OAuth в статусе «In production»** (бесплатно, обычный Gmail):

1. В том же проекте Google Cloud: **APIs & Services → OAuth consent screen** (или **Google Auth Platform**) → тип **External** → заполните имя и email → сохраните.
2. Раздел **Audience** → **Publish app** → статус должен стать **In production**. Это важно: в статусе «Testing» вход умирает через 7 дней, и монтаж молча перестанет работать.
3. **Clients → Create client → Desktop app** → скопируйте **Client ID** и **Client secret**.
4. На своём компьютере установите rclone (https://rclone.org/downloads/) и выполните:
   ```
   rclone authorize "drive" "ВАШ_CLIENT_ID" "ВАШ_CLIENT_SECRET"
   ```
   Откроется браузер. Войдите в Google. На экране «Google hasn't verified this app» нажмите **Advanced → Go to … (unsafe)**: это ваше же приложение. Разрешите доступ. В терминале появится строка `{"access_token": … }`. Скопируйте её целиком.
5. Добавьте секреты `GDRIVE_OAUTH_CLIENT_ID`, `GDRIVE_OAUTH_CLIENT_SECRET`, `GDRIVE_OAUTH_TOKEN` (строка из пункта 4). `GDRIVE_ROOT_ID` остаётся. Если заданы секреты OAuth, система входит через OAuth.

Вход в статусе «In production» не истекает сам. Он слетает, только если вы отзовёте доступ в аккаунте Google или им не пользуются 6 месяцев.

## Правила

- Система **ничего не публикует**. Она только кладёт файлы в `Done`.
- На Диске она пишет только в `Done` и `_autoedit_state`. Исходники, `3D`, `SFX` и `Music` не трогает.
- Секреты не попадают ни в код, ни в логи.
