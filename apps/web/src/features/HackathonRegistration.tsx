"use client";
import Link from "next/link";
import { useState } from "react";
import { useWords } from "@/features/Shell";

export function HackathonRegistration({ intent }: { intent: "worker" | "employer" }) {
  const { say } = useWords();
  const [step, setStep] = useState(0);
  const [role, setRole] = useState<string>(intent);
  const [name, setName] = useState("");
  const [area, setArea] = useState("Duhai");
  const [id, setId] = useState("");
  const [saved, setSaved] = useState(false);
  return (
    <div className="stack">
      {step < 3 ? (
        <form className="stack" key={step} onSubmit={e => {
          e.preventDefault();
          if (step === 2) setId(`DEMO-${role === "worker" ? "WKR" : "EMP"}-${crypto.randomUUID().slice(0, 6).toUpperCase()}`);
          setStep(step + 1);
        }}>
          <h1>{step === 0 ? say("Register with KaamPaas", "KaamPaas पर पंजीकरण करें") : step === 1 ? say("Enter verification code", "सत्यापन कोड भरें") : say("Create your profile", "अपनी प्रोफ़ाइल बनाएँ")}</h1>
          {step === 0 && <>
            <p>{say("For the hackathon, use sample details. No SMS is sent, and your profile stays in this browser tab.", "हैकाथॉन के लिए नमूना विवरण दें। SMS नहीं भेजा जाएगा और प्रोफ़ाइल इसी टैब तक सीमित है।")}</p>
            <label className="field">{say("Try as", "भूमिका चुनें")}<select value={role} onChange={e => setRole(e.target.value)}>
              <option value="worker">{say("Worker", "कामगार")}</option><option value="employer">{say("Employer", "नियोक्ता")}</option>
            </select></label>
          </>}
          {step === 1 && <label className="field">{say("Any six-digit code, e.g. 123456", "कोई भी छह अंकों का कोड, जैसे 123456")}
            <input required pattern="[0-9]{6}" maxLength={6} inputMode="numeric"/>
          </label>}
          {step === 2 && <>
            <label className="field">{say("Sample display name", "नमूना नाम")}<input value={name} required maxLength={60} onChange={e => setName(e.target.value)}/></label>
            <label className="field">{say("Work area", "काम का इलाका")}<select value={area} onChange={e => setArea(e.target.value)}>
              <option>Duhai</option><option>Loni</option><option>Modinagar</option>
            </select></label>
          </>}
          <button disabled={step === 2 && !name.trim()} className="btn primary">{step === 0 ? say("Continue", "जारी रखें") : step === 1 ? say("Verify code", "कोड जाँचें") : say("Confirm profile", "प्रोफ़ाइल की पुष्टि करें")}</button>
        </form>
      ) : <>
        <h1>{name.trim()}</h1><p>{id} · {area}</p>
        <article className="jobCard">
          <span className="tag">{say("Sample opening", "नमूना काम")}</span>
          <h3>{say("Mason · one-day shift", "राजमिस्त्री · एक दिन का काम")}</h3>
          <p>{area} · {say("₹750 per day", "₹750 प्रति दिन")}</p>
          <button className="btn primary" disabled={saved} onClick={() => setSaved(true)}>{saved ? say("Saved in this demo", "इस डेमो में सहेजा गया") : role === "worker" ? say("Try expressing interest", "रुचि दिखाकर देखें") : say("Try publishing a sample job", "नमूना काम प्रकाशित करके देखें")}</button>
        </article>
        <button className="btn light" onClick={() => { setStep(0); setName(""); setSaved(false); }}>{say("Reset demo", "डेमो रीसेट करें")}</button>
      </>}
      <Link className="link" href="/">{say("Back to KaamPaas", "KaamPaas पर लौटें")}</Link>
    </div>
  );
}
