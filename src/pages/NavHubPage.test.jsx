import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import NavHubPage from "./NavHubPage";

// Mock categories data
const mockCategories = [
  {
    id: "dev",
    name: "开发工具",
    icon: '<svg viewBox="0 0 24 24"></svg>',
    color: "#7dd3fc",
    links: [
      { title: "GitHub", url: "https://github.com", description: "代码托管" },
    ],
  },
  {
    id: "ai",
    name: "AI 工具",
    icon: '<svg viewBox="0 0 24 24"></svg>',
    color: "#a78bfa",
    links: [
      { title: "Claude", url: "https://claude.ai", description: "AI 助手" },
      { title: "Perplexity", url: "https://perplexity.ai", description: "AI 搜索" },
      { title: "Midjourney", url: "https://midjourney.com", description: "AI 绘画" },
    ],
  },
];

describe("NavHubPage", () => {
  beforeEach(() => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockCategories),
      })
    );
  });

  it("renders the navigation hub and filters links by category and search", async () => {
    render(<NavHubPage />);

    expect(screen.getByRole("heading", { name: "导航中心" })).toBeInTheDocument();
    expect(screen.getByAltText("AI Digest")).toBeInTheDocument();

    // Wait for data to load
    await waitFor(() => {
      expect(screen.getByText("GitHub")).toBeInTheDocument();
      expect(screen.getByText("Claude")).toBeInTheDocument();
    });

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "AI 工具" }));

    expect(screen.getByText("Perplexity")).toBeInTheDocument();
    expect(screen.queryByText("GitHub")).not.toBeInTheDocument();

    await user.type(screen.getByPlaceholderText("搜索链接..."), "搜索");

    expect(screen.getByText("Perplexity")).toBeInTheDocument();
    expect(screen.queryByText("Midjourney")).not.toBeInTheDocument();
  });
});
