"use client";
import Link from "next/link";
import { ApiError } from "@/lib/api";
import { useWords } from "./Shell";
export function Failure({
  value,
  retry,
}: {
  value: unknown;
  retry?: () => void;
}) {
  const { t, error } = useWords();
  return (
    <div className="error" role="alert">
      {error(value)}{" "}
      {value instanceof ApiError && value.status === 401 ? (
        <Link className="link" href="/login">
          {t("signin")}
        </Link>
      ) : (
        retry && (
          <button className="link" onClick={retry}>
            {t("retry")}
          </button>
        )
      )}
    </div>
  );
}
export function Loading() {
  const { t } = useWords();
  return (
    <p role="status" className="notice">
      {t("loading")}
    </p>
  );
}
