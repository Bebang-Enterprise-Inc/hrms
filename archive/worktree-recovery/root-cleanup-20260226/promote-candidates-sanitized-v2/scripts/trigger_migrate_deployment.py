"""Trigger manual deployment with migrate flag"""
import requests
import sys

token = sys.stdin.read().strip()

response = requests.post(
    'https://api.github.com/repos/Bebang-Enterprise-Inc/hrms/actions/workflows/build-and-deploy.yml/dispatches',
    headers={'Authorization': f'token {token}', 'Accept': 'application/vnd.github.v3+json'},
    json={'ref': 'production', 'inputs': {'skip_build': 'true', 'run_migrate': 'true'}}
)

print(f'Status: {response.status_code}')
if response.status_code != 204:
    print(f'Error: {response.text}')
else:
    print('[OK] Manual deployment triggered with migrate=true')
    print('[OK] This will run bench migrate on production')
    print('[OK] Wait 2-3 minutes for migration to complete')
