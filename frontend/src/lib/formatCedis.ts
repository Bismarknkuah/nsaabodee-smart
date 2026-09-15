export function formatCedis(amount: string | number): string {
  const value = typeof amount === "string" ? parseFloat(amount) : amount;
  return `GH₵${value.toLocaleString("en-GH", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
