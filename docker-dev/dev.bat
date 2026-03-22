@echo off
REM Local Frappe Development Helper for Windows
REM Usage: dev.bat [command]

cd /d "%~dp0"

if "%1"=="" goto help
if "%1"=="help" goto help
if "%1"=="start" goto start
if "%1"=="stop" goto stop
if "%1"=="restart" goto restart
if "%1"=="sync" goto sync
if "%1"=="shell" goto shell
if "%1"=="bench" goto bench
if "%1"=="logs" goto logs
if "%1"=="test" goto test
if "%1"=="migrate" goto migrate
if "%1"=="reset" goto reset
if "%1"=="status" goto status
goto help

:start
echo Starting local Frappe dev environment...
docker compose up -d
echo Waiting for services...
timeout /t 5 /nobreak >nul
docker compose logs -f frappe
goto end

:stop
echo Stopping local Frappe dev environment...
docker compose down
goto end

:restart
echo Restarting Frappe to pick up code changes...
docker compose restart frappe
goto end

:sync
echo Syncing BEI API files to container...
docker exec -it frappe-dev bash -c "cp -f /bei-api/*.py /home/frappe/frappe-bench/apps/hrms/hrms/api/ 2>/dev/null || true"
docker exec -it frappe-dev bash -c "cp -f /bei-api/__init__.py /home/frappe/frappe-bench/apps/hrms/hrms/api/__init__.py 2>/dev/null || true"
echo Clearing cache...
docker exec -it frappe-dev bench --site dev.localhost clear-cache
echo Done! Changes should be live.
goto end

:shell
echo Opening shell in Frappe container...
docker exec -it frappe-dev bash
goto end

:bench
shift
docker exec -it frappe-dev bench %1 %2 %3 %4 %5 %6 %7 %8 %9
goto end

:logs
docker compose logs -f frappe
goto end

:test
echo Testing API endpoint...
docker exec -it frappe-dev bench execute hrms.api.employee_clearance.get_exit_interview_questions
goto end

:migrate
echo Running database migrations...
docker exec -it frappe-dev bench --site dev.localhost migrate
goto end

:reset
echo Resetting local environment (deletes all data)...
set /p confirm=Are you sure? [y/N]
if /i "%confirm%"=="y" (
    docker compose down -v
    echo Done. Run 'dev.bat start' to reinitialize.
)
goto end

:status
docker compose ps
goto end

:help
echo Frappe Local Development Helper
echo.
echo Usage: dev.bat [command]
echo.
echo Commands:
echo   start    - Start the dev environment (first run takes 10-15 min)
echo   stop     - Stop the dev environment
echo   restart  - Restart Frappe to pick up code changes
echo   sync     - Sync BEI API files and clear cache (quick reload)
echo   shell    - Open bash shell in container
echo   bench    - Run bench command (e.g., dev.bat bench migrate)
echo   logs     - Follow Frappe logs
echo   test     - Test employee_clearance API
echo   migrate  - Run database migrations
echo   reset    - Delete everything and start fresh
echo   status   - Show container status
echo.
echo Development Workflow:
echo   1. Edit files in hrms\api\ locally
echo   2. Run 'dev.bat sync' to apply changes
echo   3. Test your API
echo.
echo Access:
echo   - Frappe: http://localhost:8000
echo   - Login: Administrator / admin
goto end

:end
