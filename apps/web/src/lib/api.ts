export class ApiError extends Error {
  constructor(
    public status: number,
    code: string,
  ) {
    super(code);
  }
}

let csrf: Promise<string> | undefined;
async function token() {
  return (csrf ??= fetch("/api/auth/csrf", { cache: "no-store" })
    .then(async (r) => {
      if (!r.ok) throw new ApiError(r.status, "connection");
      return (await r.json()).token as string;
    })
    .catch((e) => {
      csrf = undefined;
      throw e;
    }));
}

export async function api<T>(
  path: string,
  method = "GET",
  data?: unknown,
): Promise<T> {
  const headers: Record<string, string> = {};
  if (method !== "GET") headers["X-CSRF-Token"] = await token();
  if (data !== undefined) headers["Content-Type"] = "application/json";
  const r = await fetch("/api" + path, {
    method,
    headers,
    credentials: "same-origin",
    cache: "no-store",
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) {
    if (body.detail === "csrf" || r.status === 401) csrf = undefined;
    throw new ApiError(
      r.status,
      typeof body.detail === "string" ? body.detail : "connection",
    );
  }
  if (path === "/auth/session" || path === "/auth/browser") csrf = Promise.resolve(body.token);
  if (path === "/auth/logout") csrf = undefined;
  return body as T;
}
