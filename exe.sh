#!/usr/bin/env bash
set -euo pipefail

COMMAND="${1:-up}"

compose_up() {
  docker compose up --build -d
  echo "Stack started."
  echo "API docs: http://localhost:8000/docs"
}

compose_down() {
  docker compose down -v
  echo "Stack stopped and volumes removed."
}

compose_logs() {
  docker compose logs -f api worker postgres redis
}

compose_restart() {
  docker compose down
  compose_up
}

compose_status() {
  docker compose ps
}

case "$COMMAND" in
  up)
    compose_up
    ;;
  down)
    compose_down
    ;;
  logs)
    compose_logs
    ;;
  restart)
    compose_restart
    ;;
  status)
    compose_status
    ;;
  *)
    echo "Usage: ./exe.sh {up|down|logs|restart|status}"
    exit 1
    ;;
esac
