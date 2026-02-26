@echo off
REM Store Dashboard Daily Sync to Supabase
REM Scheduled to run daily at 6:30 AM via Windows Task Scheduler
REM (30 minutes after SCM sync to avoid rate limiting)
REM
REM To install:
REM   schtasks /create /tn "BEI_Store_Dashboard_Sync" /tr "C:\Users\Sam\Projects\Claude\BEI-ERP\scripts\sync_store_dashboards_daily.bat" /sc daily /st 06:30
REM
REM To remove:
REM   schtasks /delete /tn "BEI_Store_Dashboard_Sync" /f

setlocal

REM Set working directory
cd /d "C:\Users\Sam\Projects\Claude\BEI-ERP"

REM Generate timestamp for log file
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set LOG_DATE=%datetime:~0,8%

REM Set log file path
set LOG_FILE=logs\store_dashboard_sync_%LOG_DATE%.log

REM Log start time
echo ========================================== >> %LOG_FILE%
echo Store Dashboard Sync Started: %date% %time% >> %LOG_FILE%
echo ========================================== >> %LOG_FILE%

REM Run the sync script
python data\_tools\sync_store_dashboards.py >> %LOG_FILE% 2>&1

REM Log completion
echo. >> %LOG_FILE%
echo Store Dashboard Sync Completed: %date% %time% >> %LOG_FILE%
echo ========================================== >> %LOG_FILE%

REM Clean up old logs (keep last 30 days)
python data\_tools\sync_store_dashboards.py --cleanup-logs >> %LOG_FILE% 2>&1

endlocal
