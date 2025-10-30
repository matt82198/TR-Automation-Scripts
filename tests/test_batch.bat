@echo off
set PAYPAL_CLIENT_SECRET=EB3TC1QOko_HZwCtb1iMm2Ji6w7Vicmiv5S5udlhgBD7wpqYVKmHRzwjVobWppFBkWYOjhpo3d8EhKDz
python -c "import os; print('Secret from batch:', os.environ.get('PAYPAL_CLIENT_SECRET', 'NOT SET')); print('Length:', len(os.environ.get('PAYPAL_CLIENT_SECRET', '')))"
