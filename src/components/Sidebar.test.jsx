import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import Sidebar from "./Sidebar";

vi.mock("../hooks/useNavigation.jsx", () => ({
  useNavigation: () => ({
    navItems: [
      { icon: "◫", label: "导航中心", to: "/nav-hub" },
      { icon: "☰", label: "全部 AI 动态", to: "/all" },
    ],
    loading: false,
  }),
}));

describe("Sidebar", () => {
  it("highlights the active route and exposes dark/light theme controls", () => {
    render(
      <MemoryRouter initialEntries={["/all"]}>
        <Sidebar themePreference="light" onThemeChange={vi.fn()} />
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: /全部 ai 动态/i })).toHaveClass(
      "side-link-active",
    );
    expect(screen.getByRole("link", { name: /导航中心/i })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /反馈/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /精选/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /采集管理/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /采集归档/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /关于/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /登录/i })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "浅色" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    expect(screen.queryByRole("button", { name: "跟随系统" })).not.toBeInTheDocument();
    const navLinks = screen.getAllByRole("link");
    expect(navLinks[0]).toHaveAccessibleName(/导航中心/i);
    expect(navLinks[1]).toHaveAccessibleName(/全部 ai 动态/i);
  });
});
