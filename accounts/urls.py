from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("signup/brand/", views.signup_brand, name="signup_brand"),
    path("signup/influencer/", views.signup_influencer, name="signup_influencer"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    
    # Email verification
    path("verify-email/<uidb64>/<token>/", views.verify_email, name="verify_email"),
    path("email-verification-sent/", views.email_verification_sent, name="email_verification_sent"),
    path("resend-verification/", views.resend_verification, name="resend_verification"),
    
    # Brand onboarding
    path("onboarding/brand/", views.brand_onboarding, name="brand_onboarding"),
    path("verification/brand/pending/", views.brand_verification_pending, name="brand_verification_pending"),
    
    # Influencer onboarding
    path("onboarding/influencer/", views.influencer_onboarding, name="influencer_onboarding"),
    path("verification/influencer/pending/", views.influencer_verification_pending, name="influencer_verification_pending"),
]


