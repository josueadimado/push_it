# Generated manually to clean up duplicate emails before adding unique constraint

from django.db import migrations
from django.db.models import Count


def remove_duplicate_emails(apps, schema_editor):
    """
    Remove duplicate emails by keeping the oldest account and marking others for deletion.
    For each duplicate email, we'll keep the first created account and update others.
    """
    User = apps.get_model('accounts', 'User')
    
    # Find duplicate emails (case-insensitive)
    from django.db.models import Count
    from collections import defaultdict
    
    # Get all users with emails
    users_with_email = User.objects.exclude(email='').exclude(email__isnull=True)
    
    # Group by lowercase email
    email_groups = defaultdict(list)
    for user in users_with_email:
        email_key = user.email.lower().strip() if user.email else None
        if email_key:
            email_groups[email_key].append(user)
    
    # For each group with duplicates, keep the oldest and update/delete others
    duplicates_found = 0
    for email_key, users in email_groups.items():
        if len(users) > 1:
            duplicates_found += len(users) - 1
            # Sort by date_joined (oldest first)
            users_sorted = sorted(users, key=lambda u: u.date_joined)
            keep_user = users_sorted[0]
            
            # For the rest, we need to either:
            # 1. Delete them (if they're test accounts)
            # 2. Update their email to make it unique
            
            for user_to_fix in users_sorted[1:]:
                # Option: Add a suffix to make email unique
                # Format: original_email+duplicate_N@domain
                if '@' in keep_user.email:
                    local, domain = keep_user.email.rsplit('@', 1)
                    new_email = f"{local}+duplicate_{user_to_fix.id}@{domain}"
                else:
                    new_email = f"{keep_user.email}+duplicate_{user_to_fix.id}"
                
                # Update the email
                user_to_fix.email = new_email
                user_to_fix.username = new_email  # Also update username since we use email as username
                user_to_fix.save()
    
    print(f"Fixed {duplicates_found} duplicate email(s)")


def reverse_remove_duplicates(apps, schema_editor):
    """Reverse migration - nothing to do as we can't restore original emails"""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(remove_duplicate_emails, reverse_remove_duplicates),
    ]

