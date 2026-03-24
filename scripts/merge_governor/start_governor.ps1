$env:ANTHROPIC_API_KEY = & 'C:\Users\Sam\bin\doppler.exe' secrets get ANTHROPIC_API_KEY --plain --project bei-erp --config dev
Set-Location 'F:\Dropbox\Projects\BEI-ERP'
& 'C:\Users\Sam\AppData\Local\Programs\Python\Python312\python.exe' -m scripts.merge_governor.governor_erp --ai-backend agent-sdk
