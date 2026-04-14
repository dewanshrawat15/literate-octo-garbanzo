import { useCallback, useState } from "react";
import type { SpellingSpeed, UserProfile } from "../types";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL ?? "http://localhost:8000";
const STORAGE_KEY = "spellbee_user";

function loadStoredUser(): UserProfile | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as UserProfile) : null;
  } catch {
    return null;
  }
}

function saveUser(user: UserProfile): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
}

function clearUser(): void {
  localStorage.removeItem(STORAGE_KEY);
}

export function useAuth() {
  const [user, setUser] = useState<UserProfile | null>(loadStoredUser);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const signup = useCallback(
    async (
      username: string,
      password: string,
      spelling_speed: SpellingSpeed
    ): Promise<boolean> => {
      setError(null);
      setLoading(true);
      try {
        const res = await fetch(`${BACKEND_URL}/auth/signup`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username, password, spelling_speed }),
        });
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          setError(body?.detail ?? "Signup failed");
          return false;
        }
        const profile: UserProfile = await res.json();
        saveUser(profile);
        setUser(profile);
        return true;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Network error");
        return false;
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const login = useCallback(
    async (username: string, password: string): Promise<boolean> => {
      setError(null);
      setLoading(true);
      try {
        const res = await fetch(`${BACKEND_URL}/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username, password }),
        });
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          setError(body?.detail ?? "Invalid username or password");
          return false;
        }
        const profile: UserProfile = await res.json();
        saveUser(profile);
        setUser(profile);
        return true;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Network error");
        return false;
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const logout = useCallback(() => {
    clearUser();
    setUser(null);
    setError(null);
  }, []);

  const updateSpeed = useCallback(
    async (speed: SpellingSpeed): Promise<boolean> => {
      if (!user) return false;
      setError(null);
      setLoading(true);
      try {
        const res = await fetch(`${BACKEND_URL}/profile/speed`, {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${user.token}`,
          },
          body: JSON.stringify({ spelling_speed: speed }),
        });
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          setError(body?.detail ?? "Failed to update speed");
          return false;
        }
        const updated = { ...user, spelling_speed: speed };
        saveUser(updated);
        setUser(updated);
        return true;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Network error");
        return false;
      } finally {
        setLoading(false);
      }
    },
    [user]
  );

  return { user, error, loading, signup, login, logout, updateSpeed };
}
