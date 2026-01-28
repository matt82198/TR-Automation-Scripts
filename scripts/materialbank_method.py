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
    df['Order Date'] = pd.to_datetime(df['Order Date'], format='mixed', dayfirst=False)
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


def create_contact(first_name, last_name, company, email, phone=None, mobile=None):
    """Create a new contact/lead in Method CRM."""
    headers = get_headers(content_type=True)

    contact_data = {
        'FirstName': first_name,
        'LastName': last_name,
        'CompanyName': company,
        'Email': email,
        'TagList': 'Arazzo',
        'SalesRepRecordID': 3,  # Laura Ablan (LA)
        'LeadSource': 'Material Bank',
        'LeadRating': 'Warm',
        'LeadStatus': 'Open',
    }

    if phone:
        contact_data['Phone'] = phone
    if mobile:
        contact_data['Mobile'] = mobile

    r = requests.post(f'{BASE_URL}/tables/Contacts', headers=headers, json=contact_data)

    if r.status_code == 201:
        return int(r.text), None
    return None, f"API {r.status_code}: {r.text[:200]}"


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
        return int(r.text), None
    # Return error for logging
    return None, f"API {r.status_code}: {r.text[:200]}"


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
        return int(r.text), None
    return None, f"API {r.status_code}: {r.text[:200]}"


def process_materialbank_import(mb_df, existing_contacts=None, progress_callback=None):
    """
    Full pipeline: Convert MB data, create activities, and follow-ups.

    Creates MB Samples activities for ALL leads (including existing contacts).
    Only creates Intro EMAIL follow-up for NEW contacts.

    Args:
        mb_df: Material Bank DataFrame
        existing_contacts: Dict of email -> contact info (optional, will fetch if None)
        progress_callback: Function to call with progress updates (msg, pct)

    Returns:
        Dict with results and stats
    """
    results = {
        'leads_processed': 0,
        'contacts_created': 0,
        'activities_created': 0,
        'followups_created': 0,
        'existing_updated': 0,
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

    # Convert to Method format for stats (this filters to new leads only for CSV export)
    update_progress("Processing Material Bank data...", 10)
    method_df, stats = convert_materialbank_to_method(mb_df, existing_emails)
    results['conversion_stats'] = stats

    # Process ALL leads for MB Samples (not just new ones)
    mb_df = mb_df.copy()
    mb_df['Order Date'] = pd.to_datetime(mb_df['Order Date'], format='mixed', dayfirst=False)
    mb_df['Email_Lower'] = mb_df['Email'].str.lower()

    # Get unique emails
    unique_emails = mb_df['Email_Lower'].unique()
    total_leads = len(unique_emails)

    if total_leads == 0:
        results['errors'].append("No leads to process")
        return results

    for idx, email in enumerate(unique_emails):
        pct = 20 + int(70 * idx / total_leads)

        group = mb_df[mb_df['Email_Lower'] == email]
        lead_row = group.iloc[0]
        contact_name = f"{lead_row['First Name']} {lead_row['Last Name']}"
        company = lead_row['Company']
        is_existing = email in existing_emails

        update_progress(f"Processing {contact_name} ({'existing' if is_existing else 'new'})...", pct)

        # Collect all samples for this lead
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

        # Get contact record ID if exists, or create new contact
        contacts_record_id = None
        if email in existing_contacts:
            contacts_record_id = existing_contacts[email]['RecordID']
        else:
            # Create new contact first
            first_name = lead_row['First Name']
            last_name = lead_row['Last Name']
            phone = lead_row.get('Work Phone', '') or ''
            mobile = lead_row.get('Mobile Phone', '') or ''

            new_contact_id, contact_error = create_contact(
                first_name=first_name,
                last_name=last_name,
                company=company,
                email=email,
                phone=phone if pd.notna(phone) else None,
                mobile=mobile if pd.notna(mobile) else None
            )

            if new_contact_id:
                contacts_record_id = new_contact_id
                results['contacts_created'] += 1
                # Add to existing_contacts so we don't try to create again
                existing_contacts[email] = {'RecordID': new_contact_id}
            else:
                results['errors'].append(f"Contact creation failed for {contact_name}: {contact_error}")

            time.sleep(0.3)  # Rate limiting

        # Create MB Samples activity for ALL leads
        activity_id, error = create_activity(
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
            if is_existing:
                results['existing_updated'] += 1

            # Always create follow-up (parallel workflows allowed for new sample orders)
            if contacts_record_id:
                followup_id, followup_error = create_followup_activity(
                    parent_activity_id=activity_id,
                    contact_name=contact_name,
                    contact_email=email,
                    contacts_record_id=contacts_record_id
                )
                if followup_id:
                    results['followups_created'] += 1
                elif followup_error:
                    results['errors'].append(f"Follow-up failed for {contact_name}: {followup_error}")

            results['details'].append({
                'name': contact_name,
                'email': email,
                'company': company,
                'samples': len(samples),
                'activity_id': activity_id,
                'contact_id': contacts_record_id,
                'is_existing': is_existing,
                'is_new_contact': not is_existing
            })
        else:
            results['errors'].append(f"Activity failed for {contact_name}: {error}")

        results['leads_processed'] += 1
        time.sleep(0.3)  # Rate limiting

    update_progress("Complete!", 100)
    return results


def fetch_orphaned_activities():
    """Fetch MB Samples activities that have no linked contact."""
    headers = get_headers()
    orphaned = []
    skip = 0

    while True:
        r = requests.get(
            f'{BASE_URL}/tables/Activity?$filter=ActivityType_RecordID eq 22&skip={skip}&top=100',
            headers=headers
        )
        if r.status_code == 429:
            time.sleep(30)
            continue
        if r.status_code != 200:
            break

        batch = r.json().get('value', [])
        if not batch:
            break

        for act in batch:
            if not act.get('Contacts_RecordID'):
                orphaned.append(act)

        skip += 100
        time.sleep(0.15)

    return orphaned


def update_activity_contact(activity_id, contacts_record_id):
    """Update an activity to link it to a contact."""
    headers = get_headers(content_type=True)

    update_data = {
        'Contacts_RecordID': contacts_record_id
    }

    r = requests.patch(f'{BASE_URL}/tables/Activity/{activity_id}', headers=headers, json=update_data)

    if r.status_code in (200, 204):
        return True, None
    return False, f"API {r.status_code}: {r.text[:200]}"


def delete_activity(activity_id):
    """Delete an activity from Method CRM."""
    headers = get_headers()

    r = requests.delete(f'{BASE_URL}/tables/Activity/{activity_id}', headers=headers)

    if r.status_code in (200, 204):
        return True, None
    return False, f"API {r.status_code}: {r.text[:200]}"


def fetch_all_mb_activities():
    """Fetch ALL MB Samples activities."""
    headers = get_headers()
    all_activities = []
    skip = 0

    while True:
        r = requests.get(
            f'{BASE_URL}/tables/Activity?$filter=ActivityType_RecordID eq 22&skip={skip}&top=100',
            headers=headers
        )
        if r.status_code == 429:
            time.sleep(30)
            continue
        if r.status_code != 200:
            break

        batch = r.json().get('value', [])
        if not batch:
            break

        all_activities.extend(batch)
        skip += 100
        time.sleep(0.15)

    return all_activities


def find_duplicate_activities(activities):
    """
    Find duplicate MB Samples activities (same email + same date).
    Returns list of activity IDs to delete (keeps the one with highest RecordID).
    """
    from collections import defaultdict

    by_email_date = defaultdict(list)

    for act in activities:
        email = (act.get('ContactEmail') or '').lower().strip()
        due_date = act.get('DueDateStart', '')

        if email:
            key = f"{email}|{due_date}"
            by_email_date[key].append(act)

    duplicates_to_delete = []
    duplicate_groups = []

    for key, acts in by_email_date.items():
        if len(acts) > 1:
            # Sort by RecordID descending, keep the highest (most recent)
            sorted_acts = sorted(acts, key=lambda x: x['RecordID'], reverse=True)
            keep = sorted_acts[0]
            delete = sorted_acts[1:]

            for act in delete:
                duplicates_to_delete.append(act)
                duplicate_groups.append({
                    'keep_id': keep['RecordID'],
                    'delete_id': act['RecordID'],
                    'email': act.get('ContactEmail', ''),
                    'name': act.get('ContactName', ''),
                    'date': act.get('DueDateStart', '')
                })

    return duplicates_to_delete, duplicate_groups


def cleanup_orphaned_activities(existing_contacts=None, progress_callback=None, remove_duplicates=True):
    """
    Find orphaned MB Samples activities and link them to contacts.
    Creates contacts if they don't exist. Optionally removes duplicates.

    Args:
        existing_contacts: Dict of email -> contact info (optional, will fetch if None)
        progress_callback: Function to call with progress updates (msg, pct)
        remove_duplicates: If True, also remove duplicate activities (same email+date)

    Returns:
        Dict with results and stats
    """
    results = {
        'orphaned_found': 0,
        'activities_linked': 0,
        'contacts_created': 0,
        'skipped_no_email': 0,
        'duplicates_removed': 0,
        'errors': [],
        'details': [],
        'duplicates_deleted': []
    }

    def update_progress(msg, pct=None):
        if progress_callback:
            progress_callback(msg, pct)

    # Load existing contacts if not provided
    if existing_contacts is None:
        update_progress("Loading existing contacts from Method...", 0)
        existing_contacts = load_existing_contacts()

    # Fetch ALL MB Samples activities for duplicate detection
    update_progress("Fetching all MB Samples activities...", 5)
    all_activities = fetch_all_mb_activities()

    # Remove duplicates first if requested
    if remove_duplicates:
        update_progress("Checking for duplicates...", 10)
        duplicates_to_delete, duplicate_groups = find_duplicate_activities(all_activities)

        if duplicates_to_delete:
            update_progress(f"Removing {len(duplicates_to_delete)} duplicate activities...", 12)

            for idx, act in enumerate(duplicates_to_delete):
                success, error = delete_activity(act['RecordID'])
                if success:
                    results['duplicates_removed'] += 1
                    results['duplicates_deleted'].append({
                        'activity_id': act['RecordID'],
                        'name': act.get('ContactName', ''),
                        'email': act.get('ContactEmail', '')
                    })
                else:
                    results['errors'].append(f"Failed to delete duplicate #{act['RecordID']}: {error}")
                time.sleep(0.2)

    # Fetch orphaned activities (re-fetch to exclude deleted duplicates)
    update_progress("Fetching orphaned activities...", 15)
    orphaned = fetch_orphaned_activities()
    results['orphaned_found'] = len(orphaned)

    if not orphaned and results['duplicates_removed'] == 0:
        update_progress("No cleanup needed!", 100)
        return results

    if not orphaned:
        update_progress("Duplicate removal complete!", 100)
        return results

    update_progress(f"Found {len(orphaned)} orphaned activities", 18)

    # Process each orphaned activity
    for idx, activity in enumerate(orphaned):
        pct = 20 + int(75 * idx / len(orphaned))
        activity_id = activity['RecordID']
        contact_name = activity.get('ContactName', 'Unknown')
        contact_email = (activity.get('ContactEmail') or '').lower().strip()
        company = activity.get('ActivityCompanyName', '')

        update_progress(f"Processing {contact_name}...", pct)

        if not contact_email:
            results['skipped_no_email'] += 1
            results['errors'].append(f"Activity #{activity_id}: No email address")
            continue

        # Check if contact exists
        contacts_record_id = None
        is_new = False

        if contact_email in existing_contacts:
            contacts_record_id = existing_contacts[contact_email]['RecordID']
        else:
            # Create new contact
            name_parts = contact_name.split(' ', 1)
            first_name = name_parts[0] if name_parts else ''
            last_name = name_parts[1] if len(name_parts) > 1 else ''

            new_contact_id, contact_error = create_contact(
                first_name=first_name,
                last_name=last_name,
                company=company,
                email=contact_email
            )

            if new_contact_id:
                contacts_record_id = new_contact_id
                results['contacts_created'] += 1
                existing_contacts[contact_email] = {'RecordID': new_contact_id}
                is_new = True
            else:
                results['errors'].append(f"Activity #{activity_id}: Failed to create contact - {contact_error}")
                continue

            time.sleep(0.3)

        # Update activity to link to contact
        success, error = update_activity_contact(activity_id, contacts_record_id)

        if success:
            results['activities_linked'] += 1
            results['details'].append({
                'activity_id': activity_id,
                'contact_name': contact_name,
                'contact_email': contact_email,
                'contact_id': contacts_record_id,
                'is_new_contact': is_new
            })
        else:
            results['errors'].append(f"Activity #{activity_id}: Failed to link - {error}")

        time.sleep(0.3)

    update_progress("Cleanup complete!", 100)
    return results
