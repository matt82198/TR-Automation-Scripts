"""
Authentication utilities for Streamlit deployment.

Supports two authentication modes:
1. Streamlit Cloud: Uses native OIDC authentication (st.user, st.login)
2. Local/Tunnel: Uses streamlit-google-auth library

Requires proper secrets configuration in .streamlit/secrets.toml
"""

import streamlit as st
from typing import Optional, List
import os

# Allow OAuth scope changes (Google sometimes adds scopes)
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = 'true'

# Default authorized domain - employees with this domain get access
AUTHORIZED_DOMAIN = "@thetanneryrow.com"

# Try to import streamlit-google-auth for local OAuth
try:
    from streamlit_google_auth import Authenticate
    LOCAL_AUTH_AVAILABLE = True
except ImportError:
    LOCAL_AUTH_AVAILABLE = False


def is_streamlit_cloud() -> bool:
    """Check if running on Streamlit Cloud (where native st.user actually works)."""
    # Streamlit Cloud sets specific environment variables
    # st.user exists in newer Streamlit versions but only works on Cloud
    return os.environ.get('STREAMLIT_SHARING_MODE') == 'true' or \
           os.environ.get('IS_STREAMLIT_CLOUD') == 'true' or \
           'streamlit.app' in os.environ.get('HOSTNAME', '')


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


def get_local_authenticator():
    """Get or create the local OAuth authenticator."""
    if 'authenticator' not in st.session_state:
        try:
            from pathlib import Path
            import json
            import tempfile

            auth_config = st.secrets.get('auth', {})

            # Path to credentials file
            creds_path = Path(__file__).parent.parent / '.streamlit' / 'google_oauth_credentials.json'

            # If credentials file doesn't exist (Streamlit Cloud), create from secrets
            if not creds_path.exists():
                # Create credentials JSON from secrets
                creds_data = {
                    "web": {
                        "client_id": auth_config.get('client_id', ''),
                        "client_secret": auth_config.get('client_secret', ''),
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [auth_config.get('redirect_uri', 'http://localhost:8501')]
                    }
                }
                # Write to temp file
                temp_creds = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
                json.dump(creds_data, temp_creds)
                temp_creds.close()
                creds_path = temp_creds.name

            st.session_state.authenticator = Authenticate(
                secret_credentials_path=str(creds_path),
                cookie_name='tr_tools_auth',
                cookie_key=auth_config.get('cookie_secret', 'default_secret_key_change_me'),
                redirect_uri=auth_config.get('redirect_uri', 'http://localhost:8501'),
            )
        except Exception as e:
            st.error(f"Failed to initialize authenticator: {e}")
            return None
    return st.session_state.authenticator


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

    # Mode 1: Streamlit Cloud with native auth
    if is_streamlit_cloud():
        if not st.user.is_logged_in:
            show_login_page()
            return False

        user_email = getattr(st.user, 'email', None)
        if not is_user_authorized(user_email):
            show_unauthorized_page(user_email)
            return False
        return True

    # Mode 2: Local/Tunnel with streamlit-google-auth
    if LOCAL_AUTH_AVAILABLE:
        authenticator = get_local_authenticator()
        if authenticator is None:
            st.error("Authentication not configured properly.")
            return False

        # Check authentication status
        authenticator.check_authentification()

        # Get login status from session state
        if not st.session_state.get('connected', False):
            show_local_login_page(authenticator)
            return False

        # Check authorization
        user_email = st.session_state.get('user_info', {}).get('email')
        if not is_user_authorized(user_email):
            show_unauthorized_page(user_email)
            return False

        return True

    # No auth available - block access when REQUIRE_AUTH is set
    if os.environ.get('REQUIRE_AUTH', '').lower() == 'true':
        st.error("Authentication required but not available. Please install streamlit-google-auth.")
        return False

    # Local development without auth requirement - allow access
    return True


def show_login_page():
    """Display the login page for unauthenticated users (Streamlit Cloud)."""
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


def show_local_login_page(authenticator):
    """Display the login page for local/tunnel deployment."""
    st.set_page_config(
        page_title="Tannery Row Tools - Login",
        page_icon="🔐",
        layout="centered"
    )

    st.title("🏭 Tannery Row Internal Tools")
    st.markdown("---")

    st.info("Please sign in with your company Google account to access the tools.")

    # Use streamlit-google-auth login button
    authenticator.login()

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

    # Logout button for both modes
    if is_streamlit_cloud():
        if st.button("🔓 Sign out and try another account"):
            st.logout()
    elif LOCAL_AUTH_AVAILABLE and 'authenticator' in st.session_state:
        if st.button("🔓 Sign out and try another account"):
            st.session_state.authenticator.logout()


def show_user_info_sidebar():
    """
    Display user info and logout button in the sidebar.
    Call this after authentication check passes.
    """
    # Streamlit Cloud mode
    if is_streamlit_cloud() and st.user.is_logged_in:
        st.sidebar.markdown("---")
        st.sidebar.markdown(f"**Logged in as:**")
        st.sidebar.markdown(f"📧 {st.user.email}")
        if st.sidebar.button("🚪 Sign out", use_container_width=True):
            st.logout()
    # Local/Tunnel mode
    elif LOCAL_AUTH_AVAILABLE and st.session_state.get('connected', False):
        user_info = st.session_state.get('user_info', {})
        email = user_info.get('email', 'Unknown')
        st.sidebar.markdown("---")
        st.sidebar.markdown(f"**Logged in as:**")
        st.sidebar.markdown(f"📧 {email}")
        if st.sidebar.button("🚪 Sign out", use_container_width=True):
            if 'authenticator' in st.session_state:
                st.session_state.authenticator.logout()


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
