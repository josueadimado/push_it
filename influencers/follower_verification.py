"""
Follower count verification service.
Fetches actual follower counts from platform APIs to verify user-provided counts.
Supports both official APIs and public scraping as fallback.
"""
import re
import requests
from typing import Optional, Dict
from django.conf import settings
import logging
from bs4 import BeautifulSoup
import json

logger = logging.getLogger(__name__)


class FollowerVerificationResult:
    """Result of follower count verification."""
    
    def __init__(self, verified: bool, actual_count: Optional[int] = None, 
                 user_count: int = 0, discrepancy: int = 0, 
                 method: str = "api", error: Optional[str] = None):
        self.verified = verified
        self.actual_count = actual_count
        self.user_count = user_count
        self.discrepancy = discrepancy  # Difference between actual and user-provided
        self.method = method  # 'api', 'scrape', 'manual'
        self.error = error


class TikTokFollowerVerifier:
    """Fetch TikTok follower count from TikTok Login Kit API."""
    
    @staticmethod
    def fetch_follower_count(handle: str, access_token: str = None, open_id: str = None) -> Optional[int]:
        """
        Fetch TikTok follower count using TikTok Login Kit API.
        
        Requires OAuth access token from TikTok Login Kit.
        """
        try:
            # If we have OAuth token, use TikTok API
            if access_token:
                from .oauth import TikTokOAuth
                user_info = TikTokOAuth.get_user_info(access_token)
                if user_info:
                    follower_count = user_info.get('follower_count')
                    if follower_count is not None:
                        return int(follower_count)
            
            # Fallback: Try to get from settings (admin API key)
            tiktok_api_key = getattr(settings, 'TIKTOK_API_KEY', None)
            if tiktok_api_key and open_id:
                # TikTok Business API (if available)
                api_url = f"https://open.tiktokapis.com/v2/research/user/info/"
                headers = {
                    "Authorization": f"Bearer {tiktok_api_key}",
                    "Content-Type": "application/json"
                }
                params = {
                    "fields": "follower_count",
                    "open_id": open_id
                }
                response = requests.get(api_url, headers=headers, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    follower_count = data.get('data', {}).get('follower_count')
                    if follower_count is not None:
                        return int(follower_count)
            
            # No API access available
            logger.warning(f"TikTok API access not available for @{handle}. Connect via OAuth for automatic verification.")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching TikTok followers for @{handle}: {e}")
            return None
    
    @classmethod
    def verify(cls, handle: str, user_provided_count: int, access_token: str = None, open_id: str = None) -> FollowerVerificationResult:
        """Verify TikTok follower count."""
        actual_count = cls.fetch_follower_count(handle, access_token=access_token, open_id=open_id)
        
        if actual_count is None:
            # Can't verify - flag for manual review
            return FollowerVerificationResult(
                verified=False,
                user_count=user_provided_count,
                method="manual",
                error="Unable to fetch follower count automatically"
            )
        
        discrepancy = abs(actual_count - user_provided_count)
        # Allow 5% discrepancy (accounts for real-time changes)
        allowed_discrepancy = max(100, user_provided_count * 0.05)
        
        verified = discrepancy <= allowed_discrepancy
        
        return FollowerVerificationResult(
            verified=verified,
            actual_count=actual_count,
            user_count=user_provided_count,
            discrepancy=discrepancy,
            method="api"
        )


class InstagramFollowerVerifier:
    """Fetch Instagram follower count from Instagram Graph API."""
    
    @staticmethod
    def fetch_follower_count(handle: str, account_id: str = None, access_token: str = None) -> Optional[int]:
        """
        Fetch Instagram follower count using Instagram Graph API.
        
        Requires:
        - Facebook App ID and App Secret
        - Instagram Business Account connected to Facebook Page
        - Long-lived access token OR User access token
        
        Args:
            handle: Instagram username (without @)
            account_id: Instagram Business Account ID (optional, will try to find if not provided)
        
        Steps:
        1. Get Instagram Business Account ID (if not provided)
        2. Fetch follower count from Graph API
        """
        try:
            # Use provided access_token (from OAuth) or fallback to settings
            if not access_token:
                access_token = getattr(settings, 'INSTAGRAM_ACCESS_TOKEN', None)
            
            facebook_app_id = getattr(settings, 'FACEBOOK_APP_ID', None)
            facebook_app_secret = getattr(settings, 'FACEBOOK_APP_SECRET', None)
            facebook_page_id = getattr(settings, 'FACEBOOK_PAGE_ID', None)
            
            if not access_token:
                logger.warning("Instagram access token not configured. Add INSTAGRAM_ACCESS_TOKEN to .env or connect via OAuth")
                return None
            
            # Remove @ if present
            handle = handle.lstrip('@')
            
            # If account_id is not provided, try multiple methods to find it
            if not account_id:
                # Method 1: Get from Facebook Page (if page_id is configured)
                if facebook_page_id:
                    account_id = InstagramFollowerVerifier._get_account_id_from_page(
                        facebook_page_id, access_token
                    )
                    # Verify the username matches
                    if account_id:
                        account_info = InstagramFollowerVerifier._get_account_info(account_id, access_token)
                        if account_info and account_info.get('username', '').lower() != handle.lower():
                            # Username doesn't match, try other methods
                            account_id = None
                
                # Method 2: Search through user's Facebook Pages
                if not account_id:
                    account_id = InstagramFollowerVerifier._search_instagram_by_username(
                        handle, access_token
                    )
                
                # Method 3: Try Instagram Basic Display API (for personal accounts)
                if not account_id:
                    account_id = InstagramFollowerVerifier._try_basic_display_api(
                        handle, access_token
                    )
            
            # If we still don't have account_id, try third-party API, then public scraping
            if not account_id:
                # Try RapidAPI first (if configured)
                rapidapi_count = InstagramFollowerVerifier._rapidapi_fetch(handle)
                if rapidapi_count:
                    logger.info(f"Successfully fetched Instagram followers via RapidAPI for @{handle}: {rapidapi_count}")
                    return rapidapi_count
                
                # Fallback to public scraping
                logger.info(f"Instagram API method failed for @{handle}, trying public scraping...")
                scraped_count = InstagramFollowerVerifier._scrape_follower_count(handle)
                if scraped_count:
                    return scraped_count
                
                logger.warning(
                    f"Instagram account ID not found for @{handle}. "
                    "Instagram Graph API requires Business Account ID. "
                    "Third-party API and public scraping also failed. The account will be flagged for manual review."
                )
                return None
            
            # Fetch follower count from Instagram Graph API
            graph_url = f"https://graph.facebook.com/v18.0/{account_id}"
            params = {
                'fields': 'followers_count,username',
                'access_token': access_token
            }
            
            response = requests.get(graph_url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                followers_count = data.get('followers_count')
                if followers_count is not None:
                    return int(followers_count)
                else:
                    logger.warning(f"No followers_count in response for Instagram account {account_id}")
                    return None
            elif response.status_code == 190:  # Invalid OAuth access token
                logger.error("Invalid Instagram access token. Token may have expired.")
                return None
            else:
                error_data = response.json() if response.content else {}
                error_message = error_data.get('error', {}).get('message', 'Unknown error')
                logger.error(f"Instagram API error {response.status_code}: {error_message}")
                return None
            
        except Exception as e:
            logger.error(f"Error fetching Instagram followers for @{handle}: {e}")
            return None
    
    @staticmethod
    def _get_account_id_from_page(page_id: str, access_token: str) -> Optional[str]:
        """Get Instagram Business Account ID from Facebook Page ID."""
        try:
            graph_url = f"https://graph.facebook.com/v18.0/{page_id}"
            params = {
                'fields': 'instagram_business_account',
                'access_token': access_token
            }
            response = requests.get(graph_url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                instagram_account = data.get('instagram_business_account')
                if instagram_account:
                    return instagram_account.get('id')
            return None
        except Exception as e:
            logger.error(f"Error getting Instagram account from page {page_id}: {e}")
            return None
    
    @staticmethod
    def _get_account_info(account_id: str, access_token: str) -> Optional[dict]:
        """Get Instagram account info by account ID."""
        try:
            graph_url = f"https://graph.facebook.com/v18.0/{account_id}"
            params = {
                'fields': 'id,username,followers_count',
                'access_token': access_token
            }
            response = requests.get(graph_url, params=params, timeout=10)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"Error getting Instagram account info for {account_id}: {e}")
            return None
    
    @staticmethod
    def _search_instagram_by_username(username: str, access_token: str) -> Optional[str]:
        """
        Search for Instagram Business Account by username.
        This searches through all Facebook Pages the user has access to.
        """
        try:
            # Get all pages the user has access to
            pages_url = "https://graph.facebook.com/v18.0/me/accounts"
            params = {
                'access_token': access_token,
                'fields': 'id,name,instagram_business_account',
                'limit': 100
            }
            
            response = requests.get(pages_url, params=params, timeout=10)
            if response.status_code != 200:
                return None
            
            data = response.json()
            pages = data.get('data', [])
            
            # Search through pages for matching Instagram account
            for page in pages:
                instagram_account = page.get('instagram_business_account')
                if instagram_account:
                    account_id = instagram_account.get('id')
                    # Verify username matches
                    account_info = InstagramFollowerVerifier._get_account_info(account_id, access_token)
                    if account_info and account_info.get('username', '').lower() == username.lower():
                        return account_id
            
            return None
        except Exception as e:
            logger.error(f"Error searching Instagram by username {username}: {e}")
            return None
    
    @staticmethod
    def _try_basic_display_api(username: str, access_token: str) -> Optional[str]:
        """
        Try Instagram Basic Display API (for personal accounts).
        Note: This requires a different type of access token.
        """
        try:
            # Instagram Basic Display API endpoint
            url = "https://graph.instagram.com/me"
            params = {
                'fields': 'id,username',
                'access_token': access_token
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                # Check if username matches
                if data.get('username', '').lower() == username.lower():
                    return data.get('id')
            return None
        except Exception as e:
            # Basic Display API might not work with Graph API token
            return None
    
    @staticmethod
    def _rapidapi_fetch(username: str) -> Optional[int]:
        """
        Fetch Instagram follower count using RapidAPI.
        Requires RAPIDAPI_KEY in settings.
        
        Uses Instagram Scraper API2 from RapidAPI marketplace.
        """
        try:
            rapidapi_key = getattr(settings, 'RAPIDAPI_KEY', None)
            if not rapidapi_key:
                return None
            
            # Try Instagram Scraper API2 (most popular on RapidAPI)
            url = "https://instagram-scraper-api2.p.rapidapi.com/userinfo"
            headers = {
                "X-RapidAPI-Key": rapidapi_key,
                "X-RapidAPI-Host": "instagram-scraper-api2.p.rapidapi.com"
            }
            params = {"username_or_id_or_url": username}
            
            response = requests.get(url, headers=headers, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                # Extract follower count from response (structure may vary by API)
                if 'data' in data:
                    user_data = data['data']
                    # Try different possible field names
                    follower_count = (
                        user_data.get('edge_followed_by', {}).get('count') or
                        user_data.get('follower_count') or
                        user_data.get('followers') or
                        user_data.get('followers_count')
                    )
                    if follower_count:
                        return int(follower_count)
                # Alternative response structure
                follower_count = data.get('follower_count') or data.get('followers')
                if follower_count:
                    return int(follower_count)
            
            return None
        except Exception as e:
            logger.debug(f"RapidAPI fetch failed for @{username}: {e}")
            return None
    
    @staticmethod
    def _scrape_follower_count(username: str) -> Optional[int]:
        """
        Scrape Instagram follower count from public profile page.
        This is a fallback method when API access is not available.
        
        Note: Instagram may block scraping attempts. Use with caution.
        """
        try:
            url = f"https://www.instagram.com/{username}/"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
            }
            
            response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
            
            if response.status_code != 200:
                logger.debug(f"Instagram scraping failed: HTTP {response.status_code}")
                return None
            
            # Instagram embeds JSON data in script tags
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Method 1: Look for JSON data in script tags (new format)
            scripts = soup.find_all('script')
            for script in scripts:
                if not script.string:
                    continue
                
                script_text = script.string
                
                # Try to find _sharedData
                if 'window._sharedData' in script_text:
                    try:
                        json_text = script_text.split('window._sharedData = ')[1].split(';</script>')[0].rstrip(';')
                        data = json.loads(json_text)
                        user_data = data.get('entry_data', {}).get('ProfilePage', [{}])[0].get('graphql', {}).get('user', {})
                        if user_data:
                            follower_count = user_data.get('edge_followed_by', {}).get('count')
                            if follower_count:
                                logger.info(f"Successfully scraped Instagram followers for @{username}: {follower_count}")
                                return int(follower_count)
                    except (json.JSONDecodeError, IndexError, KeyError) as e:
                        logger.debug(f"Error parsing _sharedData: {e}")
                        continue
                
                # Try to find additional_data_react (newer format)
                if 'additional_data_react' in script_text or 'ProfilePage' in script_text:
                    try:
                        # Look for follower count in the script
                        # Pattern: "edge_followed_by":{"count":12345}
                        match = re.search(r'"edge_followed_by":\s*\{\s*"count":\s*(\d+)', script_text)
                        if match:
                            count = int(match.group(1))
                            logger.info(f"Successfully scraped Instagram followers for @{username}: {count}")
                            return count
                    except Exception as e:
                        logger.debug(f"Error parsing additional_data: {e}")
                        continue
            
            # Method 2: Look for meta tags with follower info
            meta_tags = soup.find_all('meta')
            for meta in meta_tags:
                content = meta.get('content', '')
                property_attr = meta.get('property', '')
                # Look for follower-related meta tags
                if 'followers' in content.lower() or 'followers' in property_attr.lower():
                    numbers = re.findall(r'\d+', content.replace(',', '').replace('.', ''))
                    if numbers:
                        count = int(numbers[0])
                        if count > 0:
                            logger.info(f"Found Instagram followers in meta tag for @{username}: {count}")
                            return count
            
            # Method 3: Look in page text for follower count
            page_text = soup.get_text()
            # Pattern: "X followers" or "X,XXX followers"
            matches = re.findall(r'(\d+(?:,\d+)*)\s+followers?', page_text, re.IGNORECASE)
            if matches:
                # Get the largest number (most likely to be the main follower count)
                numbers = [int(m.replace(',', '')) for m in matches]
                if numbers:
                    count = max(numbers)
                    logger.info(f"Found Instagram followers in page text for @{username}: {count}")
                    return count
            
            logger.debug(f"Could not find follower count in Instagram page for @{username}")
            return None
            
        except Exception as e:
            logger.error(f"Error scraping Instagram followers for @{username}: {e}")
            return None
    
    @classmethod
    def verify(cls, handle: str, user_provided_count: int, account_id: str = None) -> FollowerVerificationResult:
        """
        Verify Instagram follower count.
        
        This will try to automatically find the Instagram Business Account ID
        by searching through connected Facebook Pages. If found, it verifies
        the follower count. If not found, it flags for manual review.
        """
        actual_count = cls.fetch_follower_count(handle, account_id)
        
        if actual_count is None:
            return FollowerVerificationResult(
                verified=False,
                user_count=user_provided_count,
                method="manual",
                error="Unable to fetch follower count automatically. Instagram requires Business Account ID. Please ensure your Instagram account is connected to a Facebook Page, or contact support for manual verification."
            )
        
        discrepancy = abs(actual_count - user_provided_count)
        allowed_discrepancy = max(100, user_provided_count * 0.05)
        
        verified = discrepancy <= allowed_discrepancy
        
        return FollowerVerificationResult(
            verified=verified,
            actual_count=actual_count,
            user_count=user_provided_count,
            discrepancy=discrepancy,
            method="api"
        )


class YouTubeFollowerVerifier:
    """Fetch YouTube subscriber count from API."""
    
    @staticmethod
    def fetch_follower_count(handle: str) -> Optional[int]:
        """
        Fetch YouTube subscriber count using YouTube Data API v3.
        
        This is the most reliable method as YouTube has a public API.
        Requires: YouTube Data API key
        """
        try:
            api_key = getattr(settings, 'YOUTUBE_API_KEY', None)
            if not api_key:
                logger.warning("YouTube API key not configured")
                return None
            
            # Try to get channel by handle
            # First, get channel ID from handle
            search_url = "https://www.googleapis.com/youtube/v3/search"
            params = {
                'part': 'snippet',
                'q': handle,
                'type': 'channel',
                'key': api_key,
                'maxResults': 1
            }
            
            response = requests.get(search_url, params=params, timeout=10)
            if response.status_code != 200:
                logger.error(f"YouTube API error: {response.status_code}")
                return None
            
            data = response.json()
            if not data.get('items'):
                return None
            
            channel_id = data['items'][0]['id']['channelId']
            
            # Get channel statistics
            stats_url = "https://www.googleapis.com/youtube/v3/channels"
            params = {
                'part': 'statistics',
                'id': channel_id,
                'key': api_key
            }
            
            response = requests.get(stats_url, params=params, timeout=10)
            if response.status_code != 200:
                return None
            
            data = response.json()
            if data.get('items'):
                subscriber_count = int(data['items'][0]['statistics'].get('subscriberCount', 0))
                return subscriber_count
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching YouTube subscribers for @{handle}: {e}")
            return None
    
    @classmethod
    def verify(cls, handle: str, user_provided_count: int) -> FollowerVerificationResult:
        """Verify YouTube subscriber count."""
        actual_count = cls.fetch_follower_count(handle)
        
        if actual_count is None:
            return FollowerVerificationResult(
                verified=False,
                user_count=user_provided_count,
                method="manual",
                error="Unable to fetch subscriber count automatically"
            )
        
        discrepancy = abs(actual_count - user_provided_count)
        allowed_discrepancy = max(50, user_provided_count * 0.05)  # YouTube counts change frequently
        
        verified = discrepancy <= allowed_discrepancy
        
        return FollowerVerificationResult(
            verified=verified,
            actual_count=actual_count,
            user_count=user_provided_count,
            discrepancy=discrepancy,
            method="api"
        )


class FacebookFollowerVerifier:
    """Fetch Facebook Page follower count from Facebook Graph API."""
    
    @staticmethod
    def fetch_follower_count(handle: str, page_id: str = None, access_token: str = None) -> Optional[int]:
        """
        Fetch Facebook Page follower count using Facebook Graph API.
        
        Requires:
        - Facebook App ID and App Secret
        - Page Access Token with pages_read_engagement permission
        - Facebook Page ID (or will try to find from handle)
        
        Args:
            handle: Facebook Page username (without @)
            page_id: Facebook Page ID (optional, will try to find if not provided)
        """
        try:
            # Use provided access_token (from OAuth) or fallback to settings
            if not access_token:
                access_token = getattr(settings, 'FACEBOOK_ACCESS_TOKEN', None)
            
            facebook_app_id = getattr(settings, 'FACEBOOK_APP_ID', None)
            facebook_app_secret = getattr(settings, 'FACEBOOK_APP_SECRET', None)
            
            if not access_token:
                logger.warning("Facebook access token not configured. Add FACEBOOK_ACCESS_TOKEN to .env or connect via OAuth")
                return None
            
            # Remove @ if present
            handle = handle.lstrip('@')
            
            # If page_id is not provided, try to find it from handle
            if not page_id:
                # Method 1: Search by username
                search_url = "https://graph.facebook.com/v18.0/search"
                params = {
                    'q': handle,
                    'type': 'page',
                    'access_token': access_token,
                    'limit': 1
                }
                response = requests.get(search_url, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('data'):
                        page_id = data['data'][0].get('id')
            
            # If we still don't have page_id, try using handle directly
            if not page_id:
                page_id = handle
                # Try to fetch with handle as page_id
                graph_url = f"https://graph.facebook.com/v18.0/{page_id}"
                params = {
                    'fields': 'followers_count,name,username',
                    'access_token': access_token
                }
                
                response = requests.get(graph_url, params=params, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    followers_count = data.get('followers_count')
                    if followers_count is not None:
                        return int(followers_count)
                else:
                    # Log the API error for debugging
                    error_data = response.json() if response.content else {}
                    error_message = error_data.get('error', {}).get('message', 'Unknown error')
                    logger.warning(f"Facebook API error {response.status_code}: {error_message}")
            
            # If API method failed, try third-party API, then public scraping
            # Try RapidAPI first (if configured)
            rapidapi_count = FacebookFollowerVerifier._rapidapi_fetch(handle)
            if rapidapi_count:
                logger.info(f"Successfully fetched Facebook followers via RapidAPI for {handle}: {rapidapi_count}")
                return rapidapi_count
            
            # Fallback to public scraping
            logger.info(f"Facebook API method failed for {handle}, trying public scraping...")
            scraped_count = FacebookFollowerVerifier._scrape_follower_count(handle)
            if scraped_count:
                return scraped_count
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching Facebook followers for @{handle}: {e}")
            # Try scraping as last resort
            try:
                return FacebookFollowerVerifier._scrape_follower_count(handle)
            except:
                return None
    
    @staticmethod
    def _rapidapi_fetch(username: str) -> Optional[int]:
        """
        Fetch Facebook follower count using RapidAPI.
        Requires RAPIDAPI_KEY in settings.
        
        Uses Facebook Profile Scraper from RapidAPI marketplace.
        """
        try:
            rapidapi_key = getattr(settings, 'RAPIDAPI_KEY', None)
            if not rapidapi_key:
                return None
            
            # Try Facebook Profile Scraper API
            url = "https://facebook-profile-scraper.p.rapidapi.com/profile"
            headers = {
                "X-RapidAPI-Key": rapidapi_key,
                "X-RapidAPI-Host": "facebook-profile-scraper.p.rapidapi.com"
            }
            params = {"username": username}
            
            response = requests.get(url, headers=headers, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                # Extract follower count from response
                follower_count = (
                    data.get('followers_count') or
                    data.get('followers') or
                    data.get('follower_count') or
                    data.get('data', {}).get('followers_count')
                )
                if follower_count:
                    return int(follower_count)
            
            return None
        except Exception as e:
            logger.debug(f"RapidAPI fetch failed for {username}: {e}")
            return None
    
    @staticmethod
    def _scrape_follower_count(username: str) -> Optional[int]:
        """
        Scrape Facebook Page follower count from public page.
        This works for both Pages and public profiles.
        
        Note: Facebook may block scraping attempts. Use with caution.
        """
        try:
            # Try different URL formats
            urls = [
                f"https://www.facebook.com/{username}",
                f"https://www.facebook.com/{username}/",
                f"https://m.facebook.com/{username}",
            ]
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
            }
            
            for url in urls:
                try:
                    response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
                    
                    if response.status_code != 200:
                        continue
                    
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Method 1: Look for followers in meta tags
                    meta_tags = soup.find_all('meta', property=lambda x: x and ('followers' in str(x).lower() or 'follower' in str(x).lower()))
                    for meta in meta_tags:
                        content = meta.get('content', '')
                        numbers = re.findall(r'\d+', content.replace(',', '').replace('.', ''))
                        if numbers:
                            return int(numbers[0])
                    
                    # Method 2: Look for followers in text content
                    # Facebook shows "X followers" or "X people follow this"
                    text_content = soup.get_text()
                    
                    # Pattern: "X followers" or "X people follow this"
                    patterns = [
                        r'(\d+(?:,\d+)*)\s+followers',
                        r'(\d+(?:,\d+)*)\s+people\s+follow',
                        r'followers[:\s]+(\d+(?:,\d+)*)',
                    ]
                    
                    for pattern in patterns:
                        matches = re.findall(pattern, text_content, re.IGNORECASE)
                        if matches:
                            # Get the largest number (most likely to be follower count)
                            numbers = [int(m.replace(',', '')) for m in matches]
                            if numbers:
                                return max(numbers)
                    
                    # Method 3: Look in structured data or JSON-LD
                    json_scripts = soup.find_all('script', type='application/ld+json')
                    for script in json_scripts:
                        try:
                            data = json.loads(script.string)
                            # Look for follower count in structured data
                            if isinstance(data, dict):
                                # Check various possible keys
                                for key in ['followers', 'followerCount', 'interactionStatistic']:
                                    if key in data:
                                        value = data[key]
                                        if isinstance(value, (int, str)):
                                            num = int(str(value).replace(',', ''))
                                            if num > 0:
                                                return num
                        except:
                            continue
                    
                except Exception as e:
                    logger.debug(f"Error scraping from {url}: {e}")
                    continue
            
            return None
            
        except Exception as e:
            logger.error(f"Error scraping Facebook followers for {username}: {e}")
            return None
    
    @classmethod
    def verify(cls, handle: str, user_provided_count: int, page_id: str = None) -> FollowerVerificationResult:
        """Verify Facebook Page follower count."""
        actual_count = cls.fetch_follower_count(handle, page_id)
        
        if actual_count is None:
            return FollowerVerificationResult(
                verified=False,
                user_count=user_provided_count,
                method="manual",
                error="Unable to fetch follower count automatically"
            )
        
        discrepancy = abs(actual_count - user_provided_count)
        allowed_discrepancy = max(100, user_provided_count * 0.05)
        
        verified = discrepancy <= allowed_discrepancy
        
        return FollowerVerificationResult(
            verified=verified,
            actual_count=actual_count,
            user_count=user_provided_count,
            discrepancy=discrepancy,
            method="api"
        )


class FollowerVerificationService:
    """Main service for verifying follower counts."""
    
    VERIFIERS = {
        'tiktok': TikTokFollowerVerifier(),
        'instagram': InstagramFollowerVerifier(),
        'youtube': YouTubeFollowerVerifier(),
        'facebook': FacebookFollowerVerifier(),
    }
    
    @classmethod
    def verify_follower_count(cls, platform: str, handle: str, user_provided_count: int, 
                             account_id: str = None, page_id: str = None) -> FollowerVerificationResult:
        """
        Verify follower count for a platform.
        
        Args:
            platform: Platform name (tiktok, instagram, youtube, facebook)
            handle: Platform handle (without @)
            user_provided_count: Count provided by user
            account_id: Instagram Business Account ID (optional, for Instagram only)
            page_id: Facebook Page ID (optional, for Facebook only)
        
        Returns:
            FollowerVerificationResult
        """
        verifier = cls.VERIFIERS.get(platform.lower())
        
        if not verifier:
            return FollowerVerificationResult(
                verified=False,
                user_count=user_provided_count,
                method="manual",
                error=f"No verifier available for {platform}"
            )
        
        # Call verify method with appropriate parameters
        if platform.lower() == 'instagram':
            return verifier.verify(handle, user_provided_count, account_id=account_id)
        elif platform.lower() == 'facebook':
            return verifier.verify(handle, user_provided_count, page_id=page_id)
        elif platform.lower() == 'tiktok':
            # TikTok verification doesn't support access_token in this method
            # It should be handled at the connection level
            return verifier.verify(handle, user_provided_count)
        else:
            return verifier.verify(handle, user_provided_count)

