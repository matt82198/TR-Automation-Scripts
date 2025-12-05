import os

cid = os.environ.get('PAYPAL_CLIENT_ID', '')
sec = os.environ.get('PAYPAL_CLIENT_SECRET', '')

print(f"Client ID length: {len(cid)}")
print(f"Secret length: {len(sec)}")
print(f"Client ID has leading/trailing whitespace: {cid != cid.strip()}")
print(f"Secret has leading/trailing whitespace: {sec != sec.strip()}")
print(f"\nClient ID (full): '{cid}'")
print(f"\nSecret (full): '{sec}'")
print(f"\nSecret seems short - typical PayPal secrets are ~80 chars")
