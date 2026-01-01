from django.urls import path
from . import views
from campaigns import views as campaign_views

app_name = "brands"

urlpatterns = [
    path("dashboard/", views.brand_dashboard, name="dashboard"),
    path("wallet/", views.brand_wallet, name="wallet"),
    path("campaigns/", views.brand_campaigns, name="campaigns"),
    path("campaigns/create/", campaign_views.create_campaign, name="create_campaign"),
    path("campaigns/<int:campaign_id>/edit/", campaign_views.edit_campaign, name="edit_campaign"),
    path("campaigns/<int:campaign_id>/activate/", campaign_views.activate_campaign, name="activate_campaign"),
    path("billing/", views.brand_billing, name="billing"),
    path("billing/add-payment-method/", views.add_payment_method, name="add_payment_method"),
    path("billing/save-payment-method/", views.save_payment_method, name="save_payment_method"),
    path("profile/", views.brand_profile, name="profile"),
    path("settings/", views.brand_settings, name="settings"),
]


