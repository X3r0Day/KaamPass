import { getApps, initializeApp } from "firebase/app";
import { connectAuthEmulator, getAuth, inMemoryPersistence, setPersistence } from "firebase/auth";

let ready: ReturnType<typeof initialize> | undefined;
async function initialize() {
  const config = {
    apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
    appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
    authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
    projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  };
  if (Object.values(config).some(v => !v)) throw Error("auth_unconfigured");
  const auth = getAuth(getApps()[0] || initializeApp(config));
  const emulator = process.env.NEXT_PUBLIC_FIREBASE_AUTH_EMULATOR_URL;
  if (emulator) {
    if (!["localhost", "127.0.0.1"].includes(location.hostname) || !config.projectId?.startsWith("demo-"))
      throw Error("auth_unconfigured");
    connectAuthEmulator(auth, emulator, { disableWarnings: true });
  }
  await setPersistence(auth, inMemoryPersistence);
  return auth;
}
export function phoneAuth() { return ready ??= initialize().catch(e => { ready = undefined; throw e; }); }
