#!/usr/bin/env bash
#
# Build and run Monsun with demo data, using Docker or Podman.
#
#   ./launch_demo.sh              build (if needed), start, seed, open
#   ./launch_demo.sh --rebuild    force a fresh image build
#   ./launch_demo.sh --reset      DELETE the database volume, then start clean
#   ./launch_demo.sh --stop       stop the stack, keep the data
#
# Ports are taken by other services often enough to be worth overriding:
#   MONSUN_APP_PORT=9090 MONSUN_DB_PORT=5433 ./launch_demo.sh
#
# Set MONSUN_COMPOSE to force a specific compose command.

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

APP_PORT="${MONSUN_APP_PORT:-8081}"
DB_PORT="${MONSUN_DB_PORT:-5432}"
export MONSUN_APP_PORT="$APP_PORT" MONSUN_DB_PORT="$DB_PORT"

REBUILD=0
RESET=0
STOP=0

for arg in "$@"; do
    case "$arg" in
        --rebuild) REBUILD=1 ;;
        --reset)   RESET=1 ;;
        --stop)    STOP=1 ;;
        -h|--help)
            awk 'NR>2 && /^#/ {sub(/^# ?/, ""); print; next} NR>2 {exit}' "$0"
            exit 0
            ;;
        *)
            echo "Unknown option: $arg (try --help)" >&2
            exit 2
            ;;
    esac
done

say()  { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!\033[0m   %s\n' "$*" >&2; }
die()  { printf '\033[1;31mx\033[0m   %s\n' "$*" >&2; exit 1; }

# --- Pick a compose command -------------------------------------------------

find_compose() {
    if [[ -n "${MONSUN_COMPOSE:-}" ]]; then
        echo "$MONSUN_COMPOSE"
        return
    fi
    if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
        echo "docker compose"
    elif command -v docker-compose >/dev/null 2>&1; then
        echo "docker-compose"
    elif command -v podman >/dev/null 2>&1 && podman compose version >/dev/null 2>&1; then
        echo "podman compose"
    elif command -v podman-compose >/dev/null 2>&1; then
        echo "podman-compose"
    else
        return 1
    fi
}

COMPOSE="$(find_compose)" || die "Need Docker or Podman with compose support. Install one, or set MONSUN_COMPOSE."
say "Using: $COMPOSE"

compose() { $COMPOSE "$@"; }

# --- Stop / reset -----------------------------------------------------------

if [[ $STOP -eq 1 ]]; then
    say "Stopping the stack (data kept)"
    compose down
    exit 0
fi

if [[ $RESET -eq 1 ]]; then
    warn "--reset deletes the Postgres volume: every exercise, persona, post and"
    warn "user account in this stack is destroyed. The demo data is re-seeded after."
    read -r -p "Type 'reset' to confirm: " reply
    [[ "$reply" == "reset" ]] || die "Aborted — nothing was deleted."
    say "Removing containers and the database volume"
    compose down -v
fi

# --- Port checks ------------------------------------------------------------

port_busy() {
    local port="$1"
    if command -v lsof >/dev/null 2>&1; then
        lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
    elif command -v ss >/dev/null 2>&1; then
        ss -ltn "sport = :$port" 2>/dev/null | grep -q LISTEN
    else
        return 1  # can't tell — let compose report the conflict
    fi
}

# A port held by our own already-running stack is fine; anything else is not.
ours() { compose ps --format '{{.Names}}' 2>/dev/null | grep -q .; }

for spec in "app:$APP_PORT:MONSUN_APP_PORT" "db:$DB_PORT:MONSUN_DB_PORT"; do
    IFS=: read -r name port var <<<"$spec"
    if port_busy "$port" && ! ours; then
        die "Port $port ($name) is already in use by something else.
    Pick another:  $var=<port> ./launch_demo.sh"
    fi
done

# --- Build and start --------------------------------------------------------

BUILD_FLAG=()
[[ $REBUILD -eq 1 ]] && BUILD_FLAG=(--build)

say "Starting Postgres on port $DB_PORT"
compose up -d "${BUILD_FLAG[@]}" db

say "Waiting for Postgres to accept connections"
for _ in $(seq 1 60); do
    if compose exec -T db pg_isready -U claw -d claw >/dev/null 2>&1; then
        break
    fi
    sleep 1
done
compose exec -T db pg_isready -U claw -d claw >/dev/null 2>&1 \
    || die "Postgres did not come up in 60s. Check: $COMPOSE logs db"

say "Seeding demo data (skipped if it already exists)"
compose run --rm -e PYTHONPATH=/app app uv run python scripts/seed_demo.py

say "Starting the app on port $APP_PORT"
compose up -d "${BUILD_FLAG[@]}" app

say "Waiting for the app to respond"
URL="http://localhost:$APP_PORT"
for _ in $(seq 1 60); do
    if curl -fsS -o /dev/null "$URL/login" 2>/dev/null; then
        break
    fi
    sleep 1
done
curl -fsS -o /dev/null "$URL/login" 2>/dev/null \
    || die "App did not respond in 60s. Check: $COMPOSE logs app"

cat <<EOF

  Monsun is running.

    URL       $URL
    Login     admin / admin
    Exercise  Operation Nordlys (live, with a seeded feed)

    Logs      $COMPOSE logs -f app
    Stop      ./launch_demo.sh --stop
    Wipe      ./launch_demo.sh --reset

EOF
