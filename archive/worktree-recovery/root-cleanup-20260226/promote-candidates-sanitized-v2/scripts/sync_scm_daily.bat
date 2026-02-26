@echo off
REM SCM Daily Sync to Supabase
REM Scheduled to run daily at 6:00 AM via Windows Task Scheduler
REM
REM To install:
REM   schtasks /create /tn "BEI_SCM_Sync" /tr "C:\Users\Sam\Projects\Claude\BEI-ERP\scripts\sync_scm_daily.bat" /sc daily /st 06:00
REM
REM To remove:
REM   schtasks /delete /tn "BEI_SCM_Sync" /f

setlocal

REM Set working directory
cd /d "C:\Users\Sam\Projects\Claude\BEI-ERP"

REM Generate timestamp for log file
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set LOG_DATE=%datetime:~0,8%

REM Set log file path
set LOG_FILE=logs\scm_sync_%LOG_DATE%.log

REM Log start time
echo ========================================== >> %LOG_FILE%
echo SCM Sync Started: %date% %time% >> %LOG_FILE%
echo ========================================== >> %LOG_FILE%

REM Run the sync script
python data\_tools\sync_scm_to_supabase.py >> %LOG_FILE% 2>&1

REM Log completion
echo. >> %LOG_FILE%
echo SCM Sync Completed: %date% %time% >> %LOG_FILE%
echo ========================================== >> %LOG_FILE%

REM Clean up old logs (keep last 30 days)
python data\_tools\sync_scm_to_supabase.py --cleanup-logs >> %LOG_FILE% 2>&1

endlocal
