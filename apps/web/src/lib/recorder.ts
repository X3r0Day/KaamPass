export async function startClip(onStop: (wav: string) => void) {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1 },
    video: false,
  });
  let context: AudioContext | undefined;
  const cleanup = () => {
    stream.getTracks().forEach((t) => t.stop());
    if (context && context.state !== "closed") void context.close();
  };
  try {
    context = new AudioContext({ sampleRate: 16000 });
    await context.audioWorklet.addModule("/pcm-worklet.js");
    await context.resume();
    const input = context.createMediaStreamSource(stream),
      rec = new AudioWorkletNode(context, "clip-sampler");
    const silent = context.createGain();
    silent.gain.value = 0;
    input.connect(rec).connect(silent).connect(context.destination);
    const data = new Int16Array(240000);
    let size = 0,
      done = false;
    function stop(send = true) {
      if (done) return;
      done = true;
      clearTimeout(timer);
      rec.port.close();
      cleanup();
      if (!send) return;
      const wave = new ArrayBuffer(44 + size * 2),
        v = new DataView(wave);
      const str = (i: number, s: string) =>
        [...s].forEach((c, n) => v.setUint8(i + n, c.charCodeAt(0)));
      str(0, "RIFF");
      v.setUint32(4, 36 + size * 2, true);
      str(8, "WAVE");
      str(12, "fmt ");
      v.setUint32(16, 16, true);
      v.setUint16(20, 1, true);
      v.setUint16(22, 1, true);
      v.setUint32(24, 16000, true);
      v.setUint32(28, 32000, true);
      v.setUint16(32, 2, true);
      v.setUint16(34, 16, true);
      str(36, "data");
      v.setUint32(40, size * 2, true);
      for (let i = 0; i < size; i++) v.setInt16(44 + i * 2, data[i], true);
      const bytes = new Uint8Array(wave);
      let binary = "";
      for (let i = 0; i < bytes.length; i += 8192)
        binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
      onStop(btoa(binary));
    }
    const timer = setTimeout(() => stop(), 15000);
    rec.port.onmessage = (e) => {
      if (done) return;
      for (const f of e.data as Float32Array) {
        if (size >= data.length) break;
        data[size++] = Math.max(-1, Math.min(1, f)) * 32767;
      }
      if (size === data.length) stop();
    };
    return stop;
  } catch (e) {
    cleanup();
    throw e;
  }
}
