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
  return (
    <html lang={lang}>
      <body>
        <a className="skip" href="#main">
          {lang === "hi" ? "मुख्य सामग्री" : "Skip to content"}
        </a>
        <Shell initial={lang}>{children}</Shell>
      </body>
    </html>
  );
}
