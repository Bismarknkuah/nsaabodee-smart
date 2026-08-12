from django.urls import path

from .views import ChangePasswordView, DemoLoginView, LoginView, LogoutView, MeView, RefreshView, RequestOtpView, ResetPasswordWithOtpView, SwitchDashboardContextView, VerifyOtpView

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/refresh/", RefreshView.as_view(), name="auth-refresh"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("auth/switch-context/", SwitchDashboardContextView.as_view(), name="auth-switch-context"),
    path("auth/change-password/", ChangePasswordView.as_view(), name="auth-change-password"),
    path("auth/demo-login/", DemoLoginView.as_view(), name="auth-demo-login"),
    path("auth/otp/request/", RequestOtpView.as_view(), name="auth-otp-request"),
    path("auth/otp/verify/", VerifyOtpView.as_view(), name="auth-otp-verify"),
    path("auth/otp/reset-password/", ResetPasswordWithOtpView.as_view(), name="auth-otp-reset-password"),
]
