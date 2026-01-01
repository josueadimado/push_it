from django.urls import path
from . import views

app_name = "operations"

urlpatterns = [
    path("dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("campaigns/", views.admin_campaigns, name="campaigns"),
    path("campaigns/<int:campaign_id>/", views.admin_campaign_detail, name="campaign_detail"),
    path("influencers/", views.admin_influencers, name="influencers"),
    path("verification/", views.admin_verification, name="verification"),
    path("submissions/", views.admin_submissions, name="submissions"),
    path("payments/", views.admin_payments, name="payments"),
    path("reports/", views.admin_reports, name="reports"),
    # Backend actions
    path("submissions/<int:submission_id>/approve/", views.approve_submission, name="approve_submission"),
    path("submissions/<int:submission_id>/reject/", views.reject_submission, name="reject_submission"),
    path("submissions/<int:submission_id>/flag/", views.flag_submission, name="flag_submission"),
    path("payments/<int:payout_id>/mark-sent/", views.mark_payout_sent, name="mark_payout_sent"),
    path("influencers/<int:influencer_id>/review/", views.review_influencer, name="review_influencer"),
    path("influencers/<int:influencer_id>/approve/", views.approve_influencer, name="approve_influencer"),
    path("influencers/<int:influencer_id>/reject/", views.reject_influencer, name="reject_influencer"),
    path("influencers/<int:influencer_id>/pause/", views.pause_influencer, name="pause_influencer"),
    path("influencers/<int:influencer_id>/unpause/", views.unpause_influencer, name="unpause_influencer"),
    path("brands/<int:brand_id>/review/", views.review_brand, name="review_brand"),
    path("brands/<int:brand_id>/approve/", views.approve_brand, name="approve_brand"),
    path("brands/<int:brand_id>/reject/", views.reject_brand, name="reject_brand"),
    path("brands/<int:brand_id>/pause/", views.pause_brand, name="pause_brand"),
    path("brands/<int:brand_id>/unpause/", views.unpause_brand, name="unpause_brand"),
    # Notifications
    path("notifications/", views.get_notifications, name="get_notifications"),
    path("notifications/<int:notification_id>/read/", views.mark_notification_read, name="mark_notification_read"),
]


