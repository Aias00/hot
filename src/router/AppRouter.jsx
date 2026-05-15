import { BrowserRouter, Route, Routes } from "react-router-dom";

import AppLayout from "../components/AppLayout";
import { feedPageDefinitions, infoPageDefinitions } from "../data/pages";
import AboutPage from "../pages/AboutPage";
import AdminPage from "../pages/AdminPage";
import CollectedHotPage from "../pages/CollectedHotPage";
import CollectorSourcesPage from "../pages/CollectorSourcesPage";
import DailyPage from "../pages/DailyPage";
import FeedPage from "../pages/FeedPage";
import InfoPage from "../pages/InfoPage";
import MpPage from "../pages/MpPage";
import NavHubPage from "../pages/NavHubPage";

export default function AppRouter({
  themePreference,
  onThemeChange,
}) {
  return (
    <BrowserRouter>
      <Routes>
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
          <Route path="/about" element={<AboutPage />} />
          <Route path="/admin" element={<AdminPage />} />
          {infoPageDefinitions.map((page) => (
            <Route
              key={page.path}
              path={page.path}
              element={<InfoPage page={page} />}
            />
          ))}
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
