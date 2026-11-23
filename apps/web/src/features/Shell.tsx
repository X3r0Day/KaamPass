"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { createContext, useContext, useState, type ReactNode } from "react";
import { words, errors, type Word } from "@/content/words";
import type { Lang } from "@/lib/types";
import { pilot } from "@/content/pilot";

const Language = createContext({
  lang: "en" as Lang,
  whatsapp: "",
  phoneAuth: true,
  setLang: (_l: Lang) => {
    void _l;
  },
});
export function useWords() {
  const ctx = useContext(Language);
  const at = ctx.lang === "hi" ? 1 : 0;
  return {
    ...ctx,
    t: (key: Word) => words[key][at],
    say: (en: string, hi: string) => (at ? hi : en),
    error: (e: unknown) => {
      const code =
        (e as { code?: string })?.code ||
        (e instanceof Error ? e.message : String(e));
      return (errors[code] || errors.connection)[at];
    },
  };
}
function Mark() {
  return (
    <svg viewBox="0 0 40 40" width="36" height="36" aria-hidden="true">
      <rect width="40" height="40" rx="9" fill="#17483e" />
      <path
        d="M7 28V16l7-6 7 6v12m-7 0v-8m8 8V15l6-5 6 5v13"
        fill="none"
        stroke="#f4cd69"
        strokeWidth="3"
        strokeLinejoin="round"
      />
    </svg>
  );
}
function Chrome({ children }: { children: ReactNode }) {
  const { lang, setLang, t, say, phoneAuth, whatsapp } = useWords();
  const path = usePathname();
  return (
    <>
      <header className="mast">
        <div className="bar wrap">
          <Link className="brand" href="/" aria-label="KaamPaas">
            <Mark />
            KaamPaas
          </Link>
          <nav aria-label={say("Main navigation", "मुख्य नेविगेशन")}>
            <button
              className="lang"
              lang={lang === "hi" ? "en" : "hi"}
              onClick={() => setLang(lang === "hi" ? "en" : "hi")}
            >
              {lang === "hi" ? "English" : "हिन्दी"}
            </button>
            {path === "/" && phoneAuth && (
              <Link className="headerLink" href="/login">
                {t("signin")}
              </Link>
            )}
            {whatsapp ? (
              <a className="headerLink" href={whatsapp}>
                WhatsApp
              </a>
            ) : (
              <span
                className="menuPaused"
                role="link"
                aria-disabled="true"
                aria-label={say(
                  "WhatsApp (temporarily unavailable)",
                  "WhatsApp (फ़िलहाल उपलब्ध नहीं)",
                )}
              >
                WhatsApp <span aria-hidden="true">{say("Paused", "बंद")}</span>
              </span>
            )}
          </nav>
        </div>
      </header>
      <main id="main">{children}</main>
      <footer>
        <div className="wrap foot">
          <span>KaamPaas</span>
          <span>{pilot[lang].region}</span>
        </div>
      </footer>
    </>
  );
}
export function Shell({
  initial,
  children,
  whatsapp,
  phoneAuth,
}: {
  initial: Lang;
  children: ReactNode;
  whatsapp: string;
  phoneAuth: boolean;
}) {
  const [lang, update] = useState(initial);
  function setLang(l: Lang) {
    update(l);
    document.documentElement.lang = l;
    document.cookie = `kp-lang=${l}; Path=/; SameSite=Lax; Max-Age=31536000`;
  }
  return (
    <Language.Provider value={{ lang, setLang, whatsapp, phoneAuth }}>
      <Chrome>{children}</Chrome>
    </Language.Provider>
  );
}
