from django.urls import path
from . import views

app_name = "influencers"

urlpatterns = [
    path("dashboard/", views.influencer_dashboard, name="dashboard"),
    path("jobs/", views.job_feed, name="job_feed"),
    path("jobs/<int:campaign_id>/", views.campaign_detail, name="campaign_detail"),
    path("my-jobs/", views.my_jobs, name="my_jobs"),
    path("wallet/", views.wallet, name="wallet"),
    path("wallet/request-withdrawal/", views.request_withdrawal, name="request_withdrawal"),
    path("wallet/payment-methods/add/", views.add_payment_method, name="add_payment_method"),
    path("wallet/payment-methods/<int:method_id>/edit/", views.edit_payment_method, name="edit_payment_method"),
    path("wallet/payment-methods/<int:method_id>/delete/", views.delete_payment_method, name="delete_payment_method"),
    path("wallet/payment-methods/<int:method_id>/set-default/", views.set_default_payment_method, name="set_default_payment_method"),
    path("profile/", views.profile, name="profile"),
    path("platforms/<int:connection_id>/reverify/", views.reverify_platform, name="reverify_platform"),
    # OAuth endpoints
    path("connect/facebook/", views.connect_facebook, name="connect_facebook"),
    path("connect/instagram/", views.connect_instagram, name="connect_instagram"),
    path("connect/tiktok/", views.connect_tiktok, name="connect_tiktok"),
    path("oauth/callback/", views.oauth_callback, name="oauth_callback"),
]


