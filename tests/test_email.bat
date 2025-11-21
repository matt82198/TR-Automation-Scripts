@echo off
set EMAIL_USER=matt@thetanneryrow.com
python scripts\squarespace_to_quickbooks.py --order-numbers 12821 --output squarespace_invoice_12821_TEST.iif --email matt@thetanneryrow.com
