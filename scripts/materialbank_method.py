"""
Material Bank to Method CRM Integration

Imports leads from Material Bank exports into Method CRM and creates activities.
"""

import os
import requests
import pandas as pd
import re
import time
from datetime import datetime, timedelta
from pathlib import Path


METHOD_API_KEY = "Njk0MDlkYmUyMTIzYjFhM2MwZjhmZTBmLjEzRjgzMkNEMEIzNTRDRUI5OTJCNjBGQTI4Q0FDQzgz"

def get_api_key():
    """Get Method API key."""
    return METHOD_API_KEY


def get_headers(content_type=False):
    """Get headers for Method API requests."""
    api_key = get_api_key()
    if not api_key:
        raise ValueError("METHOD_API_KEY not configured")
    headers = {'Authorization': f'ApiKey {api_key}'}
    if content_type:
        headers['Content-Type'] = 'application/json'
    return headers


BASE_URL = 'https://rest.method.me/api/v1'


def extract_email_from_text(text):
    """Extract email from text that may contain other info."""
    if pd.isna(text):
        return None
    emails = re.findall(r'[\w\.-]+@[\w\.-]+', str(text))
    return emails[0].lower() if emails else None


def load_existing_contacts():
    """Load all existing contacts from Method CRM."""
    headers = get_headers()
    email_to_contact = {}

    skip = 0
    while True:
        r = requests.get(f'{BASE_URL}/tables/Contacts?skip={skip}&top=100', headers=headers)
        if r.status_code == 429:
            time.sleep(30)
            continue
        if r.status_code != 200:
            break

        contacts = r.json().get('value', [])
        if not contacts:
            break

        for c in contacts:
            email = (c.get('Email') or '').lower()
            if email:
                email_to_contact[email] = {
                    'RecordID': c['RecordID'],
                    'Entity_RecordID': c.get('Entity_RecordID'),
                    'Entity': c.get('Entity'),
                    'Name': c.get('Name'),
                }

        skip += 100
        time.sleep(0.15)

    return email_to_contact


def convert_materialbank_to_method(df, existing_emails=None):
    """
    Convert Material Bank DataFrame to Method CRM import format.

    Returns tuple of (method_df, stats_dict)
    """
    total_rows = len(df)

    # Parse and sort by Order Date
    df = df.copy()
    df['Order Date'] = pd.to_datetime(df['Order Date'], format='%m/%d/%Y')
    df = df.sort_values('Order Date', ascending=True)

    # Deduplicate by email + company (first order wins for contact info)
    df_unique = df.drop_duplicates(subset=['Email', 'Company'], keep='first').copy()
    unique_leads = len(df_unique)

    # Exclude existing contacts
    excluded = 0
    if existing_emails:
        before = len(df_unique)
        df_unique = df_unique[~df_unique['Email'].str.lower().isin(existing_emails)]
        excluded = before - len(df_unique)

    # Build Method CRM format
    method_df = pd.DataFrame()
    method_df['FirstName'] = df_unique['First Name']
    method_df['LastName'] = df_unique['Last Name']
    method_df['CompanyName'] = df_unique['Company']
    method_df['Email'] = df_unique['Email']
    method_df['Phone'] = df_unique['Work Phone'].fillna(df_unique['Mobile Phone'])
    method_df['Mobile'] = df_unique['Mobile Phone']
    method_df['Website'] = ''
    method_df['Tags'] = 'Arazzo'
    method_df['Sales Rep'] = 'LA'
    method_df['Lead Source'] = 'Material Bank'
    method_df['Lead Rating'] = 'Warm'
    method_df['Lead Status'] = 'Open'

    stats = {
        'total_rows': total_rows,
        'unique_leads': unique_leads,
        'excluded_existing': excluded,
        'new_leads': len(method_df)
    }

    return method_df, stats


def create_activity(contact_name, contact_email, company, samples, project_info, order_date, contacts_record_id=None):
    """Create an MB Samples activity in Method CRM."""
    headers = get_headers(content_type=True)

    samples_text = ', '.join(samples)

    comments = f"""<p><strong>Material Bank Sample Request</strong></p>
<p><strong>Order Date:</strong> {order_date}</p>
<p><strong>Samples Requested:</strong> {samples_text}</p>
<p><strong>Project:</strong> {project_info.get('name', 'N/A')}</p>
<p><strong>Project Type:</strong> {project_info.get('type', 'N/A')}</p>
<p><strong>Project Budget:</strong> {project_info.get('budget', 'N/A')}</p>
<p><strong>Project Phase:</strong> {project_info.get('phase', 'N/A')}</p>"""

    activity_data = {
        'ActivityType_RecordID': 22,  # MB Samples
        'ActivityStatus_RecordID': 3,  # Completed
        'AssignedTo_RecordID': 3,  # Laura Ablan
        'Comments': comments,
        'ContactName': contact_name,
        'ContactEmail': contact_email,
        'ActivityCompanyName': company,
        'DueDateStart': order_date,
        'IsToBeRenewed': True,  # Create follow-up
    }

    if contacts_record_id:
        activity_data['Contacts_RecordID'] = contacts_record_id

    r = requests.post(f'{BASE_URL}/tables/Activity', headers=headers, json=activity_data)

    if r.status_code == 201:
        return int(r.text)
    return None


def create_followup_activity(parent_activity_id, contact_name, contact_email, contacts_record_id, days_out=7):
    """Create an Intro EMAIL follow-up activity."""
    headers = get_headers(content_type=True)

    due_date = (datetime.now() + timedelta(days=days_out)).strftime('%Y-%m-%d')

    followup_data = {
        'ActivityType_RecordID': 19,  # 1. Intro EMAIL
        'ActivityStatus_RecordID': 1,  # Not Started
        'AssignedTo_RecordID': 3,  # Laura Ablan
        'Contacts_RecordID': contacts_record_id,
        'ContactName': contact_name,
        'ContactEmail': contact_email,
        'DueDateStart': due_date,
        'FollowUpFromActivityNo_RecordID': parent_activity_id,
    }

    r = requests.post(f'{BASE_URL}/tables/Activity', headers=headers, json=followup_data)

    if r.status_code == 201:
        return int(r.text)
    return None


def process_materialbank_import(mb_df, existing_contacts=None, progress_callback=None):
    """
    Full pipeline: Convert MB data, create activities, and follow-ups.

    Args:
        mb_df: Material Bank DataFrame
        existing_contacts: Dict of email -> contact info (optional, will fetch if None)
        progress_callback: Function to call with progress updates (msg, pct)

    Returns:
        Dict with results and stats
    """
    results = {
        'leads_processed': 0,
        'activities_created': 0,
        'followups_created': 0,
        'errors': [],
        'details': []
    }

    def update_progress(msg, pct=None):
        if progress_callback:
            progress_callback(msg, pct)

    # Load existing contacts if not provided
    if existing_contacts is None:
        update_progress("Loading existing contacts from Method...", 0)
        existing_contacts = load_existing_contacts()

    existing_emails = set(existing_contacts.keys())

    # Convert to Method format and get unique leads
    update_progress("Processing Material Bank data...", 10)
    method_df, stats = convert_materialbank_to_method(mb_df, existing_emails)
    results['conversion_stats'] = stats

    if len(method_df) == 0:
        results['errors'].append("No new leads to import (all already exist)")
        return results

    # Group MB data by email to get samples per lead
    mb_df['Email_Lower'] = mb_df['Email'].str.lower()
    new_emails = set(method_df['Email'].str.lower())
    mb_filtered = mb_df[mb_df['Email_Lower'].isin(new_emails)]

    total_leads = len(method_df)

    for idx, (email, group) in enumerate(mb_filtered.groupby('Email_Lower')):
        pct = 20 + int(70 * idx / total_leads)

        lead_row = group.iloc[0]
        contact_name = f"{lead_row['First Name']} {lead_row['Last Name']}"
        company = lead_row['Company']

        update_progress(f"Processing {contact_name}...", pct)

        # Collect samples
        samples = []
        for _, row in group.iterrows():
            sample = f"{row['Name']} {row['Color']}".strip()
            if sample and sample not in samples:
                samples.append(sample)

        project_info = {
            'name': lead_row.get('Project Name', ''),
            'type': lead_row.get('Project Type', ''),
            'budget': lead_row.get('Project Budget', ''),
            'phase': lead_row.get('Project Phase', ''),
        }

        order_date = lead_row['Order Date'].strftime('%Y-%m-%d') if pd.notna(lead_row['Order Date']) else datetime.now().strftime('%Y-%m-%d')

        # Get contact record ID if exists
        contacts_record_id = None
        if email in existing_contacts:
            contacts_record_id = existing_contacts[email]['RecordID']

        # Create activity
        activity_id = create_activity(
            contact_name=contact_name,
            contact_email=email,
            company=company,
            samples=samples,
            project_info=project_info,
            order_date=order_date,
            contacts_record_id=contacts_record_id
        )

        if activity_id:
            results['activities_created'] += 1

            # Create follow-up if we have the contact
            if contacts_record_id:
                followup_id = create_followup_activity(
                    parent_activity_id=activity_id,
                    contact_name=contact_name,
                    contact_email=email,
                    contacts_record_id=contacts_record_id
                )
                if followup_id:
                    results['followups_created'] += 1

            results['details'].append({
                'name': contact_name,
                'email': email,
                'company': company,
                'samples': len(samples),
                'activity_id': activity_id
            })
        else:
            results['errors'].append(f"Failed to create activity for {contact_name}")

        results['leads_processed'] += 1
        time.sleep(0.3)  # Rate limiting

    update_progress("Complete!", 100)
    return results
