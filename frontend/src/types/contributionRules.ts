export interface FamilyRateSummary {
  family_id: string;
  family_name: string;
  standing_rate: string | null;
  recommended_rate: string | null;
}

export interface MemberStatusExemption {
  status: "active" | "inactive" | "deceased";
  is_exempt: boolean;
  is_default: boolean;
}

export interface ContributionRulesSummary {
  general_rates: { male_amount: string; female_amount: string };
  family_tier_rates: { head_amount: string; senior_amount: string; junior_amount: string; woman_amount: string; town_leader_amount: string };
  family_rates: FamilyRateSummary[];
  member_status_exemptions: MemberStatusExemption[];
  defaulter_thresholds: { warning: number; high_warning: number; flag: number };
}

export interface ObligationPreview {
  own_family_amount: string | null;
  own_family_member_count: number;
  general_male_amount: string;
  general_male_member_count: number;
  general_female_amount: string;
  general_female_member_count: number;
  requires_one_off_amount: boolean;
}
