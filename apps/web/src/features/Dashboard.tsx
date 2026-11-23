"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { catalog, useLoad } from "@/lib/load";
import { money, today, type Profile, type S } from "@/lib/types";
import { useWords } from "./Shell";
import { Loading, Failure } from "./Common";
import { JobCard } from "./JobCard";
import { JobForm } from "./JobForm";

function Availability({ p, done }: { p: Profile; done: () => void }) {
  const { t, say } = useWords(),
    [mode, set] = useState<S["Availability"]["mode"]>("today"),
    [until, end] = useState(today());
  const [err, fail] = useState<unknown>(),
    [busy, wait] = useState(false);
  async function change(m: typeof mode) {
    wait(true);
    fail(undefined);
    try {
      await api("/me/availability", "PUT", {
        mode: m,
        until: m === "until" ? until : null,
      });
      done();
    } catch (e) {
      fail(e);
    } finally {
      wait(false);
    }
  }
  return (
    <div className="workTop stack">
      <h2>{p.discoverable ? t("available") : t("paused")}</h2>
      <p>
        {p.discoverable
          ? say(
              "Matching employers can invite you.",
              "मेल खाने वाले नियोक्ता आपको निमंत्रण भेज सकते हैं।",
            )
          : say(
              "You can still apply. Open your profile when you want employers to find you.",
              "आप अभी भी आवेदन कर सकते हैं। जब निमंत्रण चाहें तब उपलब्धता खोलें।",
            )}{" "}
        {p.discoverable_until && p.discoverable ? p.discoverable_until : ""}
      </p>
      <form
        className="row"
        onSubmit={(e) => {
          e.preventDefault();
          void change(mode);
        }}
      >
        <label className="field">
          {say("Visibility period", "उपलब्धता अवधि")}
          <select
            value={mode}
            onChange={(e) => set(e.target.value as typeof mode)}
          >
            {(["today", "until", "ongoing"] as const).map((m) => (
              <option key={m} value={m}>
                {t(m)}
              </option>
            ))}
          </select>
        </label>
        {mode === "until" && (
          <label className="field">
            {t("until")}
            <input
              type="date"
              min={today()}
              required
              value={until}
              onChange={(e) => end(e.target.value)}
            />
          </label>
        )}
        <button className="btn primary" disabled={busy}>
          {p.discoverable ? t("save") : t("available")}
        </button>
        {p.discoverable && (
          <button
            type="button"
            className="btn light"
            disabled={busy}
            onClick={() => change("paused")}
          >
            {t("pause")}
          </button>
        )}
      </form>
      {err != null && <Failure value={err} />}
    </div>
  );
}

export function Dashboard() {
  const { t, lang, say } = useWords(),
    router = useRouter();
  const [tab, setTab] = useState<"matches" | "invitations" | "history">(
      "matches",
    ),
    [page, setPage] = useState(0);
  const load = useCallback(
    () => api<S["Board"]>(`/me/dashboard?tab=${tab}&page=${page}`),
    [tab, page],
  );
  const board = useLoad(load),
    refs = useLoad(catalog);
  const [posting, form] = useState(false),
    [err, fail] = useState<unknown>();
  useEffect(() => {
    if (
      board.err instanceof ApiError &&
      (board.err.status === 401 || board.err.message === "onboard_first")
    )
      router.replace("/login");
  }, [board.err, router]);
  async function signout() {
    try {
      await api("/auth/logout", "POST");
      window.location.replace("/");
    } catch (e) {
      fail(e);
    }
  }
  const data = board.data,
    cat = refs.data;
  if (board.err || refs.err)
    return (
      <div className="sheet">
        <Failure
          value={board.err || refs.err}
          retry={() => {
            board.reload();
            refs.reload();
          }}
        />
      </div>
    );
  if (!data || !cat)
    return (
      <div className="sheet">
        <Loading />
      </div>
    );
  const p = data.profile,
    owner = p.role === "employer";
  return (
    <div className="workspace wrap">
      <div className="spread">
        <div>
          <p className="subhead">
            {t(p.role)} / {p.public_id}
          </p>
          <h1>{p.name}</h1>
        </div>
        <div className="row">
          <Link className="btn light" href="/dashboard/edit">
            {t("edit")}
          </Link>
          <button className="link" onClick={signout}>
            {t("signout")}
          </button>
        </div>
      </div>
      {err != null && <Failure value={err} />}
      <div className="stats">
        {(owner
          ? [
              [t("jobsPosted"), data.stats.jobs_posted],
              [t("hired"), data.stats.hired],
              [t("filled"), data.stats.placements],
            ]
          : [
              [t("completed"), data.stats.completed],
              [t("filled"), data.stats.placements],
              [t("earnings"), money(data.stats.earnings || 0, lang)],
            ]
        ).map(([key, n]) => (
          <div key={key}>
            <strong>{n || 0}</strong>
            {key}
          </div>
        ))}
      </div>
      {!owner ? (
        <Availability p={p} done={board.reload} />
      ) : posting ? (
        <JobForm
          cat={cat}
          profile={p}
          done={() => {
            form(false);
            setPage(0);
            board.reload();
          }}
        />
      ) : (
        <div className="workTop spread">
          <div>
            <h2>{say("Your openings", "आपके पोस्ट किए काम")}</h2>
            <p>
              {say(
                "Post a shift or a permanent opening for a local trade.",
                "स्थानीय हुनर के लिए पाली या स्थायी नौकरी पोस्ट करें।",
              )}
            </p>
          </div>
          <button className="btn primary" onClick={() => form(true)}>
            {t("post")}
          </button>
        </div>
      )}
      {!owner ? (
        <div className="tabs">
          {(["matches", "invitations", "history"] as const).map((k) => (
            <button
              key={k}
              aria-pressed={tab === k}
              onClick={() => {
                setTab(k);
                setPage(0);
              }}
            >
              {t(k)}
            </button>
          ))}
        </div>
      ) : (
        <div className="rule" style={{ marginTop: 24 }} />
      )}
      {data.jobs.map((j) => (
        <JobCard
          key={j.id}
          j={j}
          owner={owner}
          cat={cat}
          refresh={board.reload}
        />
      ))}
      {!data.jobs.length && (
        <div className="empty">
          <h3>
            {owner
              ? say("No openings on this page", "इस पृष्ठ पर कोई काम नहीं")
              : t("empty")}
          </h3>
          <p>
            {owner
              ? say(
                  "Post a job to reach workers in its area.",
                  "काम पोस्ट करके उस इलाके के कामगारों तक पहुँचें।",
                )
              : tab === "matches"
                ? [
                    ...(p.skills || []).map(
                      (id) => cat.skills.find((s) => s.id === id)?.[lang],
                    ),
                    ...(p.kinds || []).map(t),
                    ...[p.area, ...(p.areas || [])].map(
                      (id) => cat.places.find((a) => a.id === id)?.[lang],
                    ),
                  ]
                    .filter(Boolean)
                    .join(" · ")
                : tab === "history"
                  ? say(
                      "Jobs you express interest in will appear here.",
                      "जिन कामों में आप रुचि दिखाएँगे वे यहाँ मिलेंगे।",
                    )
                  : say(
                      "Invitations from matching employers appear here.",
                      "नियोक्ताओं से मिलने वाले निमंत्रण यहाँ दिखेंगे।",
                    )}
          </p>
          {!owner && tab === "matches" && (
            <Link className="link" href="/dashboard/edit">
              {t("edit")}
            </Link>
          )}
        </div>
      )}
      <div className="actions">
        {page > 0 && (
          <button className="btn light" onClick={() => setPage(page - 1)}>
            {t("prev")}
          </button>
        )}
        {data.more && (
          <button className="btn light" onClick={() => setPage(page + 1)}>
            {t("nextPage")}
          </button>
        )}
      </div>
    </div>
  );
}
