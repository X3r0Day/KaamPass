"use client";
import dynamic from "next/dynamic";
import { useState } from "react";
import { api } from "@/lib/api";
import {
  dateLabel,
  money,
  today,
  type Catalog,
  type Job,
  type S,
} from "@/lib/types";
import { useWords } from "./Shell";
import { Failure } from "./Common";
const Listen = dynamic(() => import("./Voice").then((m) => m.Listen), {
  ssr: false,
});
type Group = "candidates" | "interests";
type Contact = { phone: string; name: string; public_id: string };
export function JobCard({
  j,
  cat,
  owner,
  refresh,
}: {
  j: Job;
  cat: Catalog;
  owner: boolean;
  refresh: () => void;
}) {
  const { t, say, lang } = useWords(),
    base = `/jobs/${j.id}`;
  const [busy, wait] = useState(false),
    [err, fail] = useState<unknown>();
  const [group, setGroup] = useState<Group | null>(null),
    [people, list] = useState<S["Candidate"][]>([]),
    [page, setPage] = useState(0);
  const [partner, showPartner] = useState<Contact | null>(null),
    [consent, agree] = useState(false),
    [pay, amount] = useState(
      j.reported_pay != null ? String(j.reported_pay / 100) : "",
    );
  const place = cat.places.find((a) => a.id === j.area),
    skill = cat.skills.find((s) => s.id === j.skill);
  async function work(task: () => Promise<void>) {
    if (busy) return;
    wait(true);
    fail(undefined);
    try {
      await task();
    } catch (e) {
      fail(e);
    } finally {
      wait(false);
    }
  }
  async function peopleFor(g: Group, n: number) {
    const data = await api<S["Candidate"][]>(`${base}/${g}?page=${n}`);
    list(data);
    setGroup(g);
    setPage(n);
  }
  function action(endpoint: string, body?: unknown, method = "POST") {
    void work(async () => {
      await api(endpoint, method, body);
      refresh();
    });
  }
  const active = j.state === "open",
    taking = active && j.deadline >= today(),
    waitingInvite = j.invitation_status === "pending";
  const trade = skill?.[lang] || j.title;
  return (
    <article className="jobCard">
      <div className="spread">
        <h3>{trade}</h3>
        <strong>
          {money(j.pay, lang)} / {t(j.unit)}
        </strong>
      </div>
      <div className="row">
        <span className="tag">{t(j.kind)}</span>
        <span className="tag">{t(j.state)}</span>
        {j.reason && <span>{t(j.reason)}</span>}
      </div>
      <p>
        {place?.[lang] || j.area} {place?.pin} • {t("starts")}:{" "}
        {dateLabel(j.starts, lang)} {j.shift_time?.slice(0, 5)}
        {j.ends && j.ends !== j.starts && ` – ${dateLabel(j.ends, lang)}`}
      </p>
      <p className="hint mini">
        {t("deadline")}: {dateLabel(j.deadline, lang)} · {j.employer}
      </p>
      {j.description && <p>{j.description}</p>}
      <Listen job={j.id} />
      {!owner && j.interested && (
        <p className="notice">
          {j.selected
            ? say(
                "You were selected for this opening.",
                "इस काम के लिए आपको चुना गया।",
              )
            : t("applied")}
        </p>
      )}
      {!owner && taking && !j.interested && (
        <div className="stack rule">
          <label className="agreement">
            <input
              type="checkbox"
              checked={consent}
              onChange={(e) => agree(e.target.checked)}
            />
            {t("share")}
          </label>
          <div className="row">
            {waitingInvite ? (
              <>
                <button
                  className="btn primary"
                  disabled={busy || !consent}
                  onClick={() =>
                    action(`/me/invitations/${j.invitation_id}/response`, {
                      accept: true,
                      share_contact: true,
                    })
                  }
                >
                  {t("accept")}
                </button>
                <button
                  className="btn light"
                  disabled={busy}
                  onClick={() =>
                    action(`/me/invitations/${j.invitation_id}/response`, {
                      accept: false,
                    })
                  }
                >
                  {t("decline")}
                </button>
              </>
            ) : (
              <button
                className="btn primary"
                disabled={!consent || busy}
                onClick={() =>
                  action(`${base}/interest`, { share_contact: true })
                }
              >
                {t("apply")}
              </button>
            )}
          </div>
        </div>
      )}
      {j.invitation_status === "declined" && (
        <p>{say("Invitation declined", "निमंत्रण अस्वीकार किया गया")}</p>
      )}
      {owner && active && (
        <div className="row">
          {(["candidates", "interests"] as const).map((g) => (
            <button
              className="btn light"
              key={g}
              disabled={busy}
              onClick={() => void work(() => peopleFor(g, 0))}
            >
              {t(g)}
            </button>
          ))}
        </div>
      )}
      {group && (
        <div className="stack review">
          <h3>{t(group)}</h3>
          {people.length === 0 && <p>{t("empty")}</p>}
          {people.map((p) => (
            <div className="spread" key={p.public_id}>
              <span>
                {p.public_id} ·{" "}
                {cat.places.find((a) => a.id === p.area)?.[lang]}
              </span>
              <button
                className="btn light"
                disabled={busy || (group === "candidates" && p.invited)}
                onClick={() =>
                  void work(async () => {
                    if (
                      group === "interests" &&
                      !window.confirm(
                        say(
                          `Assign this opening to ${p.public_id}?`,
                          `यह काम ${p.public_id} को सौंपें?`,
                        ),
                      )
                    )
                      return;
                    await api(
                      `${base}/${group === "candidates" ? "invites" : "assign"}`,
                      "POST",
                      { worker: p.public_id },
                    );
                    if (group === "candidates") await peopleFor(group, page);
                    else refresh();
                  })
                }
              >
                {group === "interests"
                  ? t("assign")
                  : p.invited
                    ? t("invited")
                    : t("invite")}
              </button>
            </div>
          ))}
          <div className="row">
            {page > 0 && (
              <button
                className="link"
                disabled={busy}
                onClick={() => void work(() => peopleFor(group, page - 1))}
              >
                {t("prev")}
              </button>
            )}
            {people.length === 12 && (
              <button
                className="link"
                disabled={busy}
                onClick={() => void work(() => peopleFor(group, page + 1))}
              >
                {t("nextPage")}
              </button>
            )}
          </div>
        </div>
      )}
      {j.state === "assigned" && (owner || j.selected) && (
        <div className="row">
          <button
            className="btn light"
            disabled={busy}
            onClick={() =>
              void work(async () =>
                showPartner(await api<Contact>(`${base}/contact`)),
              )
            }
          >
            {t("contact")}
          </button>
          {partner && (
            <a href={`tel:${partner.phone}`} className="link">
              {partner.name}: {partner.phone}
            </a>
          )}
        </div>
      )}
      {owner && ["open", "assigned"].includes(j.state) && (
        <div className="row rule">
          {j.state === "assigned" && (
            <button
              className="btn primary"
              disabled={busy}
              onClick={() => {
                if (
                  window.confirm(
                    say(
                      "Close this opening? Contact details will no longer be available.",
                      "काम बंद करें? इसके बाद संपर्क विवरण नहीं दिखेंगे।",
                    ),
                  )
                )
                  action(
                    `${base}/${j.kind === "permanent" ? "fill" : "complete"}`,
                  );
              }}
            >
              {t(j.kind === "permanent" ? "closeHire" : "closeShift")}
            </button>
          )}
          <button
            disabled={busy}
            className="link"
            onClick={() => {
              if (
                window.confirm(
                  say(
                    "Cancel this opening? This cannot be undone.",
                    "यह काम रद्द करें? इसे वापस नहीं किया जा सकेगा।",
                  ),
                )
              )
                action(`${base}/cancel`);
            }}
          >
            {t("cancel")}
          </button>
        </div>
      )}
      {!owner && j.selected && j.state === "completed" && (
        <form
          className="row rule"
          onSubmit={(e) => {
            e.preventDefault();
            action(
              `${base}/earnings`,
              { pay: Math.round(Number(pay) * 100) },
              "PUT",
            );
          }}
        >
          <label className="field">
            {t("received")}
            <input
              type="number"
              min="0"
              step=".01"
              max="10000000"
              required
              value={pay}
              onChange={(e) => amount(e.target.value)}
            />
          </label>
          <button className="btn light" disabled={busy}>
            {t("save")}
          </button>
        </form>
      )}
      {err != null && <Failure value={err} />}
    </article>
  );
}
