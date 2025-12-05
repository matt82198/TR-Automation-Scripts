import os
import requests
import base64

# Get credentials
PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID')
PAYPAL_CLIENT_SECRET = os.environ.get('PAYPAL_CLIENT_SECRET')

print(f"Testing with credentials:")
print(f"  Client ID: {PAYPAL_CLIENT_ID}")
print(f"  Secret: {PAYPAL_CLIENT_SECRET}")
print()

# Test sandbox
print("Testing SANDBOX endpoint...")
credentials = f"{PAYPAL_CLIENT_ID}:{PAYPAL_CLIENT_SECRET}"
encoded = base64.b64encode(credentials.encode()).decode()

response = requests.post(
    'https://api-m.sandbox.paypal.com/v1/oauth2/token',
    headers={
        'Authorization': f'Basic {encoded}',
        'Content-Type': 'application/x-www-form-urlencoded'
    },
    data={'grant_type': 'client_credentials'}
)

print(f"Sandbox Status: {response.status_code}")
print(f"Sandbox Response: {response.json()}")
print()

# Test live
print("Testing LIVE endpoint...")
response = requests.post(
    'https://api-m.paypal.com/v1/oauth2/token',
    headers={
        'Authorization': f'Basic {encoded}',
        'Content-Type': 'application/x-www-form-urlencoded'
    },
    data={'grant_type': 'client_credentials'}
)

print(f"Live Status: {response.status_code}")
print(f"Live Response: {response.json()}")
