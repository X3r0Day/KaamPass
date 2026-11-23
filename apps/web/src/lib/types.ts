import type { components } from "./schema";
export type S = components["schemas"];
export type Lang = "en" | "hi";
export type Profile = S["Profile"];
export type Job = S["Job"];
export type Draft = S["JobDraft"];
export type Catalog = { places: S["Place"][]; skills: S["Skill"][] };
export const today = () =>
  new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Kolkata",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
export function money(paise: number, lang: Lang) {
  return new Intl.NumberFormat(`${lang}-IN`, {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(paise / 100);
}
export function dateLabel(value: string, lang: Lang) {
  return new Intl.DateTimeFormat(`${lang}-IN`, {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(value + "T12:00:00Z"));
}
