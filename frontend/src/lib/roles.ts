import type { Role } from "../api/client";
import type { OsView } from "./router";

/** Which workspace seats each demo role may open, and where it lands after login. */
export const ROLE_VIEWS: Record<Role, OsView[]> = {
  farmer: ["field", "trade"],
  coop: ["coop"],
  storage: ["himagar"],
  buyer: ["trade", "market"],
  bank: ["market"],
  driver: ["driver"],
  judge: ["judge", "field", "coop", "himagar", "trade", "driver", "market"],
  admin: ["judge", "field", "coop", "himagar", "trade", "driver", "market"],
};

export function homeOf(role: Role): string {
  if (role === "admin") return "/admin";
  const first = ROLE_VIEWS[role][0];
  return first === "judge" ? "/os" : `/os/${first}`;
}

export const ROLE_LABEL: Record<"en" | "bn", Record<Role, string>> = {
  en: { farmer: "Farmer", coop: "Co-op / cold chain", storage: "Himagar (cold storage)", buyer: "Buyer / trader", bank: "Bank", driver: "Truck driver", judge: "Judge", admin: "Admin" },
  bn: { farmer: "কৃষক", coop: "সমবায় / কোল্ড চেইন", storage: "হিমাগার", buyer: "ক্রেতা / ব্যবসায়ী", bank: "ব্যাংক", driver: "ট্রাক চালক", judge: "বিচারক", admin: "অ্যাডমিন" },
};

export const ROLE_TONE: Record<Role, "emerald" | "sky" | "amber" | "violet" | "slate" | "red"> = {
  farmer: "emerald", coop: "sky", storage: "sky", buyer: "amber", bank: "violet", driver: "amber", judge: "slate", admin: "red",
};
