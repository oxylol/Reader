import type {
  Chapter,
  ChapterInfo,
  ContinueItem,
  DiscoverItem,
  Job,
  Prefs,
  SearchRequest,
  Series,
  SourceInfo,
  StorageStats,
  User,
} from "./types";

const TOKEN_KEY = "inkvault_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(t: string) {
  localStorage.setItem(TOKEN_KEY, t);
}
export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function req<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const headers = new Headers(opts.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (opts.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(`/api${path}`, { ...opts, headers });
  if (res.status === 401) {
    clearToken();
    if (location.pathname !== "/login") location.href = "/login";
    throw new ApiError(401, "Unauthorized");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

/** Route a remote cover image through the backend proxy (hotlink-protected CDNs). */
export function coverUrl(url: string | null | undefined): string {
  if (!url) return "/icon-512.png";
  if (url.startsWith("/")) return url;
  return `/api/img?url=${encodeURIComponent(url)}`;
}

export const api = {
  // auth
  async login(username: string, password: string): Promise<string> {
    const body = new URLSearchParams({ username, password });
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });
    if (!res.ok) throw new ApiError(res.status, "Login failed");
    const data = await res.json();
    setToken(data.access_token);
    return data.access_token;
  },
  me: () => req<User>("/auth/me"),
  listUsers: () => req<User[]>("/auth/users"),
  createUser: (username: string, password: string, is_admin: boolean) =>
    req<User>("/auth/users", {
      method: "POST",
      body: JSON.stringify({ username, password, is_admin }),
    }),
  deleteUser: (id: number) =>
    req<void>(`/auth/users/${id}`, { method: "DELETE" }),

  // library
  library: () => req<Series[]>("/library"),
  continueReading: () => req<ContinueItem[]>("/library/continue"),
  unfollow: (id: number) => req<void>(`/library/${id}`, { method: "DELETE" }),

  // series
  addSeries: (source: string, source_id: string) =>
    req<Series>("/series", {
      method: "POST",
      body: JSON.stringify({ source, source_id }),
    }),
  series: (id: number) => req<Series>(`/series/${id}`),
  chapters: (id: number, refresh = false) =>
    req<Chapter[]>(`/series/${id}/chapters${refresh ? "?refresh=true" : ""}`),
  download: (id: number) =>
    req<Job>(`/series/${id}/download`, { method: "POST" }),

  // browse
  sources: () => req<SourceInfo[]>("/browse/sources"),
  trending: (shelf: string, timeframe: string) =>
    req<DiscoverItem[]>(
      `/browse/trending?shelf=${shelf}&timeframe=${timeframe}`,
    ),
  search: (body: SearchRequest) =>
    req<DiscoverItem[]>("/browse/search", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  history: () => req<{ query: string; at: string }[]>("/browse/history"),

  // reader
  chapterInfo: (id: number) => req<ChapterInfo>(`/read/chapter/${id}`),
  pageUrl: (chapterId: number, index: number) =>
    `/api/read/chapter/${chapterId}/page/${index}?t=${getToken() ?? ""}`,
  saveProgress: (
    chapter_id: number,
    page: number,
    scroll: number,
    completed: boolean,
  ) =>
    req<void>("/read/progress", {
      method: "PUT",
      body: JSON.stringify({ chapter_id, page, scroll, completed }),
    }),
  markRead: (chapterId: number, read: boolean) =>
    req<void>(`/read/chapter/${chapterId}/read?read=${read}`, {
      method: "POST",
    }),

  // prefs
  prefs: () => req<Prefs>("/prefs"),
  updatePrefs: (p: Partial<Prefs>) =>
    req<Prefs>("/prefs", { method: "PUT", body: JSON.stringify(p) }),
  seriesOverride: (id: number) =>
    req<{ reading_mode: string; rtl: boolean | null }>(`/prefs/series/${id}`),
  setSeriesOverride: (id: number, reading_mode: string, rtl: boolean | null) =>
    req<{ reading_mode: string; rtl: boolean | null }>(`/prefs/series/${id}`, {
      method: "PUT",
      body: JSON.stringify({ reading_mode, rtl }),
    }),

  // admin
  jobs: () => req<Job[]>("/admin/jobs"),
  jobForSeries: (id: number) => req<Job | null>(`/admin/jobs/series/${id}`),
  cancelJob: (id: number) =>
    req<Job>(`/admin/jobs/${id}/cancel`, { method: "POST" }),
  storage: () => req<StorageStats>("/admin/storage"),
  pruneSeries: (id: number) =>
    req<void>(`/admin/storage/series/${id}`, { method: "DELETE" }),
};

export { ApiError };
