#!/usr/bin/env bash
#
# iSeeAll — автоматический установщик для VPS (Ubuntu/Debian)
# Использование: sudo bash install.sh
# По вопросам: @xicge

set -euo pipefail

CONTACT="@xicge"
INSTALL_DIR="/opt/iSeeAll"
SERVICE_NAME="iseeall"

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

# ---------- 0. Права ----------
if [[ $EUID -ne 0 ]]; then
    fail "Запусти через sudo: sudo bash install.sh"
fi

# ---------- 1. Системные пакеты ----------
info "Проверяю системные пакеты (python3, venv, pip)..."
if command -v apt-get >/dev/null 2>&1; then
    apt-get update -qq
    apt-get install -y -qq python3 python3-venv python3-pip >/dev/null
else
    warn "apt-get не найден — предполагаю, что python3/venv/pip уже установлены."
fi
command -v python3 >/dev/null 2>&1 || fail "python3 не найден. Установи его вручную."
info "Python: $(python3 --version)"

# ---------- 2. Файлы проекта ----------
info "Копирую проект в ${INSTALL_DIR}..."
mkdir -p "$INSTALL_DIR"
for f in bot.py config.py database.py requirements.txt README.md .env.example; do
    [[ -f "$f" ]] || fail "Не найден файл $f — запускай установщик из корня склонированного репозитория."
    cp "$f" "$INSTALL_DIR/"
done

# ---------- 3. Виртуальное окружение ----------
info "Создаю виртуальное окружение и ставлю зависимости (это займёт минуту)..."
if [[ ! -d "$INSTALL_DIR/venv" ]]; then
    python3 -m venv "$INSTALL_DIR/venv"
fi
"$INSTALL_DIR/venv/bin/pip" install --quiet --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"
info "Зависимости установлены."

# ---------- 4. Настройка .env ----------
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
EOF
chmod 600 "$ENV_FILE"
info "Конфигурация сохранена в ${ENV_FILE} (права 600)."

# ---------- 5. Systemd ----------
info "Настраиваю автозапуск через systemd..."
systemctl stop "$SERVICE_NAME" 2>/dev/null || true

cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=iSeeAll Telegram Business Bot
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
EOF

systemctl daemon-reload
systemctl enable --now "$SERVICE_NAME"
sleep 3

# ---------- 6. Проверка результата ----------
echo
if systemctl is-active --quiet "$SERVICE_NAME"; then
    info "Сервис запущен и добавлен в автозагрузку!"
else
    fail "Сервис не поднялся. Смотри логи: journalctl -u ${SERVICE_NAME} -n 50 --no-pager"
fi

echo "———————————— Последние логи ————————————"
journalctl -u "$SERVICE_NAME" -n 10 --no-pager || true
echo "-----------------------------------------"
echo
echo "=============================================="
echo -e "${GREEN}Готово! 🚀${NC} Осталось подключить аккаунт:"
echo "  1. Напиши своему боту /start в Telegram."
echo "  2. Профиль → Изменить → Автоматизация чатов (Бизнес)."
echo "  3. Добавь бота и разреши доступ к сообщениям."
echo
echo "Полезные команды:"
echo "  journalctl -u ${SERVICE_NAME} -f          (логи вживую)"
echo "  systemctl restart ${SERVICE_NAME}         (перезапуск)"
echo
echo "Вопросы и помощь: ${CONTACT}"
echo "=============================================="
