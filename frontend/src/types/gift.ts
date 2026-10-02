export type GiftPaymentMethod = "cash" | "mobile_money" | "bank" | "other" | "not_applicable";
export type DonorCategory = "guest" | "town_leader" | "other";

export interface GiftDonation {
  id: string;
  funeral_event: string;
  recipient_family: string;
  recipient_family_name: string;
  donor_name: string;
  donor_phone: string;
  donor_member: string | null;
  donor_member_name: string | null;
  donor_category: DonorCategory;
  donor_hometown: string;
  connected_relative_name: string;
  relationship_to_recipient: string;
  received_by_member: string | null;
  received_by_member_name: string | null;
  amount_cash: string;
  gift_item: string;
  estimated_item_value: string | null;
  total_value: string;
  payment_method: GiftPaymentMethod;
  receipt_number: string;
  given_at: string;
}

export interface GiftSummary {
  funeral_id: string;
  donation_count: number;
  total_cash: string;
  total_estimated_item_value: string;
  total_combined_value: string;
}

export interface CategoryBreakdownBucket {
  donor_count: number;
  total_value: string;
}

export interface GiftCategoryBreakdown {
  funeral_id: string;
  by_category: Record<DonorCategory, CategoryBreakdownBucket>;
}

export interface DonationAccountRegistration {
  id: string;
  funeral_event: string;
  member: string;
  member_name: string;
  is_active: boolean;
  registered_at: string;
}

export interface MyDonationsReceivedFuneral {
  funeral_id: string;
  deceased_name: string;
  donation_count: number;
  total_value: string;
}

/** One donor's gift — "the name, phone contact, where the gifter resides, the amount the gifter paid," plus who and when. */
export interface DonationEntry {
  donor_name: string;
  donor_phone: string;
  donor_hometown: string;
  relationship_to_recipient: string;
  amount: string;
  deceased_name: string;
  date_of_death: string;
  paid_on: string;
  paid_at_time: string;
  receipt_number: string;
}

export interface MyDonationsReceived {
  member_id: string | null;
  member_name: string | null;
  total_received: string;
  donation_count: number;
  by_funeral: MyDonationsReceivedFuneral[];
  entries: DonationEntry[];
}

export interface ReceiverDonationList {
  member_id: string;
  member_name: string;
  donation_count: number;
  total_received: string;
  entries: DonationEntry[];
}
