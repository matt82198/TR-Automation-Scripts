@echo off
set PAYPAL_CLIENT_SECRET=REDACTED_SECRET
python -c "import os; print('Secret from batch:', os.environ.get('PAYPAL_CLIENT_SECRET', 'NOT SET')); print('Length:', len(os.environ.get('PAYPAL_CLIENT_SECRET', '')))"
