"""
"Add quick demo access button for all types of users to test the
system... on their dashboard." One User per role, in one dedicated Demo
Community, each with enough real supporting data (families, a funeral
in progress, contributions, gifts, a family fund, a task) that every
role's dashboard shows something meaningful the instant someone clicks
"Try as Chairman" — not an empty shell.

Idempotent: safe to run repeatedly (get_or_create everywhere), so this
can run automatically on every deploy without duplicating demo data.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand

from accounts.models import Role, User
from tenants.models import Community

DEMO_PASSWORD = "demo-password-not-for-real-use"

ALL_ROLES = list(Role.values)


class Command(BaseCommand):
    help = "Seeds one demo User per role, in a dedicated Demo Community, with realistic supporting data."

    def handle(self, *args, **options):
        community, _ = Community.objects.get_or_create(
            slug="demo",
            defaults={
                "name": "Demo Community",
                "region": "Demo Region",
                "default_general_male_amount": Decimal("5"),
                "default_general_female_amount": Decimal("3"),
            },
        )

        from families import services as family_services
        from members import services as member_services

        admin_user, _ = User.objects.get_or_create(
            username="demo_community_admin",
            defaults={"community": community, "role": Role.COMMUNITY_ADMIN},
        )
        admin_user.set_password(DEMO_PASSWORD)
        admin_user.community = community
        admin_user.save()

        asona = self._get_or_create_family(family_services, community, "Asona", admin_user)
        self._get_or_create_family(family_services, community, "Bretuo", admin_user)

        # One Member + one linked User per role, so every dashboard has
        # a real linked_member_id to hang member-scoped data off of.
        role_members = {}
        role_users = {}
        for role in ALL_ROLES:
            username = f"demo_{role}"
            user, _ = User.objects.get_or_create(username=username, defaults={"role": role})
            user.set_password(DEMO_PASSWORD)
            user.role = role
            if role != Role.PLATFORM_ADMIN:
                user.community = community
            user.save()
            role_users[role] = user

            if role == Role.PLATFORM_ADMIN:
                continue  # cross-community role — no Member profile needed

            member = self._get_or_create_member(member_services, community, f"Demo {role.replace('_', ' ').title()}", asona)
            if member.linked_user_id is None:
                member_services.link_member_to_user(member=member, user=user, actor=admin_user)
            role_members[role] = member

        # Family Head/Secretary/Treasurer assignments on Asona, so the
        # Family Fund and Family Officer dashboards have something real
        # to show.
        family_services.assign_family_head(family=asona, member=role_members[Role.FAMILY_HEAD], actor=admin_user)
        family_services.assign_family_officer(
            family=asona, member=role_members[Role.FAMILY_SECRETARY], officer_role="secretary", actor=admin_user,
        )
        family_services.assign_family_officer(
            family=asona, member=role_members[Role.FAMILY_TREASURER], officer_role="treasurer", actor=admin_user,
        )
        if asona.standing_family_rate is None:
            family_services.recommend_family_rate(family=asona, amount=Decimal("50"), actor=admin_user)
            family_services.approve_family_rate(family=asona, actor=admin_user)

        # A Family Fund with a real contribution.
        from family_funds import services as fund_services
        fund = fund_services.funds_for_family(asona).first()
        if fund is None:
            fund = fund_services.create_family_fund(family=asona, name="Asona Building Fund", actor=role_users[Role.FAMILY_HEAD])
        if fund.contributions.count() == 0:
            fund_services.record_fund_contribution(fund=fund, member=role_members[Role.COMMUNITY_MEMBER], amount=Decimal("25"))

        # A funeral in progress, with a real payment and a real gift, so
        # Collector/Treasurer/Auditor/etc. dashboards have real numbers.
        from funerals import services as funeral_services
        from funerals.models import ContributionObligation
        funeral = self._get_or_create_funeral(funeral_services, community, asona)
        obligation = ContributionObligation.objects.filter(
            funeral_event=funeral, member=role_members[Role.COMMUNITY_MEMBER]
        ).first()
        if obligation and obligation.amount_paid == 0:
            funeral_services.record_payment(
                obligation=obligation, amount=Decimal("50"), method="cash", collector=role_users[Role.COLLECTOR],
            )

        from gifts import services as gift_services
        if funeral.gift_donations.count() == 0:
            gift_services.record_gift_donation(
                funeral=funeral, donor_name="A Generous Guest", amount_cash=Decimal("40"), donor_hometown="Kumasi",
            )

        # A task, so Family Head / Chairman / Secretary dashboards
        # relating to task assignment have something to point at.
        from tasks import services as task_services
        if not role_members[Role.COMMUNITY_MEMBER].tasks.exists():
            task_services.assign_task(
                community=community, assigned_to=role_members[Role.COMMUNITY_MEMBER],
                title="Welcome guests at the gate", assigned_by=role_users[Role.FAMILY_HEAD],
                due_date=date.today() + timedelta(days=1),
            )

        # A funeral committee position, so the "committee_positions"
        # dashboard section (Batch 80) has something real to show —
        # this script predates that batch and several after it, so
        # every feature below is new as of this pass.
        from funerals.models import FuneralCommitteePosition
        if not FuneralCommitteePosition.objects.filter(funeral_event=funeral).exists():
            funeral_services.appoint_committee_position(
                funeral=funeral, member=role_members[Role.COMMUNITY_MEMBER], title="Logistics Coordinator", actor=admin_user,
            )

        # A community-wide meeting and a family-only meeting, so the
        # Chief/Family Head/Member dashboards' "upcoming meetings"
        # sections have real entries, one of each scope.
        from communication import services as communication_services
        from django.utils import timezone
        if not communication_services.list_upcoming_meetings(community).exists():
            communication_services.schedule_meeting(
                community=community, title="Monthly General Meeting",
                scheduled_for=timezone.now() + timedelta(days=7), location="Community Hall", actor=admin_user,
            )
        if not communication_services.list_upcoming_meetings(community, family=asona).filter(family=asona).exists():
            communication_services.schedule_meeting(
                community=community, family=asona, title="Asona Family Meeting",
                scheduled_for=timezone.now() + timedelta(days=3), actor=role_users[Role.FAMILY_HEAD],
            )

        # A welfare contribution category and an active, community-wide
        # campaign, so /welfare-contributions and every dashboard's own
        # "welfare_obligations" section (Batch 82/83) show a real,
        # already-billed example rather than an empty list.
        from welfare import services as welfare_services
        from welfare.models import ContributionCategory
        category = ContributionCategory.objects.filter(community=community, name="Monthly Welfare Contribution").first()
        if category is None:
            category = welfare_services.create_contribution_category(
                community=community, name="Monthly Welfare Contribution", purpose="General community welfare support.",
                fixed_amount=Decimal("10"), frequency=ContributionCategory.Frequency.MONTHLY, actor=admin_user,
            )
        if not category.campaigns.filter(family__isnull=True).exists():
            welfare_services.initiate_community_campaign(category=category, title="July 2026 Welfare Contribution", actor=admin_user)

        # Real branding, so /community-settings (Batch 79) shows an
        # actually-configured example instead of blank fields.
        if not community.tagline:
            from tenants import services as tenant_services
            tenant_services.update_own_community_branding(
                actor=admin_user, tagline="Every ledger transparent. Every family seen.",
                primary_color="#2F5233", secondary_color="#B8860B",
            )

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {len(ALL_ROLES)} demo users in '{community.name}'. Password (not for real use): {DEMO_PASSWORD}"
        ))

    def _get_or_create_family(self, family_services, community, name, actor):
        from families.models import Family
        existing = Family.objects.filter(community=community, name=name).first()
        if existing:
            return existing
        return family_services.create_family(community=community, name=name, actor=actor)

    def _get_or_create_member(self, member_services, community, full_name, family):
        from members.models import Member
        existing = Member.objects.filter(community=community, full_name=full_name).first()
        if existing:
            return existing
        return member_services.register_member(community=community, full_name=full_name, gender="male", family=family)

    def _get_or_create_funeral(self, funeral_services, community, family):
        from funerals.models import FuneralEvent
        existing = FuneralEvent.objects.filter(community=community, deceased_name="Demo Deceased").first()
        if existing:
            return existing
        return funeral_services.create_funeral_event(
            community=community, deceased_name="Demo Deceased", deceased_gender="male",
            deceased_family=family, date_of_death=date.today() - timedelta(days=2),
            collection_start_date=date.today() - timedelta(days=1),
        )
