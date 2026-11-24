"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { Failure } from "./Common";
import { useWords } from "./Shell";

export function BrowserRegistration({ done }: { done: () => void }) {
  const { say, t } = useWords();
  const [phone, setPhone] = useState("");
  const [enterCode, setEnterCode] = useState(false);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  return <form className="stack" onSubmit={async e => {
    e.preventDefault();
    if (!enterCode) {
      setEnterCode(true);
      return;
    }
    setBusy(true);
    setError(undefined);
    try {
      await api("/auth/browser", "POST", { code });
      done();
    } catch (e) { setError(e); }
    finally { setBusy(false); }
  }}>
    <h1>{enterCode ? say("Enter your code", "अपना कोड भरें") : say("Register with KaamPaas", "KaamPaas पर पंजीकरण करें")}</h1>
    {!enterCode ? <>
      <label className="field">{say("Mobile number", "मोबाइल नंबर")}
        <input type="tel" inputMode="tel" autoComplete="tel" placeholder="+91" maxLength={13}
          pattern="(?:[+]91)?[6-9][0-9]{9}" title={say("Enter a 10-digit Indian mobile number, with or without +91.", "+91 के साथ या बिना 10 अंकों का भारतीय मोबाइल नंबर भरें।")}
          value={phone} onChange={e => setPhone(e.target.value.replace(/[^0-9+]/g, ""))} required />
      </label>
      <p>{say("No SMS is sent. Your profile is linked to this browser, not to the number you enter.", "SMS नहीं भेजा जाएगा। आपकी प्रोफ़ाइल इस ब्राउज़र से जुड़ी है, मोबाइल नंबर से नहीं।")}</p>
    </> : <>
    <p>{say("Enter any six-digit code to continue.", "जारी रखने के लिए कोई भी छह अंकों का कोड भरें।")}</p>
    <label className="field">{say("Six-digit code", "छह अंकों का कोड")}
      <input required inputMode="numeric" pattern="[0-9]{6}" maxLength={6} value={code} onChange={e=>setCode(e.target.value)} />
    </label>
    <button type="button" className="link" disabled={busy} onClick={() => {setEnterCode(false);setCode("");setError(undefined);}}>{say("Change number", "नंबर बदलें")}</button>
    </>}
    {error != null && <Failure value={error}/>}
    <button className="btn primary" disabled={busy}>{busy ? t("loading") : say("Continue", "जारी रखें")}</button>
  </form>;
}
