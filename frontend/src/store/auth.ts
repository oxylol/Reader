import { create } from "zustand";
import { api, clearToken, getToken } from "../lib/api";
import type { User } from "../lib/types";

interface AuthState {
  user: User | null;
  loading: boolean;
  init: () => Promise<void>;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

export const useAuth = create<AuthState>((set) => ({
  user: null,
  loading: true,
  init: async () => {
    if (!getToken()) {
      set({ loading: false });
      return;
    }
    try {
      const user = await api.me();
      set({ user, loading: false });
    } catch {
      clearToken();
      set({ user: null, loading: false });
    }
  },
  login: async (username, password) => {
    await api.login(username, password);
    const user = await api.me();
    set({ user });
  },
  logout: () => {
    clearToken();
    set({ user: null });
  },
}));
