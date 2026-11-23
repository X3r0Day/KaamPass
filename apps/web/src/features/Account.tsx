"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { useLoad } from "@/lib/load";
import type { Profile, S } from "@/lib/types";
import { PhoneLogin } from "./PhoneLogin";
import { ProfileForm } from "./ProfileForm";
import { Failure, Loading } from "./Common";
import { useWords } from "./Shell";
const me = () => api<S["Me"]>("/me");
const disabled = () => Promise.resolve(null);
export function Account({
  intent = "worker",
  edit = false,
}: {
  intent?: Profile["role"];
  edit?: boolean;
}) {
  const { say, t, whatsapp, phoneAuth } = useWords();
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<unknown>();
  const state = useLoad<S["Me"] | null>(phoneAuth ? me : disabled),
    router = useRouter();
  const signedOut = state.err instanceof ApiError && state.err.status === 401;
  useEffect(() => {
    if (edit && (signedOut || state.data?.needs_onboarding))
      router.replace("/login");
    if (!edit && state.data?.profile) router.replace("/dashboard");
  }, [edit, signedOut, state.data, router]);
  let body;
  if (!phoneAuth)
    body = (
      <div className="stack">
        <h1>{say("Start on WhatsApp", "WhatsApp पर शुरू करें")}</h1>
        <p>
          {say(
            "Website SMS sign-in is not enabled. You can register and look for local jobs in the WhatsApp chat.",
            "वेबसाइट पर SMS साइन इन अभी चालू नहीं है। WhatsApp चैट में पंजीकरण और काम की खोज करें।",
          )}
        </p>
        {whatsapp && (
          <a className="btn primary" href={whatsapp}>
            {say("Open WhatsApp", "WhatsApp खोलें")}
          </a>
        )}
      </div>
    );
  else if (signedOut && !edit)
    body = (
      <>
        <PhoneLogin done={state.reload} />
        {whatsapp && (
          <a className="link" href={whatsapp}>
            {say("Register on WhatsApp instead", "WhatsApp पर पंजीकरण करें")}
          </a>
        )}
      </>
    );
  else if (state.err && !signedOut)
    body = <Failure value={state.err} retry={state.reload} />;
  else if (!edit && state.data?.can_connect)
    body = (
      <div className="stack">
        <h1>{say("Connect your existing profile", "मौजूदा प्रोफ़ाइल जोड़ें")}</h1>
        <p>
          {say(
            "Use your existing KaamPaas ID and work history instead of registering again.",
            "दोबारा पंजीकरण के बजाय मौजूदा KaamPaas ID और काम का इतिहास इस्तेमाल करें।",
          )}
        </p>
        {error != null && <Failure value={error} />}
        <button
          className="btn primary"
          disabled={connecting}
          onClick={async () => {
            setConnecting(true);
            setError(undefined);
            try {
              await api("/me/connect", "POST");
              router.replace("/dashboard");
            } catch (e) {
              setError(e);
            } finally {
              setConnecting(false);
            }
          }}
        >
          {connecting ? t("loading") : say("Connect profile", "प्रोफ़ाइल जोड़ें")}
        </button>
      </div>
    );
  else if (
    (!edit && state.data?.needs_onboarding) ||
    (edit && state.data?.profile)
  )
    body = (
      <ProfileForm
        initial={state.data?.profile || undefined}
        role={intent}
        done={() => router.replace("/dashboard")}
      />
    );
  else body = <Loading />;
  return <section className="sheet">{body}</section>;
}
