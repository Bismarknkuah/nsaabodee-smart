import { create } from "zustand";
import type { Family } from "@/types/family";

type DialogKind =
  | "add"
  | "rename"
  | "merge"
  | "deactivate"
  | "delete"
  | "transfer"
  | "assignHead"
  | "history"
  | "rate"
  | null;

interface FamilyUiState {
  activeDialog: DialogKind;
  activeFamily: Family | null;
  includeInactive: boolean;
  openDialog: (kind: DialogKind, family?: Family) => void;
  closeDialog: () => void;
  toggleIncludeInactive: () => void;
}

export const useFamilyUiStore = create<FamilyUiState>((set) => ({
  activeDialog: null,
  activeFamily: null,
  includeInactive: false,
  openDialog: (kind, family) => set({ activeDialog: kind, activeFamily: family ?? null }),
  closeDialog: () => set({ activeDialog: null, activeFamily: null }),
  toggleIncludeInactive: () => set((s) => ({ includeInactive: !s.includeInactive })),
}));
