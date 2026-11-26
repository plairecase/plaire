#!/usr/bin/env bash
# Настраивает rclone-remote "gdrive:" (корень = папка Plaire) из секретов GitHub.
# Ничего секретного в лог не выводит. Конфиг передаётся через переменные
# окружения RCLONE_CONFIG_GDRIVE_*, файл rclone.conf не создаётся.
#
# Способы входа:
#   1) сервисный аккаунт: GDRIVE_SA_JSON (+ GDRIVE_ROOT_ID)
#   2) OAuth-токен rclone: GDRIVE_OAUTH_TOKEN (+ GDRIVE_ROOT_ID),
#      по желанию свой GDRIVE_OAUTH_CLIENT_ID / GDRIVE_OAUTH_CLIENT_SECRET.
#      Если задан GDRIVE_OAUTH_TOKEN, используется он.
set -euo pipefail

fail() { echo "::error::$1"; exit 1; }
out="${GITHUB_ENV:-/dev/null}"

[ -n "${GDRIVE_ROOT_ID:-}" ] || fail "Нет секрета GDRIVE_ROOT_ID (ID папки Plaire). Добавьте его: Settings → Secrets and variables → Actions."

{
  echo "RCLONE_CONFIG_GDRIVE_TYPE=drive"
  echo "RCLONE_CONFIG_GDRIVE_SCOPE=drive"
  echo "RCLONE_CONFIG_GDRIVE_ROOT_FOLDER_ID=${GDRIVE_ROOT_ID}"
} >> "$out"

if [ -n "${GDRIVE_OAUTH_TOKEN:-}" ]; then
  # Свой client_id необязателен: без него rclone входит через своё
  # проверенное Google приложение, токен не истекает через 7 дней.
  if [ -n "${GDRIVE_OAUTH_CLIENT_ID:-}" ] && [ -n "${GDRIVE_OAUTH_CLIENT_SECRET:-}" ]; then
    {
      echo "RCLONE_CONFIG_GDRIVE_CLIENT_ID=${GDRIVE_OAUTH_CLIENT_ID}"
      echo "RCLONE_CONFIG_GDRIVE_CLIENT_SECRET=${GDRIVE_OAUTH_CLIENT_SECRET}"
    } >> "$out"
  fi
  python3 -c 'import json,os,sys; d=json.loads(os.environ["GDRIVE_OAUTH_TOKEN"]); sys.exit(0 if d.get("refresh_token") else 1)' 2>/dev/null \
    || fail "GDRIVE_OAUTH_TOKEN — не та строка. Нужна строка вида {\"access_token\":...,\"refresh_token\":...} из команды rclone authorize, целиком."
  {
    echo "RCLONE_CONFIG_GDRIVE_TOKEN=${GDRIVE_OAUTH_TOKEN}"
    echo "GDRIVE_AUTH_MODE=oauth"
  } >> "$out"
  echo "Вход на Диск: OAuth"
  exit 0
fi

[ -n "${GDRIVE_SA_JSON:-}" ] || fail "Нет секрета GDRIVE_SA_JSON (ключ сервисного аккаунта). Инструкция в README.md, раздел «Доступ к Google Диску»."

sa_file="${RUNNER_TEMP:-/tmp}/gdrive_sa.json"
( umask 077; printf '%s' "$GDRIVE_SA_JSON" > "$sa_file" )
python3 - "$sa_file" <<'PY' || fail "GDRIVE_SA_JSON — не JSON-ключ сервисного аккаунта. Вставьте содержимое скачанного .json файла целиком."
import json, sys
try:
    d = json.load(open(sys.argv[1]))
    ok = d.get("type") == "service_account" and d.get("client_email") and d.get("private_key")
except Exception:
    ok = False
sys.exit(0 if ok else 1)
PY
{
  echo "RCLONE_CONFIG_GDRIVE_SERVICE_ACCOUNT_FILE=${sa_file}"
  echo "GDRIVE_AUTH_MODE=service_account"
  echo "GDRIVE_SA_FILE=${sa_file}"
} >> "$out"
echo "Вход на Диск: сервисный аккаунт"
