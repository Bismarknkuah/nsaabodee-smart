"""
Who may take money, and where — the one place every money-recording path
asks. "Apart from the user roles responsible for collecting or recording
money, NO user role type is permitted to receive or record money... and
since we have all levels of collector, each one should collect in his
jurisdiction only."

A grant is (kind, scope):
  kind  — "contributions" (open funerals), "arrears" (closed funerals),
          "gifts" (guests' donations), "welfare", "family_fund"
  scope — ("community", None) | ("family", family_id) | ("town_elders", None)

Community level:  collector (general nomination or none) -> contributions
                  arrears_collector                       -> arrears
                  gift_collector                          -> gifts
Family level:     collector + "family" nomination         -> contributions, welfare, family_fund (that family)
                  family_arrears_officer                  -> arrears (own family)
                  collector + "donation" nomination       -> gifts (that family's funerals)
Town Elders:      collector + "town_elder" nomination     -> contributions (elders only)
                  town_elders_arrears_officer             -> arrears (elders only)
Visitors:         gift_collector                          -> gifts (any funeral)

Nobody else records money. A superuser is the platform's break-glass and
is never a normal user.
"""
from accounts.models import Role


def collector_grants(user) -> list:
    """Every (kind, scope) this person holds. Empty list = not a collector of anything."""
    if user is None or not getattr(user, "is_authenticated", False):
        return []
    if user.is_superuser:
        return [("*", ("community", None))]
    member = getattr(user, "member_profile", None)
    own_family = member.family_id if member is not None else None
    role = user.role
    grants = []
    if role == Role.COLLECTOR:
        from members.models import CollectorNomination
        approved = list(CollectorNomination.objects.filter(member=member, status=CollectorNomination.Status.APPROVED).values_list("collector_type", "scoped_family_id")) if member else []
        # "The collectors at all levels should play the same role as arrears
        # collector" — a collector takes contributions AND arrears in their
        # jurisdiction; the nomination carries the level.
        if not approved:
            grants += [("contributions", ("community", None)), ("arrears", ("community", None)), ("welfare", ("community", None))]
        for ctype, fam in approved:
            if ctype == "general":
                grants += [("contributions", ("community", None)), ("arrears", ("community", None)), ("welfare", ("community", None))]
            elif ctype == "family" and fam:
                grants += [("contributions", ("family", fam)), ("arrears", ("family", fam)), ("welfare", ("family", fam)), ("family_fund", ("family", fam))]
            elif ctype == "town_elder":
                grants += [("contributions", ("town_elders", None)), ("arrears", ("town_elders", None))]
            elif ctype == "donation":
                grants.append(("gifts", ("family", fam) if fam else ("community", None)))
    elif role == Role.GIFT_COLLECTOR:
        grants.append(("gifts", ("community", None)))
    # Legacy values (moved by the consolidation migration; kept so an unmigrated record still behaves)
    elif role == "arrears_collector":
        grants.append(("arrears", ("community", None)))
    elif role == "family_arrears_officer" and own_family:
        grants.append(("arrears", ("family", own_family)))
    elif role == "town_elders_arrears_officer":
        grants.append(("arrears", ("town_elders", None)))
    return grants


def _scope_covers_member(scope, member) -> bool:
    kind, value = scope
    if kind == "community":
        return True
    if kind == "family":
        # The ledger decides who collects. A family member moved onto the Town Elders ledger no
        # longer pays their family, so their family's collector no longer takes their money —
        # the Town Elders collector does (same person, still in the family, different ledger).
        return member is not None and member.family_id == value and not member.is_town_leader
    if kind == "town_elders":
        return member is not None and bool(member.is_town_leader)
    return False


def _has(user, kind, member=None, family_id=None) -> bool:
    for gkind, scope in collector_grants(user):
        if gkind not in ("*", kind):
            continue
        if member is not None and not _scope_covers_member(scope, member):
            continue
        if member is None and family_id is not None and not (scope[0] == "community" or (scope[0] == "family" and scope[1] == family_id)):
            continue
        return True
    return False


def can_record_contribution(user, obligation) -> bool:
    """Open-funeral contribution — the right kind of collector, whose scope covers THIS member."""
    from funerals.models import FuneralEvent
    if obligation.funeral_event.status != FuneralEvent.Status.ACTIVE:
        return False
    return _has(user, "contributions", member=obligation.member)


def can_record_arrears(user, obligation) -> bool:
    """Closed-funeral balance — an arrears collector whose scope covers THIS member."""
    from funerals.models import FuneralEvent
    if obligation.funeral_event.status == FuneralEvent.Status.ACTIVE:
        return False
    return _has(user, "arrears", member=obligation.member)


def can_record_gift(user, funeral) -> bool:
    """A guest's donation to THIS funeral — the community's gift collector, or the deceased family's own donation collector."""
    return _has(user, "gifts", family_id=funeral.deceased_family_id)


def can_record_welfare_payment(user, obligation) -> bool:
    """A community campaign -> the community's contribution collector; a family's own campaign -> that family's collector."""
    campaign = obligation.campaign
    for kind, (skind, val) in collector_grants(user):
        if kind == "*":
            return True
        if kind != "welfare":
            continue
        if campaign.family_id:
            if skind == "family" and val == campaign.family_id:
                return True
        elif skind == "community":
            return True
    return False


def can_record_family_fund_contribution(user, fund) -> bool:
    """A family's own fund is only ever collected by that family's own collector."""
    for kind, (skind, val) in collector_grants(user):
        if kind == "*" or (kind == "family_fund" and skind == "family" and val == fund.family_id):
            return True
    return False


def jurisdiction_summary(user) -> dict:
    """For a collector's own dashboard: what they collect, and where, in plain words."""
    grants = collector_grants(user)
    if not grants:
        return {"is_collector": False, "grants": []}
    from families.models import Family
    names = {}
    out = []
    for kind, (skind, val) in grants:
        if skind == "family" and val not in names:
            names[val] = Family.objects.filter(id=val).values_list("name", flat=True).first() or "their family"
        where = "the whole community" if skind == "community" else f"the {names[val]} family" if skind == "family" else "Town Elders"
        what = {"contributions": "funeral contributions (open funerals)", "arrears": "arrears (balances left after a funeral closed)",
                "gifts": "guests\' donations and gifts", "welfare": "welfare contributions", "family_fund": "family fund contributions", "*": "everything"}[kind]
        out.append({"kind": kind, "scope": skind, "family_id": str(val) if val else None, "label": f"{what} for {where}"})
    return {"is_collector": True, "grants": out}
