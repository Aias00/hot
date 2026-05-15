import { BrowserRouter, Route, Routes } from "react-router-dom";

import AppLayout from "../components/AppLayout";
import { AuthProvider } from "../hooks/useAuth.jsx";
import { feedPageDefinitions, infoPageDefinitions } from "../data/pages";
import AdminLayout from "../pages/admin/AdminLayout";
import AdminLogin from "../pages/admin/AdminLogin";
import AdminOverview from "../pages/admin/AdminOverview";
import CollectedHotPage from "../pages/CollectedHotPage";
import CollectorSourcesPage from "../pages/CollectorSourcesPage";
import DailyPage from "../pages/DailyPage";
import FeedPage from "../pages/FeedPage";
import InfoPage from "../pages/InfoPage";
import MpPage from "../pages/MpPage";
import NavHubPage from "../pages/NavHubPage";
import NavigationPage from "../pages/admin/NavigationPage";
import SourcesPage from "../pages/admin/SourcesPage";

export default function AppRouter({
  themePreference,
  onThemeChange,
}) {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Admin routes */}
          <Route path="/admin/login" element={<AdminLogin />} />
          <Route path="/admin" element={<AdminLayout />}>
            <Route index element={<AdminOverview />} />
            <Route path="sources" element={<SourcesPage />} />
            <Route path="navigation" element={<NavigationPage />} />
          </Route>

          {/* Main app routes */}
          <Route
            element={
              <AppLayout
                themePreference={themePreference}
                onThemeChange={onThemeChange}
              />
            }
          >
            {feedPageDefinitions.map((page) => (
              <Route
                key={page.path}
                path={page.path}
                element={<FeedPage page={page} />}
              />
            ))}
            <Route path="/daily" element={<DailyPage />} />
            <Route path="/daily/archive" element={<DailyPage />} />
            <Route path="/daily/:issueDate" element={<DailyPage />} />
            <Route path="/mp" element={<MpPage />} />
            <Route path="/collect" element={<CollectorSourcesPage />} />
            <Route path="/collected" element={<CollectedHotPage />} />
            <Route path="/nav-hub" element={<NavHubPage />} />
            {infoPageDefinitions.map((page) => (
              <Route
                key={page.path}
                path={page.path}
                element={<InfoPage page={page} />}
              />
            ))}
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
