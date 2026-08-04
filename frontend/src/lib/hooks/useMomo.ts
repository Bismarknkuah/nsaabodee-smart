import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { momoApi, type MomoPaymentRequest } from "@/lib/api/momo";

export function useInitiateMomoPayment() {
  return useMutation({
    mutationFn: ({ obligationId, phoneNumber, amount }: { obligationId: string; phoneNumber: string; amount: string }) =>
      momoApi.requestToPay(obligationId, phoneNumber, amount),
  });
}

export function useInitiateMomoGiftPayment() {
  return useMutation({
    mutationFn: ({
      funeralId, phoneNumber, amount, donorName, receivedByMemberId,
    }: { funeralId: string; phoneNumber: string; amount: string; donorName: string; receivedByMemberId?: string }) =>
      momoApi.requestGiftToPay(funeralId, { phoneNumber, amount, donorName, receivedByMemberId }),
  });
}

/**
 * Mobile Money doesn't tell you the outcome of a charge immediately —
 * it just accepts the request, then the payer's phone prompts them to
 * authorize (and for MTN specifically, an OTP the payer receives has
 * to be submitted before the charge can complete — see
 * useSubmitMomoOtp), and the real result only shows up via Paystack's
 * webhook or by polling. This hook polls every 3 seconds for up to 2
 * minutes, then gives up and tells the person to check back later
 * rather than spinning forever. 'awaiting_otp' pauses polling (an OTP
 * being needed isn't itself a final outcome, successful or failed) and
 * is reported as its own distinct state rather than folded into
 * "resolved" — the calling dialog decides what to show for it.
 */
export function usePollMomoStatus(referenceId: string | null, onResolved: (request: MomoPaymentRequest) => void) {
  const [status, setStatus] = useState<"idle" | "polling" | "awaiting_otp" | "resolved" | "timed_out">("idle");
  const attemptsRef = useRef(0);

  useEffect(() => {
    if (!referenceId) {
      setStatus("idle");
      return;
    }
    setStatus("polling");
    attemptsRef.current = 0;

    const interval = setInterval(async () => {
      attemptsRef.current += 1;
      try {
        const result = await momoApi.checkStatus(referenceId);
        if (result.status === "awaiting_otp") {
          clearInterval(interval);
          setStatus("awaiting_otp");
        } else if (result.status !== "pending") {
          clearInterval(interval);
          setStatus("resolved");
          onResolved(result);
        } else if (attemptsRef.current >= 40) {
          clearInterval(interval);
          setStatus("timed_out");
        }
      } catch {
        // A transient check failure shouldn't stop polling — Paystack's
        // own status endpoint can be flaky mid-transaction.
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [referenceId, onResolved]);

  return status;
}

/** Submits the OTP MTN mobile money sends the payer, resuming the charge — see payments.services.submit_momo_otp. */
export function useSubmitMomoOtp() {
  return useMutation({
    mutationFn: ({ referenceId, otp }: { referenceId: string; otp: string }) => momoApi.submitOtp(referenceId, otp),
  });
}

export function useMomoQueryInvalidation() {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: ["funeral-obligations"] });
  };
}

export function useMomoGiftQueryInvalidation() {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: ["gifts"] });
    qc.invalidateQueries({ queryKey: ["gift-summary"] });
    qc.invalidateQueries({ queryKey: ["gift-category-breakdown"] });
    qc.invalidateQueries({ queryKey: ["my-donations-received"] });
  };
}
