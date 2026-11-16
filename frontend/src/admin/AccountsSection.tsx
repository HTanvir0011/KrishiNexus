import { RotateCcw, Trash2, UserPlus, Users } from "lucide-react";
import { useState, type FormEvent } from "react";

import { api, type Role } from "../api/client";
import { Badge, Button, Panel, Spinner } from "../components/ui";
import { cn } from "../lib/format";
import { useCopy } from "../lib/i18n";
import { ROLE_LABEL, ROLE_TONE } from "../lib/roles";
import { useAppState } from "../state/store";
import { TABLE, TD, TH, useAdmin } from "./useAdmin";

export const ROLES: Role[] = ["farmer", "coop", "buyer", "bank", "judge", "admin"];
const FIELD = "min-h-10 w-full rounded-lg bg-white px-3 text-[14px] text-slate-900 ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-emerald-700 focus:outline-none";

const COPY = {
  en: {
    users: "Accounts",
    add: "Add a demo account",
    name: "Name",
    role: "Role",
    district: "District",
    titleField: "Description",
    passwordField: "Password (optional)",
    passwordHint: "Leave empty to use the demo password.",
    create: "Add account",
    headers: ["Account", "Role", "District", "Status", ""],
    active: "Active",
    disabled: "Disabled",
    enable: "Enable",
    disable: "Disable",
    remove: "Delete",
    you: "you",
    confirmDelete: (name: string) => `Delete the account "${name}"? This cannot be undone.`,
    resetUsers: "Restore the 8 seeded accounts",
    confirmReset: "Replace every account with the 8 seeded demo accounts?",
    saved: "Account saved",
    deleted: "Account deleted",
    restored: "Seeded accounts restored",
  },
  bn: {
    users: "অ্যাকাউন্ট",
    add: "ডেমো অ্যাকাউন্ট যোগ করুন",
    name: "নাম",
    role: "ভূমিকা",
    district: "জেলা",
    titleField: "বিবরণ",
    passwordField: "পাসওয়ার্ড (ঐচ্ছিক)",
    passwordHint: "খালি রাখলে ডেমো পাসওয়ার্ড থাকবে।",
    create: "যোগ করুন",
    headers: ["অ্যাকাউন্ট", "ভূমিকা", "জেলা", "অবস্থা", ""],
    active: "সক্রিয়",
    disabled: "বন্ধ",
    enable: "চালু",
    disable: "বন্ধ করুন",
    remove: "মুছুন",
    you: "আপনি",
    confirmDelete: (name: string) => `"${name}" অ্যাকাউন্ট মুছবেন? এটি ফেরানো যাবে না।`,
    resetUsers: "৮টি মূল অ্যাকাউন্ট ফিরিয়ে আনুন",
    confirmReset: "সব অ্যাকাউন্ট বদলে ৮টি মূল ডেমো অ্যাকাউন্ট ফিরিয়ে আনবেন?",
    saved: "অ্যাকাউন্ট সংরক্ষিত",
    deleted: "অ্যাকাউন্ট মুছে ফেলা হয়েছে",
    restored: "মূল অ্যাকাউন্ট ফিরেছে",
  },
};

export function AccountsSection() {
  const c = useCopy(COPY);
  const lang = useAppState((s) => s.lang);
  const me = useAppState((s) => s.user);
  const { data: users, busy, run } = useAdmin(api.adminUsers);
  const [form, setForm] = useState({ name: "", role: "farmer" as Role, district: "", title: "", password: "" });

  const create = (event: FormEvent) => {
    event.preventDefault();
    void run("create", async () => {
      await api.adminCreateUser({ ...form, password: form.password || undefined });
      setForm({ name: "", role: form.role, district: "", title: "", password: "" });
    }, c.saved);
  };

  return (
    <div className="grid gap-5 2xl:grid-cols-3">
      <Panel className="2xl:col-span-2" title={c.users} icon={<Users className="size-4 text-slate-600" aria-hidden />}
        actions={
          <Button variant="quiet" disabled={busy !== null}
            onClick={() => window.confirm(c.confirmReset) && void run("reset", api.adminResetUsers, c.restored)}>
            <RotateCcw className="size-4" aria-hidden /> {c.resetUsers}
          </Button>
        }>
        {!users ? <Spinner /> : (
          <div className="scroll-thin -mx-1 overflow-x-auto">
            <table className={TABLE}>
              <thead><tr className="border-b border-slate-200">{c.headers.map((h, i) => <th key={i} scope="col" className={TH}>{h}</th>)}</tr></thead>
              <tbody>
                {users.map((u) => {
                  const self = u.user_id === me?.user_id;
                  return (
                    <tr key={u.user_id} className={cn("border-b border-slate-100", !u.active && "text-slate-400")}>
                      <td className={TD}>
                        <div className="font-semibold text-slate-900">{u.name}{self && <span className="ml-1.5 text-[12px] font-normal text-slate-500">({c.you})</span>}</div>
                        <div className="font-mono text-[11.5px] text-slate-500">{u.user_id}{u.title ? ` · ${u.title}` : ""}</div>
                      </td>
                      <td className={TD}>
                        <select aria-label={`${c.role}: ${u.name}`} value={u.role} disabled={busy !== null || self}
                          onChange={(e) => void run(`role-${u.user_id}`, () => api.adminUpdateUser(u.user_id, { role: e.target.value as Role }), c.saved)}
                          className="min-h-9 rounded-md bg-white px-2 text-[13px] ring-1 ring-inset ring-slate-300">
                          {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABEL[lang][r]}</option>)}
                        </select>
                      </td>
                      <td className={TD}>{u.district || "—"}</td>
                      <td className={TD}><Badge tone={u.active ? ROLE_TONE[u.role] : "slate"}>{u.active ? c.active : c.disabled}</Badge></td>
                      <td className={TD}>
                        <div className="flex justify-end gap-1">
                          <Button variant="quiet" className="min-h-9" disabled={busy !== null || self}
                            onClick={() => void run(`active-${u.user_id}`, () => api.adminUpdateUser(u.user_id, { active: !u.active }), c.saved)}>
                            {u.active ? c.disable : c.enable}
                          </Button>
                          <Button variant="quiet" className="min-h-9 text-rose-700" disabled={busy !== null || self} aria-label={`${c.remove}: ${u.name}`}
                            onClick={() => window.confirm(c.confirmDelete(u.name)) && void run(`del-${u.user_id}`, () => api.adminDeleteUser(u.user_id), c.deleted)}>
                            <Trash2 className="size-4" aria-hidden />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Panel className="content-start" title={c.add} icon={<UserPlus className="size-4 text-slate-600" aria-hidden />}>
        <form onSubmit={create} className="grid gap-3">
          <label className="grid gap-1 text-[13px] font-medium text-slate-700">{c.name}
            <input required minLength={2} maxLength={60} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className={FIELD} />
          </label>
          <label className="grid gap-1 text-[13px] font-medium text-slate-700">{c.role}
            <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as Role })} className={FIELD}>
              {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABEL[lang][r]}</option>)}
            </select>
          </label>
          <label className="grid gap-1 text-[13px] font-medium text-slate-700">{c.district}
            <input maxLength={40} value={form.district} onChange={(e) => setForm({ ...form, district: e.target.value })} className={FIELD} />
          </label>
          <label className="grid gap-1 text-[13px] font-medium text-slate-700">{c.titleField}
            <input maxLength={80} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className={FIELD} />
          </label>
          <label className="grid gap-1 text-[13px] font-medium text-slate-700">{c.passwordField}
            <input type="password" autoComplete="new-password" minLength={6} maxLength={128} value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })} className={FIELD} />
            <span className="text-[12px] font-normal text-slate-500">{c.passwordHint}</span>
          </label>
          <Button variant="primary" type="submit" disabled={busy !== null}>
            {busy === "create" ? <Spinner /> : <UserPlus className="size-4" aria-hidden />} {c.create}
          </Button>
        </form>
      </Panel>
    </div>
  );
}
