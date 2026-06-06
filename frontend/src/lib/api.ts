const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getToken(): string | null {
  return typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
}

export function setTokens(access: string, refresh: string) {
  localStorage.setItem("access_token", access);
  localStorage.setItem("refresh_token", refresh);
}

export function clearTokens() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}

async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const token = getToken();
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };
  const res = await fetch(`${BASE}${path}`, { ...options, headers });
  if (res.status === 401) {
    clearTokens();
    window.location.href = "/login";
  }
  return res;
}

export const api = {
  async post(path: string, body?: unknown) {
    return apiFetch(path, { method: "POST", body: JSON.stringify(body) });
  },
  async get(path: string) {
    return apiFetch(path);
  },
  async patch(path: string, body?: unknown) {
    return apiFetch(path, { method: "PATCH", body: JSON.stringify(body) });
  },
  async delete(path: string) {
    return apiFetch(path, { method: "DELETE" }),
  },
  async upload(path: string, formData: FormData) {
    const token = getToken();
    return fetch(`${BASE}${path}`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData,
    });
  },
  streamUrl(path: string) {
    return `${BASE}${path}`;
  },
  getToken,
};
