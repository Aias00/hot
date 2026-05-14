import { useThemePreference } from "./hooks/useThemePreference";
import AppRouter from "./router/AppRouter";

export default function App() {
  const { themePreference, setThemePreference } = useThemePreference();

  return (
    <AppRouter
      themePreference={themePreference}
      onThemeChange={setThemePreference}
    />
  );
}
