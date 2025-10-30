import os
import requests
import base64
import json

# Get credentials
PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID')
PAYPAL_CLIENT_SECRET = os.environ.get('PAYPAL_CLIENT_SECRET')
PAYPAL_MODE = os.environ.get('PAYPAL_MODE', 'live')

print("=" * 60)
print("PayPal Authentication Debug")
print("=" * 60)
print(f"\nClient ID: {PAYPAL_CLIENT_ID[:20]}... (truncated)")
print(f"Secret: {PAYPAL_CLIENT_SECRET[:20]}... (truncated)")
print(f"Mode: {PAYPAL_MODE}")
print(f"Client ID length: {len(PAYPAL_CLIENT_ID) if PAYPAL_CLIENT_ID else 0}")
print(f"Secret length: {len(PAYPAL_CLIENT_SECRET) if PAYPAL_CLIENT_SECRET else 0}")

# Try both endpoints
endpoints = {
    'live': 'https://api-m.paypal.com',
    'sandbox': 'https://api-m.sandbox.paypal.com'
}

for mode, base_url in endpoints.items():
    print(f"\n{'=' * 60}")
    print(f"Testing {mode.upper()} endpoint: {base_url}")
    print(f"{'=' * 60}")

    credentials = f"{PAYPAL_CLIENT_ID}:{PAYPAL_CLIENT_SECRET}"
    encoded = base64.b64encode(credentials.encode()).decode()

    print(f"Encoded credentials length: {len(encoded)}")

    try:
        response = requests.post(
            f'{base_url}/v1/oauth2/token',
            headers={
                'Authorization': f'Basic {encoded}',
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            data={'grant_type': 'client_credentials'}
        )

        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")

        try:
            response_json = response.json()
            print(f"Response JSON: {json.dumps(response_json, indent=2)}")
        except:
            print(f"Response Text: {response.text}")

        if response.status_code == 200:
            print(f"\n✓ SUCCESS! Authentication worked on {mode} endpoint")
            print(f"Access Token: {response_json.get('access_token', '')[:30]}...")
        else:
            print(f"\n✗ FAILED on {mode} endpoint")

    except Exception as e:
        print(f"Error: {e}")
