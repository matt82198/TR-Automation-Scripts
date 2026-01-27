"""
Authentication utilities for Streamlit deployment.

Supports authentication modes:
1. Password + Email: Simple password gate with email domain verification
2. Streamlit Cloud: Uses native OIDC authentication (st.user, st.login) - paid tier only
3. Local: Bypasses auth for local development

Requires proper secrets configuration in .streamlit/secrets.toml
"""

import streamlit as st
from typing import Optional, List
import os

# Default authorized domain - employees with this domain get access
AUTHORIZED_DOMAIN = "@thetanneryrow.com"


def is_streamlit_cloud() -> bool:
    """Check if running on Streamlit Cloud."""
    # Check environment variables
    if os.environ.get('STREAMLIT_SHARING_MODE') == 'true':
        return True
    if os.environ.get('IS_STREAMLIT_CLOUD') == 'true':
        return True
    if 'streamlit.app' in os.environ.get('HOSTNAME', ''):
        return True
    # Check if secrets are configured (indicates cloud deployment)
    try:
        if hasattr(st, 'secrets') and 'APP_PASSWORD' in st.secrets:
            return True
    except Exception:
        pass
    return False


def get_authorized_emails() -> List[str]:
    """
    Get list of authorized email addresses from secrets.
    Falls back to empty list if not configured.
    """
    try:
        if hasattr(st, 'secrets') and 'authorized_users' in st.secrets:
            return [e.lower() for e in st.secrets.authorized_users.get('emails', [])]
    except Exception:
        pass
    return []


def is_user_authorized(email: str) -> bool:
    """
    Check if a user email is authorized to access the app.

    Authorization rules (in order):
    1. Email ends with authorized domain (@thetanneryrow.com)
    2. Email is in the whitelist from secrets

    Args:
        email: User's email address

    Returns:
        True if authorized, False otherwise
    """
    if not email:
        return False

    email_lower = email.lower().strip()

    # Check domain
    if email_lower.endswith(AUTHORIZED_DOMAIN.lower()):
        return True

    # Check whitelist
    authorized_emails = get_authorized_emails()
    if email_lower in authorized_emails:
        return True

    return False


def check_authentication() -> bool:
    """
    Check if user is authenticated and authorized.

    This should be called at the top of app.py to gate access.

    Returns:
        True if user should proceed, False if blocked
    """
    # Skip auth entirely if SKIP_AUTH is set (for local network access)
    if os.environ.get('SKIP_AUTH', '').lower() == 'true':
        return True

    # Check secrets for SKIP_AUTH
    try:
        if hasattr(st, 'secrets') and st.secrets.get('SKIP_AUTH', '').lower() == 'true':
            return True
    except Exception:
        pass

    # Local development - allow access
    if not is_streamlit_cloud():
        return True

    # Check if already authenticated this session
    if st.session_state.get('authenticated', False):
        return True

    # Show password + email login
    show_password_login_page()
    return False


def show_password_login_page():
    """Display the password + email login page."""
    st.set_page_config(
        page_title="Tannery Row Tools - Login",
        page_icon="🔐",
        layout="centered"
    )

    st.title("🏭 Tannery Row Internal Tools")
    st.markdown("---")

    st.info("Enter your company email and the access password.")

    # Get the app password from secrets
    try:
        app_password = st.secrets.get('APP_PASSWORD', '')
    except Exception:
        app_password = ''

    if not app_password:
        st.error("APP_PASSWORD not configured in secrets.")
        st.stop()

    with st.form("login_form"):
        email = st.text_input("Company Email", placeholder="you@thetanneryrow.com")
        password = st.text_input("Access Password", type="password")
        submitted = st.form_submit_button("Sign In", type="primary", use_container_width=True)

        if submitted:
            email = email.strip().lower()

            # Check email domain
            if not email.endswith(AUTHORIZED_DOMAIN.lower()):
                st.error(f"Only {AUTHORIZED_DOMAIN} email addresses are allowed.")
            # Check password
            elif password != app_password:
                st.error("Incorrect password.")
            else:
                # Success - set session state
                st.session_state['authenticated'] = True
                st.session_state['user_email'] = email
                st.rerun()

    st.markdown("---")
    st.caption("Access is restricted to Tannery Row employees.")


def show_unauthorized_page(email: Optional[str] = None):
    """Display the unauthorized access page."""
    st.set_page_config(
        page_title="Access Denied",
        page_icon="🚫",
        layout="centered"
    )

    st.title("🚫 Access Denied")
    st.markdown("---")

    if email:
        st.error(f"Your account ({email}) is not authorized to access this application.")
    else:
        st.error("Your account is not authorized to access this application.")

    st.markdown("""
    **Need access?** Contact your administrator to be added to the authorized users list.
    """)

    # Logout button
    if st.button("Sign out and try again"):
        st.session_state['authenticated'] = False
        st.session_state['user_email'] = ''
        st.rerun()


def show_user_info_sidebar():
    """
    Display user info and logout button in the sidebar.
    Call this after authentication check passes.
    """
    if st.session_state.get('authenticated', False):
        email = st.session_state.get('user_email', 'Unknown')
        st.sidebar.markdown("---")
        st.sidebar.markdown(f"**Logged in as:**")
        st.sidebar.markdown(f"{email}")
        if st.sidebar.button("Sign out", use_container_width=True):
            st.session_state['authenticated'] = False
            st.session_state['user_email'] = ''
            st.rerun()


def get_secret(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Get a secret value, with fallback to environment variable.

    This allows the same code to work locally (env vars) and on
    Streamlit Cloud (secrets.toml).

    Args:
        key: The secret key name
        default: Default value if not found

    Returns:
        The secret value or default
    """
    import os

    # Try Streamlit secrets first
    try:
        if hasattr(st, 'secrets') and key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass

    # Fall back to environment variable
    return os.environ.get(key, default)
