import { useEffect } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./store/auth";
import { useQuery } from "@tanstack/react-query";
import { api } from "./lib/api";
import BottomNav from "./components/BottomNav";
import Login from "./pages/Login";
import Library from "./pages/Library";
import Browse from "./pages/Browse";
import SeriesPage from "./pages/SeriesPage";
import Reader from "./pages/Reader";
import Settings from "./pages/Settings";

function Protected({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="spinner" />;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  const init = useAuth((s) => s.init);
  const user = useAuth((s) => s.user);
  const location = useLocation();

  useEffect(() => {
    init();
  }, [init]);

  // Apply theme from prefs once logged in.
  const { data: prefs } = useQuery({
    queryKey: ["prefs"],
    queryFn: api.prefs,
    enabled: !!user,
  });
  useEffect(() => {
    document.documentElement.setAttribute(
      "data-theme",
      prefs?.theme === "light" ? "light" : "dark",
    );
  }, [prefs?.theme]);

  const isReader = location.pathname.startsWith("/read/");
  const showNav = !!user && !isReader && location.pathname !== "/login";

  return (
    <div className="app">
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <Protected>
              <Library />
            </Protected>
          }
        />
        <Route
          path="/browse"
          element={
            <Protected>
              <Browse />
            </Protected>
          }
        />
        <Route
          path="/series/:id"
          element={
            <Protected>
              <SeriesPage />
            </Protected>
          }
        />
        <Route
          path="/read/:chapterId"
          element={
            <Protected>
              <Reader />
            </Protected>
          }
        />
        <Route
          path="/settings"
          element={
            <Protected>
              <Settings />
            </Protected>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      {showNav && <BottomNav isAdmin={!!user?.is_admin} />}
    </div>
  );
}
