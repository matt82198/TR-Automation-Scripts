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


def api_request_with_retry(method, url, headers, json=None, max_retries=3, retry_callback=None):
    """
    Make API request with tiered retry on rate limiting or connection errors.

    Retry strategy:
    - 1st retry: wait 3 seconds
    - 2nd retry: wait 60 seconds
    - 3rd retry: wait 60 seconds

    Args:
        method: HTTP method (GET, POST, PATCH, DELETE)
        url: Request URL
        headers: Request headers
        json: JSON body for POST/PATCH
        max_retries: Maximum number of retry attempts
        retry_callback: Optional function(attempt, wait_seconds, reason) for UI updates

    Returns:
        Response object or None if all retries failed
    """
    retry_delays = [3, 60, 60]  # Seconds to wait for each retry attempt

    for attempt in range(max_retries):
        try:
            if method == 'POST':
                r = requests.post(url, headers=headers, json=json, timeout=30)
            elif method == 'GET':
                r = requests.get(url, headers=headers, timeout=30)
            elif method == 'DELETE':
                r = requests.delete(url, headers=headers, timeout=30)
            elif method == 'PATCH':
                r = requests.patch(url, headers=headers, json=json, timeout=30)
            else:
                raise ValueError(f"Unknown method: {method}")

            # Handle rate limiting (429)
            if r.status_code == 429:
                if attempt < max_retries - 1:
                    wait_time = retry_delays[min(attempt, len(retry_delays) - 1)]
                    if retry_callback:
                        retry_callback(attempt + 1, wait_time, "rate_limit")
                    time.sleep(wait_time)
                    continue
                else:
                    return r  # Return the 429 response if all retries exhausted

            return r

        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            if attempt < max_retries - 1:
                wait_time = retry_delays[min(attempt, len(retry_delays) - 1)]
                if retry_callback:
                    retry_callback(attempt + 1, wait_time, "connection_error")
                time.sleep(wait_time)
            else:
                # Return None instead of raising to allow graceful handling
                return None

    return None


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


def create_customer(company, first_name, last_name, email, phone=None, mobile=None, retry_callback=None):
    """
    Create a new Customer record in Method CRM.

    Returns tuple of (customer_record_id, error)
    """
    headers = get_headers(content_type=True)

    contact_name = f"{first_name} {last_name}".strip()
    customer_name = company or contact_name

    customer_data = {
        'Name': customer_name,
        'CompanyName': customer_name,
        'FullName': customer_name,
        'FirstName': first_name,
        'LastName': last_name,
        'Email': email,
        'Contact': contact_name,
        'EntityType': 'Customer Lead',
        'IsActive': True,
        'IsLeadStatusOnly': True,
        'LeadStatus_RecordID': 2,  # Open
        'LeadRating_RecordID': 2,  # Warm
        'LeadSource_RecordID': 14, # Material Bank
        'SalesRep_RecordID': 1,    # LA (Laura Ablan)
    }

    if phone:
        customer_data['Phone'] = phone
    if mobile:
        customer_data['Mobile'] = mobile

    r = api_request_with_retry('POST', f'{BASE_URL}/tables/Customer', headers=headers, json=customer_data, retry_callback=retry_callback)

    if r and r.status_code == 201:
        return int(r.text), None
    return None, f"API {r.status_code if r else 'No response'}: {r.text[:200] if r else 'Connection failed'}"


def create_contact(first_name, last_name, email, company, phone=None, mobile=None, entity_record_id=None):
    """
    Create a new Contact record in Method CRM, optionally linked to a Customer.

    Args:
        first_name, last_name, email, company: Contact details
        phone, mobile: Optional phone numbers
        entity_record_id: Customer RecordID to link this contact to (Entity_RecordID)

    Returns tuple of (contact_record_id, error)
    """
    headers = get_headers(content_type=True)

    contact_data = {
        'FirstName': first_name,
        'LastName': last_name,
        'Name': f"{first_name} {last_name}".strip(),
        'Email': email,
        'CompanyName': company,
        'TagList': 'Arazzo',
    }

    # Link to Customer if provided
    if entity_record_id:
        contact_data['Entity_RecordID'] = entity_record_id
        contact_data['Entity'] = company
        contact_data['EntityType'] = 'Customer'

    if phone:
        contact_data['Phone'] = phone
    if mobile:
        contact_data['Mobile'] = mobile

    r = api_request_with_retry('POST', f'{BASE_URL}/tables/Contacts', headers=headers, json=contact_data)

    if r and r.status_code == 201:
        return int(r.text), None
    return None, f"API {r.status_code if r else 'No response'}: {r.text[:200] if r else 'Connection failed'}"


def create_lead(first_name, last_name, email, company, phone=None, mobile=None):
    """
    Create a complete lead: Customer record + Contact record linked together.

    Returns tuple of (contact_record_id, customer_record_id, error)
    """
    # Step 1: Create Customer record
    customer_id, error = create_customer(
        company=company,
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
        mobile=mobile
    )

    if not customer_id:
        return None, None, f"Customer creation failed: {error}"

    time.sleep(0.3)  # Small delay between API calls

    # Step 2: Create Contact record linked to Customer
    contact_id, error = create_contact(
        first_name=first_name,
        last_name=last_name,
        email=email,
        company=company,
        phone=phone,
        mobile=mobile,
        entity_record_id=customer_id
    )

    if not contact_id:
        return None, customer_id, f"Contact creation failed (Customer #{customer_id} created): {error}"

    return contact_id, customer_id, None


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

    # Due date is one week after sample order date
    try:
        order_dt = datetime.strptime(order_date, '%Y-%m-%d')
        due_date = (order_dt + timedelta(days=7)).strftime('%Y-%m-%d')
    except:
        due_date = order_date  # Fallback if date parsing fails

    activity_data = {
        'ActivityType_RecordID': 22,  # MB Samples
        'ActivityStatus_RecordID': 3,  # Completed
        'AssignedTo_RecordID': 3,  # Laura Ablan
        'Comments': comments,
        'ContactName': contact_name,
        'ContactEmail': contact_email,
        'ActivityCompanyName': company,
        'DueDateStart': due_date,
        'IsToBeRenewed': True,  # Create follow-up
    }

    if contacts_record_id:
        activity_data['Contacts_RecordID'] = contacts_record_id

    r = api_request_with_retry('POST', f'{BASE_URL}/tables/Activity', headers=headers, json=activity_data)

    if r and r.status_code == 201:
        return int(r.text), None
    # Return error for logging
    return None, f"API {r.status_code if r else 'No response'}: {r.text[:200] if r else 'Connection failed'}"


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

    r = api_request_with_retry('POST', f'{BASE_URL}/tables/Activity', headers=headers, json=followup_data)

    if r and r.status_code == 201:
        return int(r.text), None
    return None, f"API {r.status_code if r else 'No response'}: {r.text[:200] if r else 'Connection failed'}"


def process_materialbank_import(mb_df, existing_contacts=None, progress_callback=None, dry_run=False, skip_existing=False):
    """
    Full pipeline: Convert MB data, create contacts, activities, and follow-ups.

    For NEW leads: Creates Contact first, then MB Samples activity, then follow-up.
    For EXISTING leads: Creates MB Samples activity linked to existing contact, then follow-up.

    Args:
        mb_df: Material Bank DataFrame
        existing_contacts: Dict of email -> contact info (optional, will fetch if None)
        progress_callback: Function to call with progress updates (msg, pct)
        dry_run: If True, only report what would be done without making changes
        skip_existing: If True, completely skip leads that already have contacts (for re-uploads after failures)

    Returns:
        Dict with results and stats
    """
    results = {
        'leads_processed': 0,
        'customers_created': 0,
        'contacts_created': 0,
        'activities_created': 0,
        'followups_created': 0,
        'existing_updated': 0,
        'skipped_existing': 0,
        'errors': [],
        'details': [],
        'dry_run': dry_run
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

    # Get unique emails (filter out NaN/empty values)
    unique_emails = [e for e in mb_df['Email_Lower'].unique() if pd.notna(e) and e.strip()]
    total_leads = len(unique_emails)

    if total_leads == 0:
        results['errors'].append("No leads to process")
        return results

    for idx, email in enumerate(unique_emails):
        pct = 20 + int(70 * idx / total_leads)

        group = mb_df[mb_df['Email_Lower'] == email]
        if group.empty:
            results['errors'].append(f"No data found for email: {email}")
            continue
        lead_row = group.iloc[0]
        contact_name = f"{lead_row['First Name']} {lead_row['Last Name']}"
        company = lead_row['Company']
        is_existing = email in existing_emails

        # Skip existing contacts entirely if skip_existing is enabled
        if skip_existing and is_existing:
            results['skipped_existing'] += 1
            update_progress(f"Skipping {contact_name} (already exists)...", pct)
            continue

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
        contact_created = False

        if email in existing_contacts:
            contacts_record_id = existing_contacts[email]['RecordID']
        else:
            # NEW LEAD: Create Customer + Contact (linked together)
            first_name = lead_row.get('First Name', '')
            last_name = lead_row.get('Last Name', '')
            phone = lead_row.get('Work Phone', None)
            mobile = lead_row.get('Mobile Phone', None)

            if dry_run:
                # In dry run, simulate lead creation
                results['customers_created'] += 1
                results['contacts_created'] += 1
                contacts_record_id = -1  # Placeholder for dry run
                contact_created = True
            else:
                contact_id, customer_id, lead_error = create_lead(
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    company=company,
                    phone=phone if pd.notna(phone) else None,
                    mobile=mobile if pd.notna(mobile) else None
                )

                if customer_id:
                    results['customers_created'] += 1

                if contact_id:
                    contacts_record_id = contact_id
                    contact_created = True
                    results['contacts_created'] += 1
                    # Add to existing_contacts so duplicates in same batch are handled
                    existing_contacts[email] = {
                        'RecordID': contact_id,
                        'Name': contact_name,
                        'Entity_RecordID': customer_id,
                    }
                else:
                    results['errors'].append(f"Lead creation failed for {contact_name}: {lead_error}")
                    # Continue anyway - activity will be orphaned but we'll log the error

                time.sleep(0.5)  # Rate limiting for lead creation

        # Create MB Samples activity
        if dry_run:
            activity_id = -1  # Placeholder for dry run
            results['activities_created'] += 1
            if is_existing:
                results['existing_updated'] += 1
        else:
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
            else:
                results['errors'].append(f"Activity failed for {contact_name}: {error}")

        # Create follow-up activity (only if we have a contact)
        if contacts_record_id and (dry_run or activity_id):
            if dry_run:
                results['followups_created'] += 1
            else:
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
            'activity_id': activity_id if not dry_run else None,
            'contact_id': contacts_record_id if not dry_run else None,
            'is_existing': is_existing,
            'contact_created': contact_created
        })

        results['leads_processed'] += 1
        time.sleep(0.3)  # Rate limiting

    update_progress("Complete!", 100)
    return results


def process_activities_only(mb_df, existing_contacts, progress_callback=None, dry_run=False):
    """
    Create activities for leads that already have contacts in Method.
    Use this after importing contacts via CSV.

    Args:
        mb_df: Material Bank DataFrame
        existing_contacts: Dict of email -> contact info
        progress_callback: Function for progress updates
        dry_run: If True, only report what would be done

    Returns:
        Dict with results
    """
    results = {
        'activities_created': 0,
        'followups_created': 0,
        'skipped': 0,
        'skipped_details': [],
        'errors': [],
        'details': [],
        'dry_run': dry_run
    }

    def update_progress(msg, pct=None):
        if progress_callback:
            progress_callback(msg, pct)

    # Prepare data
    mb_df = mb_df.copy()
    mb_df['Order Date'] = pd.to_datetime(mb_df['Order Date'], format='mixed', dayfirst=False)
    mb_df['Email_Lower'] = mb_df['Email'].str.lower().str.strip()

    unique_emails = mb_df['Email_Lower'].unique()
    total = len(unique_emails)

    for idx, email in enumerate(unique_emails):
        pct = int(100 * idx / total) if total > 0 else 100
        update_progress(f"Processing {idx+1}/{total}...", pct)

        group = mb_df[mb_df['Email_Lower'] == email]
        lead_row = group.iloc[0]
        contact_name = f"{lead_row['First Name']} {lead_row['Last Name']}"
        company = lead_row['Company']

        # Check if contact exists
        if email not in existing_contacts:
            results['skipped'] += 1
            results['skipped_details'].append({
                'name': contact_name,
                'email': email,
                'company': company
            })
            continue

        contacts_record_id = existing_contacts[email]['RecordID']

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

        if dry_run:
            results['activities_created'] += 1
            results['followups_created'] += 1
        else:
            # Create activity
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

                # Create follow-up
                followup_id, _ = create_followup_activity(
                    parent_activity_id=activity_id,
                    contact_name=contact_name,
                    contact_email=email,
                    contacts_record_id=contacts_record_id
                )
                if followup_id:
                    results['followups_created'] += 1
            else:
                results['errors'].append(f"Activity failed for {contact_name}: {error}")

            time.sleep(0.3)

        results['details'].append({
            'name': contact_name,
            'email': email,
            'company': company,
            'samples': len(samples)
        })

    update_progress("Complete!", 100)
    return results


# =============================================================================
# Cleanup Functions - for fixing orphaned/duplicate activities from failed imports
# =============================================================================

def fetch_all_mb_activities():
    """Fetch all MB Samples activities."""
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
    Returns list of activities to delete (keeps the one with highest RecordID).
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
    for key, acts in by_email_date.items():
        if len(acts) > 1:
            sorted_acts = sorted(acts, key=lambda x: x['RecordID'], reverse=True)
            duplicates_to_delete.extend(sorted_acts[1:])  # Keep highest ID, delete rest

    return duplicates_to_delete


def delete_activity(activity_id):
    """Delete an activity."""
    headers = get_headers()
    r = requests.delete(f'{BASE_URL}/tables/Activity/{activity_id}', headers=headers)
    if r.status_code in (200, 204):
        return True, None
    return False, f"API {r.status_code}: {r.text[:200]}"


def update_activity_contact(activity_id, contacts_record_id):
    """Link an activity to a contact."""
    headers = get_headers(content_type=True)
    r = requests.patch(
        f'{BASE_URL}/tables/Activity/{activity_id}',
        headers=headers,
        json={'Contacts_RecordID': contacts_record_id}
    )
    if r.status_code in (200, 204):
        return True, None
    return False, f"API {r.status_code}: {r.text[:200]}"


def get_contact_by_email(email):
    """
    Query a single contact by email. Returns contact dict or None.
    Much more API-efficient than loading all contacts.
    """
    headers = get_headers()
    email_lower = email.lower().strip()

    # Method uses 'filter' not '$filter'
    r = api_request_with_retry(
        'GET',
        f"{BASE_URL}/tables/Contacts?filter=Email eq '{email_lower}'",
        headers=headers
    )

    if r and r.status_code == 200:
        contacts = r.json().get('value', [])
        if contacts:
            c = contacts[0]
            return {
                'RecordID': c['RecordID'],
                'Entity_RecordID': c.get('Entity_RecordID'),
                'Entity': c.get('Entity'),
                'Name': c.get('Name'),
                'Email': c.get('Email'),
                'FirstName': c.get('FirstName'),
                'LastName': c.get('LastName'),
                'CompanyName': c.get('CompanyName'),
                'Phone': c.get('Phone'),
                'Mobile': c.get('Mobile'),
                'TagList': c.get('TagList'),
            }
    return None


def fix_orphaned_contacts(progress_callback=None, target_emails=None, dry_run=False, csv_data=None, retry_callback=None):
    """
    Fix contacts that were created without Customer entities.

    Method CRM auto-creates a Contact when you create a Customer, so we:
    1. Create Customer (auto-creates Contact)
    2. Update auto-created Contact with TagList and CSV data
    3. Re-link any existing activities from orphan to new Contact
    4. Delete the original orphan Contact

    Args:
        progress_callback: Function for progress updates (msg, pct)
        target_emails: Required - set/list of emails to fix (queries only these, not all contacts)
        dry_run: If True, only report what would be done
        csv_data: Optional dict mapping email -> {company, first_name, last_name, phone, mobile}
                  Used to enrich/correct contact data from the original CSV
        retry_callback: Optional function(attempt, wait_seconds, reason) for retry notifications

    Returns:
        Dict with results
    """
    results = {
        'customers_created': 0,
        'contacts_created': 0,
        'orphans_deleted': 0,
        'activities_relinked': 0,
        'already_linked': 0,
        'not_found': 0,
        'errors': [],
        'details': []
    }

    def update_progress(msg, pct=None):
        if progress_callback:
            progress_callback(msg, pct)

    if not target_emails:
        results['errors'].append("target_emails is required to avoid loading all contacts")
        return results

    # Normalize emails
    emails_to_check = [e.lower().strip() for e in target_emails]
    # Deduplicate while preserving order
    seen = set()
    unique_emails = []
    for e in emails_to_check:
        if e not in seen:
            seen.add(e)
            unique_emails.append(e)

    total = len(unique_emails)
    update_progress(f"Checking {total} emails from CSV...", 0)

    for idx, email in enumerate(unique_emails):
        pct = int(100 * idx / total) if total > 0 else 100
        update_progress(f"Processing {idx+1}/{total}: {email}...", pct)

        # Query this specific contact (1 API call)
        orphan_contact = get_contact_by_email(email)
        time.sleep(0.2)  # Rate limiting

        if not orphan_contact:
            results['not_found'] += 1
            results['details'].append({
                'email': email,
                'status': 'not_found_in_method'
            })
            continue

        # Check if already linked to a customer
        if orphan_contact.get('Entity_RecordID'):
            results['already_linked'] += 1
            results['details'].append({
                'email': email,
                'name': orphan_contact.get('Name'),
                'contact_id': orphan_contact['RecordID'],
                'customer_id': orphan_contact['Entity_RecordID'],
                'status': 'already_linked'
            })
            continue

        # This contact is orphaned - needs fixing
        orphan_id = orphan_contact['RecordID']

        # Get data from CSV if available, otherwise use contact data
        if csv_data and email in csv_data:
            csv_row = csv_data[email]
            first_name = csv_row.get('first_name', '')
            last_name = csv_row.get('last_name', '')
            company = csv_row.get('company', '')
            phone = csv_row.get('phone')
            mobile = csv_row.get('mobile')
        else:
            first_name = orphan_contact.get('FirstName') or ''
            last_name = orphan_contact.get('LastName') or ''
            company = orphan_contact.get('CompanyName') or ''
            phone = orphan_contact.get('Phone')
            mobile = orphan_contact.get('Mobile')

        # Fallback: parse name if not available
        if not first_name and not last_name:
            name_parts = (orphan_contact.get('Name') or '').split(' ', 1)
            first_name = name_parts[0] if name_parts else ''
            last_name = name_parts[1] if len(name_parts) > 1 else ''

        if not company:
            company = f"{first_name} {last_name}".strip() or email

        contact_name = f"{first_name} {last_name}".strip()

        if dry_run:
            results['customers_created'] += 1
            results['contacts_created'] += 1
            results['orphans_deleted'] += 1
            results['details'].append({
                'email': email,
                'name': contact_name,
                'company': company,
                'orphan_id': orphan_id,
                'status': 'would_fix',
                'dry_run': True
            })
            continue

        # Step 1: Create Customer (Method auto-creates Contact)
        customer_id, error = create_customer(
            company=company,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            mobile=mobile,
            retry_callback=retry_callback
        )

        if not customer_id:
            results['errors'].append(f"Failed to create customer for {contact_name}: {error}")
            continue

        results['customers_created'] += 1
        time.sleep(0.3)

        # Step 2: Find the auto-created Contact
        headers = get_headers()
        r = api_request_with_retry(
            'GET',
            f"{BASE_URL}/tables/Contacts?filter=Entity_RecordID eq {customer_id}",
            headers=headers,
            retry_callback=retry_callback
        )

        new_contact_id = None
        if r and r.status_code == 200:
            contacts = r.json().get('value', [])
            if contacts:
                new_contact_id = contacts[0]['RecordID']
                results['contacts_created'] += 1

        if not new_contact_id:
            results['errors'].append(f"Could not find auto-created contact for {contact_name}")
            continue

        time.sleep(0.2)

        # Step 3: Update auto-created Contact with TagList
        headers_json = get_headers(content_type=True)
        r = api_request_with_retry(
            'PATCH',
            f'{BASE_URL}/tables/Contacts/{new_contact_id}',
            headers=headers_json,
            json={'TagList': 'Arazzo'},
            retry_callback=retry_callback
        )
        time.sleep(0.2)

        # Step 4: Find and re-link activities from orphan to new contact
        r = api_request_with_retry(
            'GET',
            f"{BASE_URL}/tables/Activity?filter=Contacts_RecordID eq {orphan_id}",
            headers=headers,
            retry_callback=retry_callback
        )

        if r and r.status_code == 200:
            activities = r.json().get('value', [])
            for act in activities:
                r2 = api_request_with_retry(
                    'PATCH',
                    f"{BASE_URL}/tables/Activity/{act['RecordID']}",
                    headers=headers_json,
                    json={'Contacts_RecordID': new_contact_id},
                    retry_callback=retry_callback
                )
                if r2 and r2.status_code in (200, 204):
                    results['activities_relinked'] += 1
                time.sleep(0.1)

        time.sleep(0.2)

        # Step 5: Delete the orphan contact
        r = api_request_with_retry(
            'DELETE',
            f'{BASE_URL}/tables/Contacts/{orphan_id}',
            headers=headers,
            retry_callback=retry_callback
        )
        if r and r.status_code in (200, 204):
            results['orphans_deleted'] += 1

        results['details'].append({
            'email': email,
            'name': contact_name,
            'company': company,
            'orphan_id': orphan_id,
            'new_contact_id': new_contact_id,
            'customer_id': customer_id,
            'status': 'fixed'
        })

        time.sleep(0.5)  # Rate limiting between contacts

    update_progress("Done!", 100)
    return results


def cleanup_activities(progress_callback=None, target_emails=None):
    """
    Clean up MB Samples activities: remove duplicates and link orphans to contacts.

    Args:
        progress_callback: Function for progress updates (msg, pct)
        target_emails: Optional set of emails to limit cleanup scope

    Returns:
        Dict with results
    """
    results = {
        'duplicates_removed': 0,
        'activities_linked': 0,
        'errors': []
    }

    def update_progress(msg, pct=None):
        if progress_callback:
            progress_callback(msg, pct)

    # Load existing contacts
    update_progress("Loading contacts...", 0)
    existing_contacts = load_existing_contacts()

    # Fetch all MB activities
    update_progress("Fetching activities...", 10)
    all_activities = fetch_all_mb_activities()

    # Filter by target emails if provided
    if target_emails:
        target_lower = {e.lower().strip() for e in target_emails}
        all_activities = [a for a in all_activities
                         if (a.get('ContactEmail') or '').lower().strip() in target_lower]

    # Remove duplicates
    update_progress("Finding duplicates...", 20)
    duplicates = find_duplicate_activities(all_activities)

    for act in duplicates:
        success, error = delete_activity(act['RecordID'])
        if success:
            results['duplicates_removed'] += 1
        else:
            results['errors'].append(f"Delete #{act['RecordID']}: {error}")
        time.sleep(0.2)

    # Re-fetch after deletions
    if duplicates:
        all_activities = fetch_all_mb_activities()
        if target_emails:
            target_lower = {e.lower().strip() for e in target_emails}
            all_activities = [a for a in all_activities
                             if (a.get('ContactEmail') or '').lower().strip() in target_lower]

    # Link orphaned activities to existing contacts
    update_progress("Linking orphans...", 60)
    orphaned = [a for a in all_activities if not a.get('Contacts_RecordID')]

    for act in orphaned:
        email = (act.get('ContactEmail') or '').lower().strip()
        if email and email in existing_contacts:
            contact_id = existing_contacts[email]['RecordID']
            success, error = update_activity_contact(act['RecordID'], contact_id)
            if success:
                results['activities_linked'] += 1
            else:
                results['errors'].append(f"Link #{act['RecordID']}: {error}")
            time.sleep(0.2)

    update_progress("Done!", 100)
    return results
