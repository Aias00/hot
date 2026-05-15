import { createContext, useCallback, useContext, useEffect, useState } from "react";

const AUTH_TOKEN_KEY = "admin_token";
const AUTH_EXPIRES_KEY = "admin_token_expires";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(AUTH_TOKEN_KEY));
  const [expiresAt, setExpiresAt] = useState(() => localStorage.getItem(AUTH_EXPIRES_KEY));
  const [isLoading, setIsLoading] = useState(false);

  const isAuthenticated = Boolean(token && expiresAt && new Date(expiresAt) > new Date());

  const login = useCallback(async (password) => {
    setIsLoading(true);
    try {
      const response = await fetch("/api/admin/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || "Login failed");
      }

      const data = await response.json();
      localStorage.setItem(AUTH_TOKEN_KEY, data.token);
      localStorage.setItem(AUTH_EXPIRES_KEY, data.expires_at);
      setToken(data.token);
      setExpiresAt(data.expires_at);
      return { success: true };
    } catch (error) {
      return { success: false, error: error.message };
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(AUTH_EXPIRES_KEY);
    setToken(null);
    setExpiresAt(null);
  }, []);

  const verifyToken = useCallback(async () => {
    if (!token) return false;

    try {
      const response = await fetch("/api/admin/auth/verify", {
        headers: { Authorization: `Bearer ${token}` },
      });
      return response.ok;
    } catch {
      return false;
    }
  }, [token]);

  // Check token validity on mount
  useEffect(() => {
    if (token && expiresAt) {
      const isExpired = new Date(expiresAt) <= new Date();
      if (isExpired) {
        logout();
      }
    }
  }, [token, expiresAt, logout]);

  const authFetch = useCallback(
    async (url, options = {}) => {
      const headers = {
        ...options.headers,
        Authorization: `Bearer ${token}`,
      };
      return fetch(url, { ...options, headers });
    },
    [token]
  );

  return (
    <AuthContext.Provider
      value={{
        token,
        isAuthenticated,
        isLoading,
        login,
        logout,
        verifyToken,
        authFetch,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
