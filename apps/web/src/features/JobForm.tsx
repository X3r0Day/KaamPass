"use client";
import dynamic from "next/dynamic";
import { useRef, useState } from "react";
import { api } from "@/lib/api";
import {
  dateLabel,
  money,
  today,
  type Catalog,
  type Draft,
  type Profile,
  type S,
} from "@/lib/types";
import { Failure } from "./Common";
import { useWords } from "./Shell";
const Dictate = dynamic(() => import("./Voice").then((m) => m.Dictate), {
  ssr: false,
});
const Listen = dynamic(() => import("./Voice").then((m) => m.Listen), {
  ssr: false,
});

export function JobForm({
  cat,
  profile,
  done,
}: {
  cat: Catalog;
  profile: Profile;
  done: () => void;
}) {
  const { lang, t, say } = useWords(),
    [draft, set] = useState<Draft>(() => ({
      skill: "",
      area: profile.area,
      kind: "short_term",
      starts: today(),
      deadline: today(),
      ends: today(),
      shift_time: "09:00",
      pay: 0,
      unit: "day",
      title: "",
      description: "",
    }));
  const [rupees, setRupees] = useState(""),
    [review, showReview] = useState(false),
    [agree, consent] = useState(false);
  const [err, fail] = useState<unknown>(),
    [busy, wait] = useState(false);
  const key = useRef("");
  function change(part: Partial<Draft>) {
    key.current = "";
    set((d) => ({ ...d, ...part }));
  }
  const place = cat.places.find((p) => p.id === draft.area),
    skill = cat.skills.find((s) => s.id === draft.skill);
  async function submit() {
    fail(undefined);
    if (
      !draft.skill ||
      !place ||
      draft.pay < 1 ||
      draft.starts < draft.deadline ||
      draft.deadline < today() ||
      (draft.kind === "short_term" &&
        (!draft.ends ||
          draft.ends < draft.starts ||
          (draft.starts === draft.ends && !draft.shift_time)))
    ) {
      fail(Error("invalid_fields"));
      return;
    }
    if (!review) {
      showReview(true);
      return;
    }
    if (!agree) {
      fail(Error("consent"));
      return;
    }
    key.current ||= crypto.randomUUID();
    wait(true);
    try {
      const payload: S["Publish"] = {
        ...draft,
        submission_key: key.current,
        share_contact: true,
      };
      await api("/jobs", "POST", payload);
      done();
    } catch (e) {
      fail(e);
    } finally {
      wait(false);
    }
  }
  return (
    <section className="panel">
      <h2>{review ? t("review") : t("post")}</h2>
      <form
        className="stack"
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
      >
        {review ? (
          <>
            <div className="review stack">
              <h3>
                {skill?.[lang]} — {money(draft.pay, lang)}/{t(draft.unit)}
              </h3>
              <p>
                {t(draft.kind)} / {place?.[lang]} ({place?.pin})
              </p>
              <p>
                {t("starts")}: {dateLabel(draft.starts, lang)}{" "}
                {draft.shift_time}{" "}
                {draft.ends && `— ${dateLabel(draft.ends, lang)}`}
              </p>
              <p>
                {t("deadline")}: {dateLabel(draft.deadline, lang)}
              </p>
              {draft.description && <p>{draft.description}</p>}
              <Listen draft={draft} />
            </div>
            <label className="agreement">
              <input
                required
                type="checkbox"
                checked={agree}
                onChange={(e) => consent(e.target.checked)}
              />
              {profile.realm === "browser" ? say("Confirm these details are ready to publish.", "पुष्टि करें कि ये विवरण प्रकाशित करने के लिए तैयार हैं।") : t("share")}
            </label>
          </>
        ) : (
          <>
            <label className="field">
              {t("trade")}
              <select
                required
                value={draft.skill}
                onChange={(e) => change({ skill: e.target.value })}
              >
                <option value="">{t("choose")}</option>
                {cat.skills.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s[lang]}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              {t("area")}
              <select
                required
                value={draft.area}
                onChange={(e) => change({ area: e.target.value })}
              >
                {cat.places.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p[lang]} ({p.pin})
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              {t("kind")}
              <select
                value={draft.kind}
                onChange={(e) => {
                  const k = e.target.value as Draft["kind"];
                  change({
                    kind: k,
                    ends: k === "permanent" ? null : draft.starts,
                    unit: k === "permanent" ? "month" : "day",
                    shift_time: k === "permanent" ? null : "09:00",
                  });
                }}
              >
                {(["short_term", "permanent"] as const).map((k) => (
                  <option key={k} value={k}>
                    {t(k)}
                  </option>
                ))}
              </select>
            </label>
            <div className="two">
              <label className="field">
                {t("pay")}
                <input
                  type="number"
                  inputMode="decimal"
                  min="0.01"
                  max="10000000"
                  step=".01"
                  required
                  value={rupees}
                  onChange={(e) => {
                    setRupees(e.target.value);
                    change({ pay: Math.round(Number(e.target.value) * 100) });
                  }}
                />
              </label>
              <label className="field">
                {t("unit")}
                <select
                  value={draft.unit}
                  onChange={(e) =>
                    change({ unit: e.target.value as Draft["unit"] })
                  }
                >
                  {(["day", "shift", "month", "job"] as const).map((u) => (
                    <option key={u} value={u}>
                      {t(u)}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="two">
              <label className="field">
                {t("starts")}
                <input
                  type="date"
                  required
                  min={today()}
                  value={draft.starts}
                  onChange={(e) => {
                    const starts = e.target.value;
                    change({
                      starts,
                      ends:
                        draft.kind === "short_term" &&
                        (!draft.ends || draft.ends < starts)
                          ? starts
                          : draft.ends,
                    });
                  }}
                />
              </label>
              <label className="field">
                {t("deadline")}
                <input
                  type="date"
                  required
                  min={today()}
                  max={draft.starts}
                  value={draft.deadline}
                  onChange={(e) => change({ deadline: e.target.value })}
                />
              </label>
            </div>
            {draft.kind === "short_term" && (
              <div className="two">
                <label className="field">
                  {t("ends")}
                  <input
                    type="date"
                    min={draft.starts}
                    required
                    value={draft.ends || ""}
                    onChange={(e) => change({ ends: e.target.value })}
                  />
                </label>
                <label className="field">
                  {t("time")}
                  <input
                    type="time"
                    required={draft.ends === draft.starts}
                    value={draft.shift_time || ""}
                    onChange={(e) =>
                      change({ shift_time: e.target.value || null })
                    }
                  />
                </label>
              </div>
            )}
            <label className="field">
              {t("description")}
              <textarea
                maxLength={1200}
                value={draft.description}
                onChange={(e) => change({ description: e.target.value })}
              />
            </label>
            <Dictate onText={(text) => change({ description: text })} />
          </>
        )}
        {err != null && <Failure value={err} />}
        <div className="actions">
          <button className="btn primary" disabled={busy}>
            {busy ? t("loading") : review ? t("publish") : t("review")}
          </button>
          <button
            type="button"
            className="btn light"
            disabled={busy}
            onClick={() => (review ? showReview(false) : done())}
          >
            {review ? t("back") : say("Close form", "फ़ॉर्म बंद करें")}
          </button>
        </div>
      </form>
    </section>
  );
}
