import type { Metadata } from "next";
import { cookies } from "next/headers";
import "@fontsource-variable/manrope";
import "@fontsource/mukta/devanagari-400.css";
import "@fontsource/mukta/devanagari-700.css";
import "@/styles/site.css";
import { Shell } from "@/features/Shell";

export const metadata: Metadata = {
  title: {
    default: "KaamPaas | Local work in Ghaziabad",
    template: "%s | KaamPaas",
  },
  description:
    "Find daily work or permanent jobs in Ghaziabad, Uttar Pradesh. Hire by trade and locality in Hindi or English.",
};
export default async function Layout({
  children,
}: {
  children: React.ReactNode;
}) {
  const lang = (await cookies()).get("kp-lang")?.value === "hi" ? "hi" : "en";
  const number = process.env.WHATSAPP_PUBLIC_NUMBER?.trim() || "";
  const whatsapp =
    process.env.WHATSAPP_ENABLED?.toLowerCase() === "true" &&
    /^[1-9]\d{7,14}$/.test(number)
      ? `https://wa.me/${number}?text=Hi`
      : "";
  const phoneAuth =
    (
      process.env.WEB_PHONE_AUTH_ENABLED ??
      (process.env.VERCEL ? "false" : "true")
    ).toLowerCase() === "true";
  return (
    <html lang={lang}>
      <body>
        <a className="skip" href="#main">
          {lang === "hi" ? "मुख्य सामग्री" : "Skip to content"}
        </a>
        <Shell initial={lang} whatsapp={whatsapp} phoneAuth={phoneAuth}>
          {children}
        </Shell>
      </body>
    </html>
  );
}
