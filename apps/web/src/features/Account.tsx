"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { useLoad } from "@/lib/load";
import type { Profile, S } from "@/lib/types";
import { PhoneLogin } from "./PhoneLogin";
import { ProfileForm } from "./ProfileForm";
import { Failure, Loading } from "./Common";
const me = () => api<S["Me"]>("/me");
export function Account({
  intent = "worker",
  edit = false,
}: {
  intent?: Profile["role"];
  edit?: boolean;
}) {
  const state = useLoad(me),
    router = useRouter();
  const signedOut = state.err instanceof ApiError && state.err.status === 401;
  useEffect(() => {
    if (edit && (signedOut || state.data?.needs_onboarding))
      router.replace("/login");
    if (!edit && state.data?.profile) router.replace("/dashboard");
  }, [edit, signedOut, state.data, router]);
  let body;
  if (signedOut && !edit) body = <PhoneLogin done={state.reload} />;
  else if (state.err && !signedOut)
    body = <Failure value={state.err} retry={state.reload} />;
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
