import { createContext, useContext, useState, useEffect } from "react";
import client from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const stored = localStorage.getItem("careerai_user");
    return stored ? JSON.parse(stored) : null;
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("careerai_token");
    if (token && !user) {
      // token exists but no cached user - try to refresh profile
      client
        .get("/profile/me")
        .then((res) => {
          const u = res.data.user;
          setUser(u);
          localStorage.setItem("careerai_user", JSON.stringify(u));
        })
        .catch(() => {
          localStorage.removeItem("careerai_token");
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const login = async (email, password) => {
    const res = await client.post("/auth/login", { email, password });
    localStorage.setItem("careerai_token", res.data.token);
    localStorage.setItem("careerai_user", JSON.stringify(res.data.user));
    setUser(res.data.user);
    return res.data.user;
  };

  const signup = async (name, email, password, stream) => {
    const res = await client.post("/auth/signup", { name, email, password, stream });
    localStorage.setItem("careerai_token", res.data.token);
    localStorage.setItem("careerai_user", JSON.stringify(res.data.user));
    setUser(res.data.user);
    return res.data.user;
  };

  const logout = () => {
    localStorage.removeItem("careerai_token");
    localStorage.removeItem("careerai_user");
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, setUser, login, signup, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
