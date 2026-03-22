#!/bin/bash
# Local Frappe Development Helper
# Usage: ./dev.sh [command]

set -e
cd "$(dirname "$0")"

case "${1:-help}" in
  start)
    echo "Starting local Frappe dev environment..."
    docker compose up -d
    echo "Waiting for services..."
    sleep 5
    docker compose logs -f frappe
    ;;

  stop)
    echo "Stopping local Frappe dev environment..."
    docker compose down
    ;;

  restart)
    echo "Restarting Frappe to pick up code changes..."
    docker compose restart frappe
    ;;

  sync)
    echo "Syncing BEI API files to container..."
    docker exec -it frappe-dev bash -c "cp -f /bei-api/*.py /home/frappe/frappe-bench/apps/hrms/hrms/api/ 2>/dev/null || true"
    docker exec -it frappe-dev bash -c "cp -f /bei-api/__init__.py /home/frappe/frappe-bench/apps/hrms/hrms/api/__init__.py 2>/dev/null || true"
    echo "Clearing cache..."
    docker exec -it frappe-dev bench --site dev.localhost clear-cache
    echo "Done! Changes should be live."
    ;;

  shell)
    echo "Opening shell in Frappe container..."
    docker exec -it frappe-dev bash
    ;;

  bench)
    shift
    docker exec -it frappe-dev bench "$@"
    ;;

  logs)
    docker compose logs -f frappe
    ;;

  test)
    echo "Testing API endpoint..."
    docker exec -it frappe-dev bench execute hrms.api.employee_clearance.get_exit_interview_questions
    ;;

  migrate)
    echo "Running database migrations..."
    docker exec -it frappe-dev bench --site dev.localhost migrate
    ;;

  reset)
    echo "Resetting local environment (deletes all data)..."
    read -p "Are you sure? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
      docker compose down -v
      echo "Done. Run './dev.sh start' to reinitialize."
    fi
    ;;

  status)
    docker compose ps
    ;;

  help|*)
    echo "Frappe Local Development Helper"
    echo ""
    echo "Usage: ./dev.sh [command]"
    echo ""
    echo "Commands:"
    echo "  start    - Start the dev environment (first run takes 10-15 min)"
    echo "  stop     - Stop the dev environment"
    echo "  restart  - Restart Frappe to pick up code changes"
    echo "  sync     - Sync BEI API files and clear cache (quick reload)"
    echo "  shell    - Open bash shell in container"
    echo "  bench    - Run bench command (e.g., ./dev.sh bench migrate)"
    echo "  logs     - Follow Frappe logs"
    echo "  test     - Test employee_clearance API"
    echo "  migrate  - Run database migrations"
    echo "  reset    - Delete everything and start fresh"
    echo "  status   - Show container status"
    echo ""
    echo "Development Workflow:"
    echo "  1. Edit files in hrms/api/ locally"
    echo "  2. Run './dev.sh sync' to apply changes"
    echo "  3. Test your API"
    echo ""
    echo "Access:"
    echo "  - Frappe: http://localhost:8000"
    echo "  - Login: Administrator / admin"
    ;;
esac
