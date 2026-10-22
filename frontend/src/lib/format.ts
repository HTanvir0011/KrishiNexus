import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

const BN_DIGITS = "০১২৩৪৫৬৭৮৯";

export function bnDigits(value: string | number): string {
  return String(value).replace(/[0-9]/g, (d) => BN_DIGITS[Number(d)]);
}

export function tk(value: number | null | undefined, decimals = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return `Tk ${value.toLocaleString("en-IN", { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}`;
}

export function kg(value: number): string {
  return `${value.toLocaleString("en-IN", { maximumFractionDigits: 0 })} kg`;
}

export function pct(value: number | null | undefined, decimals = 1): string {
  return value === null || value === undefined ? "-" : `${value.toFixed(decimals)}%`;
}

export function shortHash(hash: string, size = 10): string {
  return hash.length > size * 2 ? `${hash.slice(0, size)}…${hash.slice(-6)}` : hash;
}

export function timeOf(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleTimeString("en-GB", { hour12: false });
}
