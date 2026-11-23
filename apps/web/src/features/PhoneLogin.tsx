"use client";
import { useEffect, useRef, useState } from "react";
import type { ConfirmationResult, RecaptchaVerifier } from "@firebase/auth";
import { api } from "@/lib/api";
import { useWords } from "./Shell";
import { Failure } from "./Common";

const westernDigits = (value: string) =>
  value.replace(/[०-९]/g, (digit) => String(digit.charCodeAt(0) - 0x0966));

export function PhoneLogin({ done }: { done: () => void }) {
  const { lang, t, say } = useWords();
  const [phone, setPhone] = useState(""),
    [code, setCode] = useState("");
  const [confirmation, setConfirmation] = useState<ConfirmationResult | null>(
    null,
  );
  const [busy, setBusy] = useState(false),
    [err, setErr] = useState<unknown>(),
    [cooldown, setCooldown] = useState(0);
  const verifier = useRef<RecaptchaVerifier | null>(null);
  useEffect(() => () => verifier.current?.clear(), []);
  useEffect(() => {
    if (!cooldown) return;
    const id = setTimeout(() => setCooldown((c) => Math.max(0, c - 1)), 1000);
    return () => clearTimeout(id);
  }, [cooldown]);
  async function send() {
    setBusy(true);
    setErr(undefined);
    try {
      const compact = westernDigits(phone).replace(/[\s()-]/g, "");
      const number = /^\d{10}$/.test(compact) ? "+91" + compact : compact;
      if (!/^\+[1-9]\d{7,14}$/.test(number))
        throw Error("auth/invalid-phone-number");
      const [{ phoneAuth }, sdk] = await Promise.all([
        import("@/lib/firebase"),
        import("@firebase/auth"),
      ]);
      const auth = await phoneAuth();
      auth.languageCode = lang;
      verifier.current?.clear();
      verifier.current = new sdk.RecaptchaVerifier(auth, "phone-challenge", {
        size: "invisible",
      });
      setConfirmation(
        await sdk.signInWithPhoneNumber(auth, number, verifier.current),
      );
      setCode("");
      setCooldown(45);
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  }
  async function verify() {
    if (!confirmation) return;
    setBusy(true);
    setErr(undefined);
    try {
      const { user } = await confirmation.confirm(code);
      try {
        await api("/auth/session", "POST", {
          id_token: await user.getIdToken(),
        });
      } finally {
        const [{ signOut }, { phoneAuth }] = await Promise.all([
          import("@firebase/auth"),
          import("@/lib/firebase"),
        ]);
        await signOut(await phoneAuth());
      }
      done();
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <p className="subhead">{say("Phone sign-in", "मोबाइल से साइन इन")}</p>
      <h1>
        {confirmation
          ? say("Check your SMS", "अपना SMS देखें")
          : say("Start with your number", "मोबाइल नंबर से शुरू करें")}
      </h1>
      <p className="hint">
        {confirmation
          ? say(
              `Enter the code sent to ${phone}.`,
              ` ${phone} पर भेजा कोड दर्ज करें।`,
            )
          : say(
              "Use the number you can receive a text on. It can be a basic phone.",
              "वह नंबर दें जिस पर SMS मिल सके। साधारण फ़ोन भी चलेगा।",
            )}
      </p>
      <form
        className="stack"
        onSubmit={(e) => {
          e.preventDefault();
          void (confirmation ? verify() : send());
        }}
      >
        {confirmation ? (
          <label className="field">
            {t("code")}
            <input
              autoComplete="one-time-code"
              inputMode="numeric"
              pattern="[0-9]{6}"
              maxLength={6}
              value={code}
              onChange={(e) => setCode(westernDigits(e.target.value))}
              required
            />
          </label>
        ) : (
          <>
            <label className="field">
              {t("phone")}
              <input
                type="tel"
                autoComplete="tel"
                maxLength={22}
                placeholder="+91"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                required
              />
            </label>
            <label className="agreement">
              <input type="checkbox" required />
              {say(
                "Send me an SMS to verify this number. Google processes it for verification and abuse prevention. Carrier rates may apply.",
                "इस नंबर की पुष्टि के लिए SMS भेजें। Google सत्यापन और दुरुपयोग रोकने के लिए नंबर का उपयोग करता है। SMS शुल्क लागू हो सकता है।",
              )}
            </label>
          </>
        )}
        <div id="phone-challenge" />
        {err != null && <Failure value={err} />}
        <button className="btn primary" disabled={busy}>
          {busy ? t("loading") : confirmation ? t("verify") : t("send")}
        </button>
        {confirmation && (
          <div className="row">
            <button
              type="button"
              className="link"
              disabled={busy || cooldown > 0}
              onClick={send}
            >
              {t("resend")} {cooldown > 0 ? `(${cooldown})` : ""}
            </button>
            <button
              type="button"
              className="link"
              disabled={busy}
              onClick={() => {
                setConfirmation(null);
                setCode("");
                setErr(undefined);
              }}
            >
              {say("Change number", "नंबर बदलें")}
            </button>
          </div>
        )}
      </form>
    </>
  );
}
