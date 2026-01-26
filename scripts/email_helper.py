"""
Email helper for sending IIF files
"""
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import List


def send_iif_email(
    iif_file: str,
    report_file: str,
    recipient: str,
    invoice_count: int,
    new_customer_count: int,
    smtp_host: str = 'smtp.gmail.com',
    smtp_port: int = 587,
    smtp_user: str = None,
    smtp_password: str = None
) -> bool:
    """
    Send IIF file and report via email

    Args:
        iif_file: Path to IIF file
        report_file: Path to new customers report
        recipient: Email address to send to
        invoice_count: Number of invoices in the file
        new_customer_count: Number of new customers
        smtp_host: SMTP server hostname
        smtp_port: SMTP server port
        smtp_user: SMTP username
        smtp_password: SMTP password

    Returns:
        True if successful, False otherwise
    """
    if not smtp_user or not smtp_password:
        print("ERROR: Email credentials not set")
        print("Set EMAIL_USER and EMAIL_PASSWORD environment variables")
        return False

    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = recipient
        msg['Subject'] = f"Daily Squarespace Invoices - {invoice_count} invoice(s)"

        # Email body
        body = f"""Daily Squarespace Invoice Report

Invoices: {invoice_count}
New Customers: {new_customer_count}

Attached files:
1. {os.path.basename(iif_file)} - Import this into QuickBooks
2. {os.path.basename(report_file)} - Review new customers before importing

To Import:
1. Open QuickBooks Desktop
2. File > Utilities > Import > IIF Files
3. Select the attached IIF file
4. QuickBooks will:
   - Skip existing customers (by name)
   - Create new customers with full contact info
   - Create all invoices

---
This is an automated report from Squarespace to QuickBooks integration.
"""

        msg.attach(MIMEText(body, 'plain'))

        # Attach IIF file
        with open(iif_file, 'rb') as f:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename={os.path.basename(iif_file)}')
            msg.attach(part)

        # Attach report file
        with open(report_file, 'rb') as f:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename={os.path.basename(report_file)}')
            msg.attach(part)

        # Send email
        print(f"\nSending email to {recipient}...")
        server = smtplib.SMTP(smtp_host, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
        server.quit()

        print(f"[OK] Email sent successfully to {recipient}")
        return True

    except Exception as e:
        print(f"ERROR sending email: {e}")
        return False
