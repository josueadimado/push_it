"""
Automated verification service for brands.
Similar to influencer verification but checks brand-specific criteria.
"""
from typing import Optional, List
from dataclasses import dataclass
from django.utils import timezone
from django.db import transaction
import re
from urllib.parse import urlparse

from .models import Brand


@dataclass
class VerificationResult:
    """Result of brand verification."""
    passed: bool
    reason: str
    confidence: float  # 0.0 to 1.0
    flags: List[str] = None
    
    def __post_init__(self):
        if self.flags is None:
            self.flags = []


class BrandVerifier:
    """Automated verification service for brands."""
    
    @staticmethod
    def verify_website(website: str):
        """
        Verify website URL format and accessibility.
        
        Returns:
            (is_valid, confidence_score, flags)
        """
        if not website:
            return False, 0.0, ["No website provided"]
        
        # Check URL format
        try:
            parsed = urlparse(website)
            if not parsed.scheme or not parsed.netloc:
                return False, 0.3, ["Invalid website URL format"]
            
            # Check if it's a valid domain
            if not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$', parsed.netloc):
                return False, 0.3, ["Invalid domain format"]
            
            # Check for common TLDs
            valid_tlds = ['.com', '.net', '.org', '.io', '.co', '.app', '.dev', '.tech', '.ai']
            has_valid_tld = any(parsed.netloc.endswith(tld) for tld in valid_tlds)
            
            if has_valid_tld:
                return True, 0.8, []
            else:
                return True, 0.6, ["Uncommon TLD - may need manual review"]
        except Exception:
            return False, 0.2, ["Website URL parsing failed"]
    
    @staticmethod
    def verify_company_name(name: str):
        """Verify company name quality."""
        if not name:
            return False, 0.0, ["Company name is required"]
        
        name = name.strip()
        
        # Check minimum length
        if len(name) < 2:
            return False, 0.2, ["Company name too short"]
        
        # Check for suspicious patterns
        suspicious_patterns = [
            r'^test\s*',
            r'^demo\s*',
            r'^example\s*',
            r'\d{10,}',  # Too many numbers
        ]
        
        flags = []
        for pattern in suspicious_patterns:
            if re.search(pattern, name, re.IGNORECASE):
                flags.append("Suspicious company name pattern")
        
        if flags:
            return True, 0.5, flags
        
        # Good company name
        if len(name) >= 3 and len(name) <= 100:
            return True, 1.0, []
        else:
            return True, 0.8, ["Company name length unusual"]
    
    @staticmethod
    def verify_industry(industry: str):
        """Verify industry field."""
        if not industry:
            return False, 0.0, ["Industry is required"]
        
        industry = industry.strip()
        
        # Check minimum length
        if len(industry) < 2:
            return False, 0.3, ["Industry too short"]
        
        # Check for common industries (basic validation)
        common_industries = [
            'fashion', 'tech', 'food', 'beauty', 'fitness', 'travel',
            'finance', 'health', 'education', 'entertainment', 'sports',
            'automotive', 'real estate', 'retail', 'e-commerce'
        ]
        
        is_common = any(ind.lower() in industry.lower() for ind in common_industries)
        
        if is_common:
            return True, 1.0, []
        else:
            return True, 0.7, ["Uncommon industry - may need review"]
    
    @staticmethod
    def verify_description(description: str):
        """Verify company description quality."""
        if not description:
            return False, 0.0, ["Description is required"]
        
        description = description.strip()
        
        # Check minimum length
        if len(description) < 20:
            return False, 0.3, ["Description too short (minimum 20 characters)"]
        
        # Check for suspicious content
        suspicious_keywords = ['test', 'demo', 'example', 'lorem ipsum']
        flags = []
        for keyword in suspicious_keywords:
            if keyword.lower() in description.lower():
                flags.append(f"Suspicious keyword found: {keyword}")
        
        # Good description
        if len(description) >= 50:
            score = 1.0
        elif len(description) >= 30:
            score = 0.8
        else:
            score = 0.6
        
        return True, score, flags
    
    @staticmethod
    def verify_contact_info(contact_email: str, phone_number: str):
        """Verify contact information."""
        flags = []
        score = 0.0
        
        # Check email
        if contact_email:
            if '@' in contact_email and '.' in contact_email.split('@')[1]:
                score += 0.5
            else:
                flags.append("Invalid contact email format")
        else:
            flags.append("No contact email provided")
        
        # Check phone number
        if phone_number:
            # Basic phone validation (allows international formats)
            phone_clean = re.sub(r'[\s\-\(\)]', '', phone_number)
            if re.match(r'^\+?\d{7,15}$', phone_clean):
                score += 0.5
            else:
                flags.append("Invalid phone number format")
        else:
            flags.append("No phone number provided")
        
        return score > 0, score, flags
    
    @classmethod
    def verify_brand(cls, brand: Brand) -> VerificationResult:
        """
        Verify a brand using automated checks.
        
        Returns:
            VerificationResult with verification outcome
        """
        checks = []
        total_score = 0.0
        max_score = 0.0
        all_flags = []
        
        # 1. Company name check
        name_valid, name_score, name_flags = cls.verify_company_name(brand.company_name)
        checks.append(("Company Name", name_valid, name_score))
        total_score += name_score
        max_score += 1.0
        all_flags.extend(name_flags)
        
        # 2. Industry check
        industry_valid, industry_score, industry_flags = cls.verify_industry(brand.industry)
        checks.append(("Industry", industry_valid, industry_score))
        total_score += industry_score
        max_score += 1.0
        all_flags.extend(industry_flags)
        
        # 3. Description check
        desc_valid, desc_score, desc_flags = cls.verify_description(brand.description)
        checks.append(("Description", desc_valid, desc_score))
        total_score += desc_score
        max_score += 1.0
        all_flags.extend(desc_flags)
        
        # 4. Website check (optional but adds to score)
        if brand.website:
            website_valid, website_score, website_flags = cls.verify_website(brand.website)
            checks.append(("Website", website_valid, website_score))
            total_score += website_score
            max_score += 1.0
            all_flags.extend(website_flags)
        else:
            # Website is optional, so we don't penalize but don't add to score
            checks.append(("Website", True, 0.0))
        
        # 5. Contact info check
        contact_valid, contact_score, contact_flags = cls.verify_contact_info(
            brand.contact_email, brand.phone_number
        )
        checks.append(("Contact Info", contact_valid, contact_score))
        total_score += contact_score
        max_score += 1.0
        all_flags.extend(contact_flags)
        
        # Calculate final confidence score
        if max_score > 0:
            confidence = total_score / max_score
        else:
            confidence = 0.0
        
        # Determine if passed
        # Pass if: all required fields valid AND confidence >= 0.7
        required_passed = (
            name_valid and 
            industry_valid and 
            desc_valid and 
            contact_valid
        )
        
        passed = required_passed and confidence >= 0.7
        
        reason = "All checks passed" if passed else "Some verification checks failed"
        
        return VerificationResult(
            passed=passed,
            reason=reason,
            confidence=confidence,
            flags=all_flags
        )


class BrandVerificationService:
    """Main service for brand verification."""
    
    @classmethod
    def verify_brand(cls, brand: Brand, auto_approve: bool = True) -> VerificationResult:
        """
        Verify a brand and optionally auto-approve.
        
        Args:
            brand: Brand instance to verify
            auto_approve: If True, automatically approve brands that pass
        
        Returns:
            VerificationResult with verification outcome
        """
        result = BrandVerifier.verify_brand(brand)
        
        # Auto-approve if passed and auto_approve is True
        if result.passed and auto_approve:
            with transaction.atomic():
                brand.verification_status = Brand.VerificationStatus.VERIFIED
                brand.save()
        
        return result
