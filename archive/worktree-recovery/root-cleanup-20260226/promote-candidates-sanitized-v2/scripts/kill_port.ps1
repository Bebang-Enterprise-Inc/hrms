param (
    [Parameter(Mandatory=$true)]
    [int]$Port
)

Write-Host "Looking for process locking port $Port..."
$netstat = netstat -ano | findstr ":$Port" | Select-String "LISTENING"
if (-not $netstat) {
    Write-Host "No process is listening on port $Port."
    exit
}

$pidStr = ($netstat.Line -split '\s+')[-1]
$processId = [int]$pidStr

if ($processId -eq 0) {
    Write-Host "Port is locked by the System (PID 0)."
    exit
}

$process = Get-Process -Id $processId -ErrorAction SilentlyContinue
if ($process) {
    Write-Host "Found process '$($process.ProcessName)' (PID: $processId) on port $Port. Killing it..."
    Stop-Process -Id $processId -Force
    Write-Host "Process killed successfully."
} else {
    Write-Host "Process with PID $processId no longer exists or access is denied."
}
