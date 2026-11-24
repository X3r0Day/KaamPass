"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { Failure } from "./Common";
import { useWords } from "./Shell";

export function BrowserRegistration({ done }: { done: () => void }) {
  const { say, t } = useWords();
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  return <form className="stack" onSubmit={async e => {
    e.preventDefault();
    setBusy(true);
    setError(undefined);
    try {
      await api("/auth/browser", "POST", { code });
      done();
    } catch (e) { setError(e); }
    finally { setBusy(false); }
  }}>
    <h1>{say("Register with KaamPaas", "KaamPaas पर पंजीकरण करें")}</h1>
    <p>{say("Enter any six-digit code to continue. No SMS is sent. Your profile is linked to this browser.", "जारी रखने के लिए कोई भी छह अंकों का कोड भरें। SMS नहीं भेजा जाएगा। आपकी प्रोफ़ाइल इसी ब्राउज़र से जुड़ी है।")}</p>
    <label className="field">{say("Six-digit code", "छह अंकों का कोड")}
      <input required inputMode="numeric" pattern="[0-9]{6}" maxLength={6} value={code} onChange={e=>setCode(e.target.value)} />
    </label>
    {error != null && <Failure value={error}/>}
    <button className="btn primary" disabled={busy}>{busy ? t("loading") : say("Continue", "जारी रखें")}</button>
  </form>;
}
