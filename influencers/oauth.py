"""
OAuth integration for Facebook, Instagram, and TikTok.
Allows influencers to connect their accounts for automatic verification.
"""
import requests
from django.shortcuts import redirect
from django.contrib import messages
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import logging
import base64
import secrets

logger = logging.getLogger(__name__)


class FacebookOAuth:
    """Facebook OAuth integration for connecting Facebook Pages and Instagram accounts."""
    
    BASE_URL = "https://www.facebook.com/v18.0/dialog/oauth"
    TOKEN_URL = "https://graph.facebook.com/v18.0/oauth/access_token"
    API_BASE = "https://graph.facebook.com/v18.0"
    
    # Required permissions for Facebook Pages and Instagram Business accounts
    # IMPORTANT: These permissions must be added in your Facebook App settings FIRST:
    # 
    # STEP 1: Add permissions in Facebook App
    # 1. Go to https://developers.facebook.com/apps/
    # 2. Select your app → "App Review" → "Permissions and Features"
    # 3. Click "Add a Permission" button
    # 4. Add these permissions one by one:
    #    - pages_show_list (to list user's pages)
    #    - pages_read_engagement (to read page metrics including follower counts)
    #
    # STEP 2: For Development Mode
    # - These permissions work in Development mode without App Review
    # - You can only test with your own account or test users
    # - Go to "Roles" → "Test Users" to add test users
    #
    # STEP 3: For Production
    # - Submit for App Review when ready for production
    # - Some permissions may require business verification
    #
    # Note: We access Instagram Business accounts through their connected Facebook Pages
    # using the pages permissions. Instagram-specific permissions are deprecated.
    FACEBOOK_PERMISSIONS = [
        "public_profile",  # Basic profile (always available, no review needed)
        "pages_show_list",  # List user's Facebook Pages (required for Instagram access)
        "pages_read_engagement",  # Read page metrics including follower counts
        # Note: instagram_basic and instagram_manage_insights are deprecated
        # We access Instagram through Facebook Pages API instead
    ]
    
    @classmethod
    def get_authorization_url(cls, redirect_uri, state=None):
        """Generate Facebook OAuth authorization URL."""
        app_id = getattr(settings, 'FACEBOOK_APP_ID', None)
        if not app_id:
            raise ValueError("FACEBOOK_APP_ID not configured in settings")
        
        params = {
            'client_id': app_id,
            'redirect_uri': redirect_uri,
            'scope': ','.join(cls.FACEBOOK_PERMISSIONS),
            'response_type': 'code',
        }
        if state:
            params['state'] = state
        
        url = f"{cls.BASE_URL}?{'&'.join([f'{k}={v}' for k, v in params.items()])}"
        return url
    
    @classmethod
    def exchange_code_for_token(cls, code, redirect_uri):
        """Exchange authorization code for access token."""
        app_id = getattr(settings, 'FACEBOOK_APP_ID', None)
        app_secret = getattr(settings, 'FACEBOOK_APP_SECRET', None)
        
        if not app_id or not app_secret:
            raise ValueError("Facebook OAuth credentials not configured")
        
        params = {
            'client_id': app_id,
            'client_secret': app_secret,
            'redirect_uri': redirect_uri,
            'code': code,
        }
        
        response = requests.get(cls.TOKEN_URL, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('access_token'), data.get('expires_in')
        else:
            error_data = response.json() if response.content else {}
            error_message = error_data.get('error', {}).get('message', 'Unknown error')
            raise Exception(f"Token exchange failed: {error_message}")
    
    @classmethod
    def get_user_pages(cls, access_token):
        """Get list of Facebook Pages the user manages."""
        url = f"{cls.API_BASE}/me/accounts"
        params = {
            'access_token': access_token,
            'fields': 'id,name,username,instagram_business_account',
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('data', [])
        else:
            logger.error(f"Failed to get user pages: {response.status_code}")
            return []
    
    @classmethod
    def get_page_info(cls, page_id, access_token):
        """Get Facebook Page information including follower count."""
        url = f"{cls.API_BASE}/{page_id}"
        params = {
            'access_token': access_token,
            'fields': 'id,name,username,followers_count,instagram_business_account',
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Failed to get page info: {response.status_code}")
            return None
    
    @classmethod
    def get_instagram_account_info(cls, instagram_account_id, access_token):
        """Get Instagram Business Account information including follower count."""
        url = f"{cls.API_BASE}/{instagram_account_id}"
        params = {
            'access_token': access_token,
            'fields': 'id,username,followers_count',
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Failed to get Instagram account info: {response.status_code}")
            return None
    
    @classmethod
    def exchange_for_long_lived_token(cls, short_lived_token):
        """Exchange short-lived token for long-lived token (60 days)."""
        app_id = getattr(settings, 'FACEBOOK_APP_ID', None)
        app_secret = getattr(settings, 'FACEBOOK_APP_SECRET', None)
        
        if not app_id or not app_secret:
            raise ValueError("Facebook OAuth credentials not configured")
        
        url = f"{cls.API_BASE}/oauth/access_token"
        params = {
            'grant_type': 'fb_exchange_token',
            'client_id': app_id,
            'client_secret': app_secret,
            'fb_exchange_token': short_lived_token,
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('access_token'), data.get('expires_in')
        else:
            error_data = response.json() if response.content else {}
            error_message = error_data.get('error', {}).get('message', 'Unknown error')
            raise Exception(f"Token exchange failed: {error_message}")


class TikTokOAuth:
    """TikTok OAuth integration using TikTok Login Kit."""
    
    BASE_URL = "https://www.tiktok.com/v2/auth/authorize"
    TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
    API_BASE = "https://open.tiktokapis.com/v2"
    
    # Required scopes for follower count
    SCOPES = [
        "user.info.basic",  # Basic user info
        "user.info.stats",  # Follower count and stats
    ]
    
    @classmethod
    def get_authorization_url(cls, redirect_uri, state=None):
        """Generate TikTok OAuth authorization URL."""
        client_key = getattr(settings, 'TIKTOK_CLIENT_KEY', None)
        if not client_key:
            raise ValueError("TIKTOK_CLIENT_KEY not configured in settings")
        
        if not state:
            state = secrets.token_urlsafe(32)
        
        params = {
            'client_key': client_key,
            'redirect_uri': redirect_uri,
            'scope': ','.join(cls.SCOPES),
            'response_type': 'code',
            'state': state,
        }
        
        url = f"{cls.BASE_URL}?{'&'.join([f'{k}={v}' for k, v in params.items()])}"
        return url, state
    
    @classmethod
    def exchange_code_for_token(cls, code, redirect_uri):
        """Exchange authorization code for access token."""
        client_key = getattr(settings, 'TIKTOK_CLIENT_KEY', None)
        client_secret = getattr(settings, 'TIKTOK_CLIENT_SECRET', None)
        
        if not client_key or not client_secret:
            raise ValueError("TikTok OAuth credentials not configured")
        
        # TikTok requires base64 encoded client_key:client_secret
        credentials = f"{client_key}:{client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {encoded_credentials}"
        }
        
        data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': redirect_uri,
        }
        
        response = requests.post(cls.TOKEN_URL, headers=headers, data=data, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            access_token = data.get('access_token')
            expires_in = data.get('expires_in', 3600)  # Default 1 hour
            refresh_token = data.get('refresh_token')
            return access_token, expires_in, refresh_token
        else:
            error_data = response.json() if response.content else {}
            error_message = error_data.get('error_description', error_data.get('error', 'Unknown error'))
            raise Exception(f"Token exchange failed: {error_message}")
    
    @classmethod
    def refresh_access_token(cls, refresh_token):
        """Refresh access token using refresh token."""
        client_key = getattr(settings, 'TIKTOK_CLIENT_KEY', None)
        client_secret = getattr(settings, 'TIKTOK_CLIENT_SECRET', None)
        
        if not client_key or not client_secret:
            raise ValueError("TikTok OAuth credentials not configured")
        
        credentials = f"{client_key}:{client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {encoded_credentials}"
        }
        
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
        }
        
        response = requests.post(cls.TOKEN_URL, headers=headers, data=data, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            access_token = data.get('access_token')
            expires_in = data.get('expires_in', 3600)
            refresh_token = data.get('refresh_token')
            return access_token, expires_in, refresh_token
        else:
            error_data = response.json() if response.content else {}
            error_message = error_data.get('error_description', error_data.get('error', 'Unknown error'))
            raise Exception(f"Token refresh failed: {error_message}")
    
    @classmethod
    def get_user_info(cls, access_token, open_id=None):
        """
        Get TikTok user information including follower count.
        Note: TikTok API v2 requires open_id in the request body for user/info endpoint.
        If open_id is not provided, we'll try to get it from the token.
        """
        url = f"{cls.API_BASE}/user/info/"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        # TikTok API v2 requires open_id in request body
        # If we don't have open_id yet, we need to get it from the token response
        # For now, we'll use the fields parameter and let TikTok return what it can
        params = {
            "fields": "open_id,union_id,avatar_url,display_name,bio_description,profile_deep_link,is_verified,follower_count,following_count,likes_count,video_count"
        }
        
        # If open_id is provided, include it in the request body
        if open_id:
            import json
            body = {
                "open_id": open_id,
                "fields": params["fields"].split(",")
            }
            response = requests.post(url, headers=headers, json=body, timeout=10)
        else:
            # Try GET request (may not work for all endpoints, but worth trying)
            response = requests.get(url, headers=headers, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            # TikTok API v2 returns data in different formats
            if 'data' in data:
                user_info = data.get('data', {}).get('user', {})
                if user_info:
                    return user_info
                # Sometimes data is directly in data
                if isinstance(data.get('data'), dict) and 'open_id' in data.get('data', {}):
                    return data.get('data', {})
            # Fallback: return the entire data if structure is different
            return data
        else:
            error_data = response.json() if response.content else {}
            error_message = error_data.get('error', {}).get('message', error_data.get('error_description', 'Unknown error'))
            logger.error(f"Failed to get TikTok user info: {error_message} (Status: {response.status_code})")
            return None
