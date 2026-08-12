export type MemberStatus = "active" | "inactive" | "deceased";
export type DefaulterTier = "none" | "warning" | "high_warning" | "flagged";
export type Gender = "male" | "female";

export interface MemberFamilyDetail {
  id: string;
  name: string;
}

export interface Member {
  id: string;
  membership_number: string;
  full_name: string;
  gender: Gender;
  date_of_birth: string | null;
  occupation: string;
  phone: string;
  address: string;
  ghana_card_number: string | null;
  photo_url: string | null;
  family: string | null;
  family_detail: MemberFamilyDetail | null;
  emergency_contact_name: string;
  emergency_contact_phone: string;
  status: MemberStatus;
  linked_username: string | null;
  linked_role: string | null;
  missed_contributions_count: number;
  defaulter_tier: DefaulterTier;
  defaulter_evaluated_at: string | null;
  created_at: string;
  updated_at: string;
  possible_duplicates?: Member[];
}

export interface DigitalMembershipCard {
  member_id: string;
  membership_number: string;
  full_name: string;
  family_name: string | null;
  status: MemberStatus;
  photo_url: string | null;
  qr_code_base64: string;
}
