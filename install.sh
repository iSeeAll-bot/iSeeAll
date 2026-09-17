#!/usr/bin/env bash
#
# iSeeAll — универсальный установщик для VPS (Ubuntu/Debian)
# Спрашивает: название, метод (systemd/Docker), токен бота, ID владельца.
# Использование: sudo bash install.sh
# Или одной командой: curl -sSL https://raw.githubusercontent.com/iSeeAll-bot/iSeeAll/main/install.sh | sudo bash
# По вопросам: @xicge

set -euo pipefail

CONTACT="@xicge"
REPO_URL="https://github.com/iSeeAll-bot/iSeeAll"
DEFAULT_NAME="iSeeAll"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
fail()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }

echo "=============================================="
echo "   👁 iSeeAll — Telegram Business Bot"
echo "   Установщик для VPS (Ubuntu/Debian)"
echo "   Вопросы и помощь: ${CONTACT}"
echo "=============================================="
echo

if [[ $EUID -ne 0 ]]; then
    fail "Запусти через sudo: sudo bash install.sh"
fi

info "Проверяю системные пакеты (git, python3, venv, pip)..."
if command -v apt-get >/dev/null 2>&1; then
    apt-get update -qq
    apt-get install -y -qq git python3 python3-venv python3-pip >/dev/null
else
    warn "apt-get не найден — предполагаю, что пакеты уже установлены."
fi
command -v python3 >/dev/null 2>&1 || fail "python3 не найден."
info "Python: $(python3 --version)"

echo
echo "Название будет использовано в папке установки, имени сервиса/контейнера,"
echo "и в приветствии твоего бота."
read -r -p "Название бота/инстанса [${DEFAULT_NAME}]: " INSTANCE
INSTANCE="${INSTANCE:-${DEFAULT_NAME}}"
while ! [[ "$INSTANCE" =~ ^[A-Za-z0-9_-]+$ ]]; do
    warn "Только латиница, цифры, дефис и подчёркивание. Пример: iSeeAll"
    read -r -p "Название бота/инстанса [${DEFAULT_NAME}]: " INSTANCE
    INSTANCE="${INSTANCE:-${DEFAULT_NAME}}"
done

SERVICE_NAME="$(echo "$INSTANCE" | tr '[:upper:]' '[:lower:]')"
INSTALL_DIR="/opt/${INSTANCE}"
info "Папка: ${INSTALL_DIR} | Сервис: ${SERVICE_NAME}"

echo
echo "Как развернуть бота?"
echo "  1) systemd — обычная установка (рекомендуется)"
echo "  2) Docker  — в изолированном контейнере"
read -r -p "Метод [1]: " METHOD
METHOD="${METHOD:-1}"
while ! [[ "$METHOD" =~ ^[12]$ ]]; do
    warn "Введи 1 или 2."
    read -r -p "Метод [1]: " METHOD
    METHOD="${METHOD:-1}"
done
if [[ "$METHOD" == "1" ]]; then info "Выбрано: systemd"; else info "Выбрано: Docker"; fi

info "Подготовка файлов проекта..."
CLEANUP_TMP=""
SRC_DIR="."
if [[ ! -f "bot.py" || ! -f "dump_generator.py" ]]; then
    info "Файлы бота не найдены в текущей директории. Клонирую актуальный репозиторий с GitHub..."
    command -v git >/dev/null 2>&1 || fail "git не установлен. Установи git и запусти снова."
    TMP_DIR="$(mktemp -d /tmp/iseeall-install.XXXXXX)"
    CLEANUP_TMP="$TMP_DIR"
    git clone --depth=1 "$REPO_URL.git" "$TMP_DIR" >/dev/null 2>&1 || fail "Не удалось склонировать репозиторий $REPO_URL"
    SRC_DIR="$TMP_DIR"
fi

info "Копирую проект в ${INSTALL_DIR}..."
mkdir -p "$INSTALL_DIR"
for f in bot.py config.py database.py dump_generator.py requirements.txt README.md .env.example docker-compose.yml Dockerfile; do
    [[ -f "$SRC_DIR/$f" ]] && cp "$SRC_DIR/$f" "$INSTALL_DIR/"
done

if [[ -n "$CLEANUP_TMP" && -d "$CLEANUP_TMP" ]]; then
    rm -rf "$CLEANUP_TMP"
fi

[[ -f "$INSTALL_DIR/bot.py" && -f "$INSTALL_DIR/dump_generator.py" ]] || fail "Файлы проекта не скопировались."

ENV_FILE="$INSTALL_DIR/.env"
echo
echo "———————————— Настройка ————————————"
echo "Токен бота можно получить у @BotFather в Telegram."
read -r -p "Вставь BOT_TOKEN: " BOT_TOKEN
while ! [[ "$BOT_TOKEN" =~ ^[0-9]+:[A-Za-z0-9_-]{30,}$ ]]; do
    warn "Токен выглядит неправильно. Пример: 1234567890:ABCdef...xyz"
    read -r -p "Вставь BOT_TOKEN ещё раз: " BOT_TOKEN
done

echo
echo "Твой Telegram ID можно узнать у @userinfobot — просто напиши ему /start."
read -r -p "Вставь твой Telegram USER_ID (владелец): " OWNER_ID
while ! [[ "$OWNER_ID" =~ ^[0-9]+$ ]]; do
    warn "ID должен быть числом, например: 123456789"
    read -r -p "Вставь твой Telegram USER_ID ещё раз: " OWNER_ID
done

read -r -p "Сколько дней хранить сообщения в базе? [30]: " CACHE_DAYS
CACHE_DAYS="${CACHE_DAYS:-30}"
[[ "$CACHE_DAYS" =~ ^[0-9]+$ ]] || CACHE_DAYS=30

cat > "$ENV_FILE" <<EOF
BOT_TOKEN=${BOT_TOKEN}
OWNER_ID=${OWNER_ID}
CACHE_DAYS=${CACHE_DAYS}
BOT_NAME=${INSTANCE}
REPO_URL=${REPO_URL}
EOF
chmod 600 "$ENV_FILE"
info "Конфигурация сохранена в ${ENV_FILE} (права 600)."

# ===== РАЗВЕРТЫВАНИЕ =====
if [[ "$METHOD" == "1" ]]; then
    info "Создаю виртуальное окружение и ставлю зависимости..."
    [[ -d "$INSTALL_DIR/venv" ]] || python3 -m venv "$INSTALL_DIR/venv"
    "$INSTALL_DIR/venv/bin/pip" install --quiet --upgrade pip
    "$INSTALL_DIR/venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"

    info "Настраиваю автозапуск через systemd..."
    systemctl stop "$SERVICE_NAME" 2>/dev/null || true

    cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF2
[Unit]
Description=${INSTANCE} Telegram Business Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${INSTALL_DIR}
ExecStart=${INSTALL_DIR}/venv/bin/python ${INSTALL_DIR}/bot.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF2

    systemctl daemon-reload
    systemctl enable --now "$SERVICE_NAME"
    sleep 3

    echo
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        info "Сервис запущен и добавлен в автозагрузку!"
    else
        fail "Сервис не поднялся. Логи: journalctl -u ${SERVICE_NAME} -n 50 --no-pager"
    fi
    journalctl -u "$SERVICE_NAME" -n 8 --no-pager || true
    echo
    echo "Полезно: journalctl -u ${SERVICE_NAME} -f | systemctl restart ${SERVICE_NAME}"
else
    info "Проверяю Docker..."
    if ! command -v docker >/dev/null 2>&1; then
        info "Docker не найден — устанавливаю..."
        apt-get install -y -qq docker.io docker-compose-v2 >/dev/null 2>&1 \
            || apt-get install -y -qq docker.io docker-compose-plugin >/dev/null
    fi
    systemctl enable --now docker >/dev/null 2>&1 || true

    DC="docker compose"
    docker compose version >/dev/null 2>&1 || DC="docker-compose"
    info "Использую: ${DC}"

    cd "$INSTALL_DIR"
    $DC up -d --build
    sleep 5

    echo
    if $DC ps 2>/dev/null | grep -qiE 'up|running'; then
        info "Контейнер запущен и добавлен в автоперезапуск!"
    else
        fail "Контейнер не поднялся. Логи: ${DC} logs --tail 50"
    fi
    $DC logs --no-log-prefix --tail 8 2>&1 || true
    echo
    echo "Полезно (в ${INSTALL_DIR}): ${DC} logs -f | ${DC} restart | ${DC} down"
fi

echo
echo "=============================================="
echo -e "${GREEN}Готово! 🚀${NC} Бот «${INSTANCE}» развернут. Осталось подключить аккаунт:"
echo "  1. Напиши своему боту /start в Telegram."
echo "  2. Профиль → Изменить → Автоматизация чатов (Бизнес)."
echo "  3. Добавь бота и разреши доступ к сообщениям."
echo
echo "Вопросы и помощь: ${CONTACT}"
echo "=============================================="
