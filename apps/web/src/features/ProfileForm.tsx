"use client";
import { useState } from "react";
import dynamic from "next/dynamic";
import { api } from "@/lib/api";
import { catalog, useLoad } from "@/lib/load";
import type { Catalog, Lang, Profile, S } from "@/lib/types";
import { useWords } from "./Shell";
import { Failure, Loading } from "./Common";
const Dictate = dynamic(() => import("./Voice").then((m) => m.Dictate), {
  ssr: false,
});
const toggle = <T,>(list: T[], key: T) =>
  list.includes(key) ? list.filter((k) => k !== key) : [...list, key];
export function ProfileForm(props: {
  initial?: Profile;
  role: Profile["role"];
  done: () => void;
}) {
  const data = useLoad(catalog);
  if (data.err) return <Failure value={data.err} retry={data.reload} />;
  return data.data ? <Fields {...props} cat={data.data} /> : <Loading />;
}
function Fields({
  initial,
  role: defaultRole,
  done,
  cat,
}: {
  initial?: Profile;
  role: Profile["role"];
  done: () => void;
  cat: Catalog;
}) {
  const { lang, setLang, t, say, phoneAuth } = useWords();
  const [role, setRole] = useState(initial?.role || defaultRole),
    [name, setName] = useState(initial?.name || "");
  const [area, setArea] = useState(initial?.area || ""),
    [areas, setAreas] = useState<string[]>(initial?.areas || []);
  const [skills, setSkills] = useState<string[]>(initial?.skills || []),
    [kinds, setKinds] = useState<("short_term" | "permanent")[]>(
      initial?.kinds || [],
    );
  const [review, setReview] = useState(false),
    [busy, setBusy] = useState(false),
    [err, setErr] = useState<unknown>(),
    [heard, setHeard] = useState("");
  const isWorker = role === "worker";
  const skillLabel = (id: string) =>
    cat.skills.find((s) => s.id === id)?.[lang];
  const placeLabel = (id: string) => {
    const a = cat.places.find((p) => p.id === id);
    return a ? `${a[lang]} (${a.pin})` : "";
  };
  async function submit() {
    setErr(undefined);
    if (isWorker && (!skills.length || !kinds.length)) {
      setErr(Error("choose_trade_type"));
      return;
    }
    if (!review) {
      setReview(true);
      return;
    }
    const fields: S["ProfileFields"] = {
      name: name.trim(),
      lang,
      area,
      areas: isWorker ? areas : [],
      skills: isWorker ? skills : [],
      kinds: isWorker ? kinds : [],
    };
    setBusy(true);
    try {
      await api(
        initial ? "/me" : "/me/onboarding",
        initial ? "PATCH" : "POST",
        initial ? fields : { ...fields, role },
      );
      done();
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  }
  const tradeSuggestion = heard.trim().toLocaleLowerCase();
  const suggested = tradeSuggestion
    ? cat.skills.filter((s) =>
        [s.en, s.hi, ...s.aliases.split("|")].some((k) =>
          tradeSuggestion.includes(k.toLowerCase()),
        ),
      )
    : [];
  return (
    <>
      <p className="subhead">
        {initial?.public_id || (phoneAuth ? say("Phone verified", "नंबर सत्यापित") : say("Registration", "पंजीकरण"))}
      </p>
      <h1>
        {review
          ? t("review")
          : initial
            ? t("edit")
            : say("Set up your work profile", "अपनी काम की प्रोफ़ाइल बनाएँ")}
      </h1>
      <form
        className="stack"
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
      >
        {review ? (
          <div className="review stack">
            <h3>{name}</h3>
            <p>
              {t(role)} / {placeLabel(area)}
            </p>
            {isWorker && (
              <>
                <p>
                  {skills.map(skillLabel).join(", ")} —{" "}
                  {kinds.map(t).join(", ")}
                </p>
                <p>{areas.map(placeLabel).join(", ")}</p>
              </>
            )}
            {!initial && isWorker && (
              <p>
                {say(
                  "Your profile starts paused. You decide when employers can find you.",
                  "आपकी प्रोफ़ाइल अभी छिपी रहेगी। आप तय करें कि नियोक्ता आपको कब खोज पाएँ।",
                )}
              </p>
            )}
          </div>
        ) : (
          <>
            {!initial && (
              <fieldset>
                <legend>
                  {say("How will you use KaamPaas?", "आप क्या करना चाहते हैं?")}
                </legend>
                <div className="checks">
                  {(["worker", "employer"] as const).map((r) => (
                    <label className="choice" key={r}>
                      <input
                        type="radio"
                        checked={role === r}
                        onChange={() => setRole(r)}
                      />
                      {t(r)}
                    </label>
                  ))}
                </div>
              </fieldset>
            )}
            <label className="field">
              {t("name")}
              <input
                required
                maxLength={80}
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </label>
            <label className="field">
              {t("language")}
              <select
                value={lang}
                onChange={(e) => setLang(e.target.value as Lang)}
              >
                <option value="hi">हिन्दी</option>
                <option value="en">English</option>
              </select>
            </label>
            <label className="field">
              {t("area")}
              <select
                required
                value={area}
                onChange={(e) => {
                  setArea(e.target.value);
                  setAreas(areas.filter((v) => v !== e.target.value));
                }}
              >
                <option value="">{t("choose")}</option>
                {cat.places.map((p) => (
                  <option key={p.id} value={p.id}>
                    {placeLabel(p.id)}
                  </option>
                ))}
              </select>
            </label>
            <p className="hint mini">
              {say(
                "Only the postal areas listed here are covered. Pick a place you can work in.",
                "अभी केवल सूची में दिए डाक क्षेत्र शामिल हैं। जहाँ काम कर सकते हैं वही इलाका चुनें।",
              )}
            </p>
            {isWorker && (
              <>
                <fieldset>
                  <legend>{t("trade")}</legend>
                  <div className="checks">
                    {cat.skills.map((s) => (
                      <label key={s.id} className="choice">
                        <input
                          type="checkbox"
                          checked={skills.includes(s.id)}
                          onChange={() => setSkills(toggle(skills, s.id))}
                        />
                        {s[lang]}
                      </label>
                    ))}
                  </div>
                </fieldset>
                <Dictate onText={setHeard} />
                {heard && (
                  <div className="notice">
                    <label className="field">
                      {say("Words heard", "सुने गए शब्द")}
                      <input
                        value={heard}
                        onChange={(e) => setHeard(e.target.value)}
                      />
                    </label>
                    {suggested.length
                      ? suggested.map((s) => (
                          <button
                            type="button"
                            className="link"
                            key={s.id}
                            onClick={() => {
                              setSkills([...new Set([...skills, s.id])]);
                              setHeard("");
                            }}
                          >
                            {say("Choose", "चुनें")} {s[lang]}
                          </button>
                        ))
                      : say(
                          "Choose the correct trade above.",
                          "ऊपर सही हुनर चुनें।",
                        )}
                  </div>
                )}
                <fieldset>
                  <legend>{t("selectTypes")}</legend>
                  <div className="checks">
                    {(["short_term", "permanent"] as const).map((k) => (
                      <label className="choice" key={k}>
                        <input
                          type="checkbox"
                          checked={kinds.includes(k)}
                          onChange={() => setKinds(toggle(kinds, k))}
                        />
                        {t(k)}
                      </label>
                    ))}
                  </div>
                </fieldset>
                <details>
                  <summary className="link">{t("extras")}</summary>
                  <div className="checks">
                    {cat.places
                      .filter((p) => p.id !== area)
                      .map((p) => (
                        <label className="choice" key={p.id}>
                          <input
                            type="checkbox"
                            disabled={
                              !areas.includes(p.id) && areas.length === 3
                            }
                            checked={areas.includes(p.id)}
                            onChange={() => setAreas(toggle(areas, p.id))}
                          />
                          {placeLabel(p.id)}
                        </label>
                      ))}
                  </div>
                </details>
              </>
            )}
          </>
        )}
        {err != null && <Failure value={err} />}
        <div className="row">
          <button className="btn primary" disabled={busy}>
            {busy
              ? t("loading")
              : review
                ? initial
                  ? t("save")
                  : t("confirm")
                : t("review")}
          </button>
          {review && (
            <button
              type="button"
              className="btn light"
              disabled={busy}
              onClick={() => setReview(false)}
            >
              {t("back")}
            </button>
          )}
        </div>
      </form>
    </>
  );
}
