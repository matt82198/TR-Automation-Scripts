"""
Authentication utilities for Streamlit Cloud deployment.

Uses Streamlit's native OIDC authentication with Google Sign-In.
Requires Streamlit 1.42+ and proper secrets configuration.
"""

import streamlit as st
from typing import Optional, List

# Default authorized domain - employees with this domain get access
AUTHORIZED_DOMAIN = "@thetanneryrow.com"


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
    # Check if we're in Streamlit Cloud with auth enabled
    if not hasattr(st, 'user'):
        # Local development - allow access
        return True

    # Check if user is logged in
    if not st.user.is_logged_in:
        show_login_page()
        return False

    # Check if user is authorized
    user_email = getattr(st.user, 'email', None)
    if not is_user_authorized(user_email):
        show_unauthorized_page(user_email)
        return False

    return True


def show_login_page():
    """Display the login page for unauthenticated users."""
    st.set_page_config(
        page_title="Tannery Row Tools - Login",
        page_icon="🔐",
        layout="centered"
    )

    st.title("🏭 Tannery Row Internal Tools")
    st.markdown("---")

    st.info("Please sign in with your company Google account to access the tools.")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🔑 Sign in with Google", type="primary", use_container_width=True):
            st.login()

    st.markdown("---")
    st.caption("Access is restricted to authorized Tannery Row employees.")


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

    if st.button("🔓 Sign out and try another account"):
        st.logout()


def show_user_info_sidebar():
    """
    Display user info and logout button in the sidebar.
    Call this after authentication check passes.
    """
    if hasattr(st, 'user') and st.user.is_logged_in:
        st.sidebar.markdown("---")
        st.sidebar.markdown(f"**Logged in as:**")
        st.sidebar.markdown(f"📧 {st.user.email}")
        if st.sidebar.button("🚪 Sign out", use_container_width=True):
            st.logout()


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
