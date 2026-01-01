from django.urls import path
from . import views

app_name = "payments"

urlpatterns = [
    path("callback/", views.payment_callback, name="callback"),
    path("webhook/paystack/", views.paystack_webhook, name="paystack_webhook"),
]

