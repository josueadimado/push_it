"""
Automated verification system for influencer platform connections.
Handles bulk verification with automated checks and flagging for manual review.
"""

import re
import requests
from typing import Dict, List, Tuple, Optional
from django.utils import timezone
from django.db import transaction
from datetime import timedelta

from .models import PlatformConnection, PlatformSettings, Influencer
from .follower_verification import FollowerVerificationService


class VerificationResult:
    """Result of a verification check."""
    
    def __init__(self, passed: bool, reason: str = "", confidence: float = 0.0, flags: List[str] = None):
        self.passed = passed
        self.reason = reason
        self.confidence = confidence  # 0.0 to 1.0
        self.flags = flags or []  # List of warning flags
    
    def __repr__(self):
        return f"VerificationResult(passed={self.passed}, confidence={self.confidence}, flags={self.flags})"


class PlatformVerifier:
    """Base class for platform-specific verification."""
    
    def verify(self, connection: PlatformConnection) -> VerificationResult:
        """Verify a platform connection. Returns VerificationResult."""
        raise NotImplementedError


class TikTokVerifier(PlatformVerifier):
    """TikTok-specific verification checks."""
    
    def verify(self, connection: PlatformConnection) -> VerificationResult:
        flags = []
        checks_passed = 0
        total_checks = 0
        
        # Check 1: Verify actual follower count from platform API
        total_checks += 1
        # Use OAuth data if available (preferred method)
        access_token = connection.access_token if connection.access_token else None
        open_id = connection.tiktok_open_id if connection.tiktok_open_id else None
        
        # If we have OAuth token, use it directly
        if access_token:
            from .follower_verification import TikTokFollowerVerifier
            actual_count = TikTokFollowerVerifier.fetch_follower_count(
                connection.handle, 
                access_token=access_token,
                open_id=open_id
            )
            # Create result manually since we have direct access
            if actual_count is not None:
                from .follower_verification import FollowerVerificationResult
                discrepancy = abs(actual_count - connection.followers_count)
                allowed_discrepancy = max(100, connection.followers_count * 0.05)
                verified = discrepancy <= allowed_discrepancy
                follower_result = FollowerVerificationResult(
                    verified=verified,
                    actual_count=actual_count,
                    user_count=connection.followers_count,
                    discrepancy=discrepancy,
                    method="api"
                )
            else:
                follower_result = FollowerVerificationService.verify_follower_count(
                    'tiktok', 
                    connection.handle, 
                    connection.followers_count
                )
        else:
            # Fallback to regular verification
            follower_result = FollowerVerificationService.verify_follower_count(
                'tiktok', 
                connection.handle, 
                connection.followers_count
            )
        
        if follower_result.verified and follower_result.actual_count:
            # Update verified count
            connection.verified_followers_count = follower_result.actual_count
            connection.follower_verification_date = timezone.now()
            connection.save(update_fields=['verified_followers_count', 'follower_verification_date'])
            checks_passed += 1
        elif follower_result.actual_count is not None:
            # API returned count but it doesn't match
            connection.verified_followers_count = follower_result.actual_count
            connection.follower_verification_date = timezone.now()
            connection.save(update_fields=['verified_followers_count', 'follower_verification_date'])
            
            discrepancy_pct = (follower_result.discrepancy / follower_result.actual_count * 100) if follower_result.actual_count > 0 else 0
            flags.append(f"Follower count mismatch: User provided {connection.followers_count:,}, API shows {follower_result.actual_count:,} (difference: {follower_result.discrepancy:,}, {discrepancy_pct:.1f}%)")
        else:
            # Can't verify via API - flag for manual review
            flags.append("Unable to verify follower count via API - requires manual review")
        
        # Check 2: Follower count meets minimum (use verified count if available)
        total_checks += 1
        count_to_check = connection.verified_followers_count or connection.followers_count
        min_followers = PlatformSettings.get_minimum_followers('tiktok')
        if count_to_check >= min_followers:
            checks_passed += 1
        else:
            flags.append(f"Follower count ({count_to_check:,}) below minimum ({min_followers:,})")
        
        # Check 2: Handle format validation
        total_checks += 1
        if re.match(r'^[a-zA-Z0-9._]+$', connection.handle) and len(connection.handle) >= 1:
            checks_passed += 1
        else:
            flags.append("Invalid handle format")
        
        # Check 3: Sample post URL validation (if provided)
        if connection.sample_post_url:
            total_checks += 1
            if 'tiktok.com' in connection.sample_post_url.lower():
                checks_passed += 1
            else:
                flags.append("Sample post URL doesn't appear to be from TikTok")
        
        # Check 4: Follower count reasonableness (flag if suspiciously high)
        total_checks += 1
        if connection.followers_count < 1000000:  # Flag if over 1M (might need manual review)
            checks_passed += 1
        else:
            flags.append("Very high follower count - manual review recommended")
        
        # Check 5: Engagement rate reasonableness
        if connection.engagement_rate > 0:
            total_checks += 1
            # Typical engagement: 1-5% for TikTok
            if 0.5 <= connection.engagement_rate <= 10:
                checks_passed += 1
            else:
                flags.append(f"Unusual engagement rate: {connection.engagement_rate}%")
        
        confidence = checks_passed / total_checks if total_checks > 0 else 0.0
        
        # Auto-approve if high confidence and no critical flags
        passed = confidence >= 0.8 and not any('below minimum' in flag for flag in flags)
        
        return VerificationResult(
            passed=passed,
            reason=f"Passed {checks_passed}/{total_checks} checks",
            confidence=confidence,
            flags=flags
        )


class InstagramVerifier(PlatformVerifier):
    """Instagram-specific verification checks."""
    
    def verify(self, connection: PlatformConnection) -> VerificationResult:
        flags = []
        checks_passed = 0
        total_checks = 0
        
        # Check 1: Verify actual follower count from platform API
        total_checks += 1
        # Use OAuth data if available (preferred method)
        account_id = connection.instagram_business_account_id
        access_token = connection.access_token if connection.access_token else None
        
        # If we have OAuth token, use it directly
        if access_token and account_id:
            from .follower_verification import InstagramFollowerVerifier
            actual_count = InstagramFollowerVerifier.fetch_follower_count(
                connection.handle, 
                account_id=account_id,
                access_token=access_token
            )
            # Create result manually since we have direct access
            if actual_count is not None:
                from .follower_verification import FollowerVerificationResult
                discrepancy = abs(actual_count - connection.followers_count)
                allowed_discrepancy = max(100, connection.followers_count * 0.05)
                verified = discrepancy <= allowed_discrepancy
                follower_result = FollowerVerificationResult(
                    verified=verified,
                    actual_count=actual_count,
                    user_count=connection.followers_count,
                    discrepancy=discrepancy,
                    method="api"
                )
            else:
                follower_result = FollowerVerificationService.verify_follower_count(
                    'instagram', 
                    connection.handle, 
                    connection.followers_count,
                    account_id=account_id
                )
        else:
            # Fallback to regular verification
            follower_result = FollowerVerificationService.verify_follower_count(
                'instagram', 
                connection.handle, 
                connection.followers_count,
                account_id=account_id
            )
        
        if follower_result.verified and follower_result.actual_count:
            connection.verified_followers_count = follower_result.actual_count
            connection.follower_verification_date = timezone.now()
            connection.save(update_fields=['verified_followers_count', 'follower_verification_date'])
            checks_passed += 1
        elif follower_result.actual_count is not None:
            connection.verified_followers_count = follower_result.actual_count
            connection.follower_verification_date = timezone.now()
            connection.save(update_fields=['verified_followers_count', 'follower_verification_date'])
            
            discrepancy_pct = (follower_result.discrepancy / follower_result.actual_count * 100) if follower_result.actual_count > 0 else 0
            flags.append(f"Follower count mismatch: User provided {connection.followers_count:,}, API shows {follower_result.actual_count:,} (difference: {follower_result.discrepancy:,}, {discrepancy_pct:.1f}%)")
        else:
            flags.append("Unable to verify follower count via API - requires manual review")
        
        # Check 2: Follower count meets minimum (use verified count if available)
        total_checks += 1
        count_to_check = connection.verified_followers_count or connection.followers_count
        min_followers = PlatformSettings.get_minimum_followers('instagram')
        if count_to_check >= min_followers:
            checks_passed += 1
        else:
            flags.append(f"Follower count ({count_to_check:,}) below minimum ({min_followers:,})")
        
        # Check 2: Handle format validation
        total_checks += 1
        if re.match(r'^[a-zA-Z0-9._]+$', connection.handle) and len(connection.handle) >= 1:
            checks_passed += 1
        else:
            flags.append("Invalid handle format")
        
        # Check 3: Sample post URL validation
        if connection.sample_post_url:
            total_checks += 1
            if 'instagram.com' in connection.sample_post_url.lower():
                checks_passed += 1
            else:
                flags.append("Sample post URL doesn't appear to be from Instagram")
        
        # Check 4: Engagement rate reasonableness
        if connection.engagement_rate > 0:
            total_checks += 1
            # Typical engagement: 1-3% for Instagram
            if 0.5 <= connection.engagement_rate <= 8:
                checks_passed += 1
            else:
                flags.append(f"Unusual engagement rate: {connection.engagement_rate}%")
        
        confidence = checks_passed / total_checks if total_checks > 0 else 0.0
        passed = confidence >= 0.8 and not any('below minimum' in flag for flag in flags)
        
        return VerificationResult(
            passed=passed,
            reason=f"Passed {checks_passed}/{total_checks} checks",
            confidence=confidence,
            flags=flags
        )


class YouTubeVerifier(PlatformVerifier):
    """YouTube-specific verification checks."""
    
    def verify(self, connection: PlatformConnection) -> VerificationResult:
        flags = []
        checks_passed = 0
        total_checks = 0
        actual_follower_count = None
        
        # Check 1: Verify actual subscriber count from YouTube API
        total_checks += 1
        follower_result = FollowerVerificationService.verify_follower_count(
            'youtube', 
            connection.handle, 
            connection.followers_count
        )
        
        # Always update verified_followers_count if we got a real count from API
        if follower_result.actual_count is not None:
            actual_follower_count = follower_result.actual_count
            connection.verified_followers_count = actual_follower_count
            connection.follower_verification_date = timezone.now()
            connection.save(update_fields=['verified_followers_count', 'follower_verification_date'])
            
            # Check if user-provided count matches
            if follower_result.verified:
                checks_passed += 1
            else:
                # User provided wrong number - we'll use the real count for validation
                discrepancy_pct = (abs(follower_result.discrepancy) / actual_follower_count * 100) if actual_follower_count > 0 else 0
                flags.append(f"Follower count corrected: Your channel has {actual_follower_count:,} subscribers (you provided {connection.followers_count:,})")
        else:
            # API unavailable - use user-provided count
            actual_follower_count = connection.followers_count
            flags.append("Unable to verify subscriber count via API - using provided count")
        
        # Check 2: Subscriber count meets minimum (ALWAYS use verified/real count from API if available)
        total_checks += 1
        count_to_check = actual_follower_count or connection.followers_count
        min_followers = PlatformSettings.get_minimum_followers('youtube')
        
        if count_to_check >= min_followers:
            checks_passed += 1
        else:
            # Clear message showing the real count and minimum required
            flags.append(f"Your channel has {count_to_check:,} subscribers, but you need at least {min_followers:,} to join. Please grow your channel and try again.")
        
        # Check 3: Handle/Channel format validation
        total_checks += 1
        # YouTube handles can be @handle or channel IDs
        if re.match(r'^[a-zA-Z0-9._-]+$', connection.handle) and len(connection.handle) >= 1:
            checks_passed += 1
        else:
            flags.append("Invalid channel handle format")
        
        # Check 4: Sample post URL validation
        if connection.sample_post_url:
            total_checks += 1
            if 'youtube.com' in connection.sample_post_url.lower() or 'youtu.be' in connection.sample_post_url.lower():
                checks_passed += 1
            else:
                flags.append("Sample post URL doesn't appear to be from YouTube")
        
        # Determine if verification passes BEFORE calculating confidence
        api_unavailable = any('Unable to verify' in flag for flag in flags)
        below_minimum = any('you need at least' in flag.lower() for flag in flags)
        
        if below_minimum:
            # Always reject if below minimum (even if API unavailable)
            passed = False
            confidence = checks_passed / total_checks if total_checks > 0 else 0.0
        elif api_unavailable:
            # If API is unavailable but basic checks pass, still approve with medium confidence
            basic_checks_passed = (
                count_to_check >= min_followers and
                re.match(r'^[a-zA-Z0-9._-]+$', connection.handle) and
                len(connection.handle) >= 1
            )
            if basic_checks_passed:
                # Approve with medium confidence (0.7) when API unavailable but basic checks pass
                confidence = 0.7
                passed = True
            else:
                # API unavailable and basic checks didn't pass - use calculated confidence
                confidence = checks_passed / total_checks if total_checks > 0 else 0.0
                passed = confidence >= 0.8
        else:
            # Normal verification when API is available
            # If we got a real count from API and it's >= minimum, and handle is valid, approve
            # (Don't penalize for user providing wrong initial count)
            if actual_follower_count is not None and actual_follower_count >= min_followers:
                # Real count is valid - check handle format
                handle_valid = re.match(r'^[a-zA-Z0-9._-]+$', connection.handle) and len(connection.handle) >= 1
                if handle_valid:
                    # Approve with high confidence since we verified via API
                    passed = True
                    confidence = 0.9  # High confidence when API verified and count is good
                else:
                    # Count is good but handle is invalid
                    confidence = checks_passed / total_checks if total_checks > 0 else 0.0
                    passed = confidence >= 0.8
            else:
                # Calculate confidence normally
                confidence = checks_passed / total_checks if total_checks > 0 else 0.0
                # Pass if confidence is high AND not below minimum
                passed = confidence >= 0.8 and not below_minimum
        
        return VerificationResult(
            passed=passed,
            reason=f"Passed {checks_passed}/{total_checks} checks" + (f" (Real count: {actual_follower_count:,})" if actual_follower_count else ""),
            confidence=confidence,
            flags=flags
        )


class FacebookVerifier(PlatformVerifier):
    """Facebook-specific verification checks."""
    
    def verify(self, connection: PlatformConnection) -> VerificationResult:
        flags = []
        checks_passed = 0
        total_checks = 0
        
        # Check 1: Verify actual follower count from platform API
        total_checks += 1
        # Use OAuth data if available (preferred method)
        page_id = connection.facebook_page_id
        access_token = connection.access_token if connection.access_token else None
        
        # If we have OAuth token, use it directly
        if access_token and page_id:
            from .follower_verification import FacebookFollowerVerifier
            actual_count = FacebookFollowerVerifier.fetch_follower_count(
                connection.handle, 
                page_id=page_id,
                access_token=access_token
            )
            # Create result manually since we have direct access
            if actual_count is not None:
                from .follower_verification import FollowerVerificationResult
                discrepancy = abs(actual_count - connection.followers_count)
                allowed_discrepancy = max(100, connection.followers_count * 0.05)
                verified = discrepancy <= allowed_discrepancy
                follower_result = FollowerVerificationResult(
                    verified=verified,
                    actual_count=actual_count,
                    user_count=connection.followers_count,
                    discrepancy=discrepancy,
                    method="api"
                )
            else:
                follower_result = FollowerVerificationService.verify_follower_count(
                    'facebook', 
                    connection.handle, 
                    connection.followers_count,
                    page_id=page_id
                )
        else:
            # Fallback to regular verification
            follower_result = FollowerVerificationService.verify_follower_count(
                'facebook', 
                connection.handle, 
                connection.followers_count,
                page_id=page_id
            )
        
        if follower_result.verified and follower_result.actual_count:
            connection.verified_followers_count = follower_result.actual_count
            connection.follower_verification_date = timezone.now()
            connection.save(update_fields=['verified_followers_count', 'follower_verification_date'])
            checks_passed += 1
        elif follower_result.actual_count is not None:
            connection.verified_followers_count = follower_result.actual_count
            connection.follower_verification_date = timezone.now()
            connection.save(update_fields=['verified_followers_count', 'follower_verification_date'])
            
            discrepancy_pct = (follower_result.discrepancy / follower_result.actual_count * 100) if follower_result.actual_count > 0 else 0
            flags.append(f"Follower count mismatch: User provided {connection.followers_count:,}, API shows {follower_result.actual_count:,} (difference: {follower_result.discrepancy:,}, {discrepancy_pct:.1f}%)")
        else:
            flags.append("Unable to verify follower count via API - requires manual review")
        
        # Check 2: Follower count meets minimum (use verified count if available)
        total_checks += 1
        count_to_check = connection.verified_followers_count or connection.followers_count
        min_followers = PlatformSettings.get_minimum_followers('facebook')
        if count_to_check >= min_followers:
            checks_passed += 1
        else:
            flags.append(f"Follower count ({count_to_check:,}) below minimum ({min_followers:,})")
        
        # Check 3: Handle format validation
        total_checks += 1
        if re.match(r'^[a-zA-Z0-9._]+$', connection.handle) and len(connection.handle) >= 1:
            checks_passed += 1
        else:
            flags.append("Invalid handle format")
        
        # Check 4: Sample post URL validation
        if connection.sample_post_url:
            total_checks += 1
            if 'facebook.com' in connection.sample_post_url.lower():
                checks_passed += 1
            else:
                flags.append("Sample post URL doesn't appear to be from Facebook")
        
        confidence = checks_passed / total_checks if total_checks > 0 else 0.0
        passed = confidence >= 0.8 and not any('below minimum' in flag for flag in flags)
        
        return VerificationResult(
            passed=passed,
            reason=f"Passed {checks_passed}/{total_checks} checks",
            confidence=confidence,
            flags=flags
        )


class VerificationService:
    """Main verification service that orchestrates automated verification."""
    
    VERIFIERS = {
        'tiktok': TikTokVerifier(),
        'instagram': InstagramVerifier(),
        'youtube': YouTubeVerifier(),
        'facebook': FacebookVerifier(),
        # Add more verifiers as needed
    }
    
    @classmethod
    def get_verifier(cls, platform: str) -> Optional[PlatformVerifier]:
        """Get the appropriate verifier for a platform."""
        return cls.VERIFIERS.get(platform.lower())
    
    @classmethod
    def verify_connection(cls, connection: PlatformConnection, auto_approve: bool = True) -> VerificationResult:
        """
        Verify a single platform connection.
        
        Args:
            connection: PlatformConnection to verify
            auto_approve: If True, automatically approve connections that pass
        
        Returns:
            VerificationResult with verification outcome
        """
        verifier = cls.get_verifier(connection.platform)
        
        if not verifier:
            # No automated verifier for this platform - flag for manual review
            return VerificationResult(
                passed=False,
                reason="No automated verifier available for this platform",
                confidence=0.0,
                flags=["Requires manual review"]
            )
        
        result = verifier.verify(connection)
        
        # Auto-approve if passed and auto_approve is True
        if result.passed and auto_approve:
            with transaction.atomic():
                connection.verification_status = PlatformConnection.VerificationStatus.VERIFIED
                connection.verified_at = timezone.now()
                connection.save()
        
        return result
    
    @classmethod
    def verify_influencer_platforms(cls, influencer: Influencer, auto_approve: bool = True) -> Dict[str, VerificationResult]:
        """
        Verify all pending platform connections for an influencer.
        
        Returns:
            Dictionary mapping platform to VerificationResult
        """
        results = {}
        pending_connections = influencer.platform_connections.filter(
            verification_status=PlatformConnection.VerificationStatus.PENDING
        )
        
        for connection in pending_connections:
            result = cls.verify_connection(connection, auto_approve=auto_approve)
            results[connection.platform] = result
        
        return results
    
    @classmethod
    def batch_verify_pending(cls, limit: int = 100, auto_approve: bool = True) -> Dict[str, int]:
        """
        Batch verify all pending platform connections.
        
        Args:
            limit: Maximum number of connections to process
            auto_approve: If True, automatically approve connections that pass
        
        Returns:
            Dictionary with statistics about the batch verification
        """
        pending = PlatformConnection.objects.filter(
            verification_status=PlatformConnection.VerificationStatus.PENDING
        )[:limit]
        
        stats = {
            'total_processed': 0,
            'auto_approved': 0,
            'flagged': 0,
            'rejected': 0,
        }
        
        for connection in pending:
            stats['total_processed'] += 1
            result = cls.verify_connection(connection, auto_approve=auto_approve)
            
            if result.passed:
                stats['auto_approved'] += 1
            elif result.confidence < 0.5:
                # Low confidence - reject
                connection.verification_status = PlatformConnection.VerificationStatus.REJECTED
                connection.save()
                stats['rejected'] += 1
            else:
                # Medium confidence - flag for manual review (keep as pending)
                stats['flagged'] += 1
        
        return stats
    
    @classmethod
    def flag_suspicious_connections(cls) -> List[PlatformConnection]:
        """
        Flag connections that might be suspicious for manual review.
        This runs additional checks beyond basic verification.
        
        Returns:
            List of suspicious connections
        """
        suspicious = []
        
        # Flag connections with very high follower counts (might be fake)
        high_follower_connections = PlatformConnection.objects.filter(
            verification_status=PlatformConnection.VerificationStatus.VERIFIED,
            followers_count__gte=1000000
        )
        
        for conn in high_follower_connections:
            # Check if engagement rate is suspiciously low for high follower count
            if conn.engagement_rate > 0 and conn.engagement_rate < 0.5:
                suspicious.append(conn)
        
        # Flag connections with suspicious engagement rates
        suspicious_engagement = PlatformConnection.objects.filter(
            verification_status=PlatformConnection.VerificationStatus.VERIFIED,
            engagement_rate__lt=0.1  # Less than 0.1% engagement
        )
        
        suspicious.extend(suspicious_engagement)
        
        return suspicious


def auto_verify_on_save(sender, instance, created, **kwargs):
    """
    Signal handler to automatically verify platform connections when saved.
    This can be connected via Django signals.
    """
    if created and instance.verification_status == PlatformConnection.VerificationStatus.PENDING:
        # Only auto-verify if it's a new connection
        result = VerificationService.verify_connection(instance, auto_approve=True)
        
        # If verification failed but has medium confidence, keep as pending for manual review
        if not result.passed and result.confidence >= 0.5:
            # Keep as pending - will be reviewed manually
            pass
        elif not result.passed:
            # Low confidence - reject
            instance.verification_status = PlatformConnection.VerificationStatus.REJECTED
            instance.save()

