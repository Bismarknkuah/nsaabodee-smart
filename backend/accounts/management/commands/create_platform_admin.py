"""
A genuine, production-oriented way to bootstrap the first real
Platform Admin login — not a demo account, and deliberately NOT a
Django superuser either. "The Platform Administrator must not: Add
community members, Edit community members... Manage community
finances... Manage community families..." — is_superuser bypasses
every one of these checks throughout the whole system (most
permission classes read `actor.is_superuser or actor.role in
[...]`), so granting it here would silently undo every operational
boundary Platform Admin is supposed to respect. This account's
authority comes entirely from role=platform_admin, exactly like
seed_demo_data's demo_platform_admin already does — is_staff/
is_superuser are Django admin-panel concerns, unrelated to anything
this platform's own dashboard checks.
"""
import getpass

from django.core.management.base import BaseCommand, CommandError

from accounts.models import Role, User


class Command(BaseCommand):
    help = "Create a real (non-demo) Platform Admin login."

    def add_arguments(self, parser):
        parser.add_argument("--username", type=str, help="Username for the new Platform Admin. Prompted for if omitted.")
        parser.add_argument("--email", type=str, default="", help="Optional email address.")

    def handle(self, *args, **options):
        username = options.get("username") or input("Username: ").strip()
        if not username:
            raise CommandError("A username is required.")
        if User.objects.filter(username=username).exists():
            raise CommandError(f"A user named '{username}' already exists.")

        email = options.get("email", "")

        password = getpass.getpass("Password (at least 8 characters): ")
        if len(password) < 8:
            raise CommandError("Password must be at least 8 characters.")
        password_confirm = getpass.getpass("Confirm password: ")
        if password != password_confirm:
            raise CommandError("Passwords did not match.")

        user = User.objects.create_user(username=username, email=email, password=password, role=Role.PLATFORM_ADMIN)

        self.stdout.write(self.style.SUCCESS(
            f"Platform Admin '{username}' created — role=platform_admin only, not a Django superuser."
        ))
