"use client";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { Draft } from "@/lib/types";
import { useWords } from "./Shell";
import { Failure } from "./Common";

export function Dictate({ onText }: { onText: (s: string) => void }) {
  const { lang, t, say } = useWords(),
    [mode, set] = useState("idle"),
    [err, fail] = useState<unknown>();
  const stop = useRef<((send?: boolean) => void) | null>(null),
    alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      stop.current?.(false);
    };
  }, []);
  async function start() {
    fail(undefined);
    set("starting");
    try {
      const { startClip } = await import("@/lib/recorder");
      const end = await startClip(async (wav) => {
        if (!alive.current) return;
        set("sending");
        try {
          const result = await api<{ transcript: string }>(
            "/voice/transcribe",
            "POST",
            { wav, lang },
          );
          if (alive.current) onText(result.transcript);
        } catch (e) {
          if (alive.current) fail(e);
        } finally {
          if (alive.current) set("idle");
        }
      });
      if (!alive.current) {
        end(false);
        return;
      }
      stop.current = end;
      set("recording");
    } catch {
      fail(Error("mic"));
      set("idle");
    }
  }
  return (
    <div className="voice">
      <p className="hint">
        {say(
          "Optional: send up to 15 seconds of audio to Google for transcription. Review the words before saving.",
          "वैकल्पिक: लिखने के लिए 15 सेकंड तक की आवाज़ Google को भेजें। सहेजने से पहले शब्द जाँचें।",
        )}
      </p>
      <button
        type="button"
        className="link"
        disabled={mode === "starting" || mode === "sending"}
        onClick={() => (mode === "recording" ? stop.current?.() : void start())}
      >
        {mode === "idle"
          ? t("record")
          : mode === "recording"
            ? t("stop")
            : t("loading")}
      </button>
      {err != null && <Failure value={err} />}
    </div>
  );
}
export function Listen({ job, draft }: { job?: string; draft?: Draft }) {
  const { lang, t } = useWords();
  const [state, set] = useState("idle"),
    [err, fail] = useState<unknown>();
  const player = useRef<HTMLAudioElement | null>(null),
    generation = useRef(0);
  useEffect(
    () => () => {
      generation.current++;
      player.current?.pause();
    },
    [],
  );
  async function play() {
    if (state === "playing") {
      player.current?.pause();
      set("idle");
      return;
    }
    const id = ++generation.current;
    fail(undefined);
    set("loading");
    try {
      const res = await api<{ audio: string }>("/voice/readback", "POST", {
        lang,
        job,
        draft,
      });
      if (id !== generation.current) return;
      const audio = new Audio(`data:audio/mpeg;base64,${res.audio}`);
      player.current = audio;
      audio.onended = () => set("idle");
      await audio.play();
      set("playing");
    } catch (e) {
      if (id === generation.current) {
        fail(e);
        set("idle");
      }
    }
  }
  return (
    <div>
      <button
        type="button"
        className="btn subtle"
        disabled={state === "loading"}
        onClick={play}
      >
        {state === "playing"
          ? t("stop")
          : state === "loading"
            ? t("loading")
            : t("listen")}
      </button>
      {err != null && <Failure value={err} />}
    </div>
  );
}
