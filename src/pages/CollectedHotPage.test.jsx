import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";

import CollectedHotPage from "./CollectedHotPage";

describe("CollectedHotPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("loads collected items and applies source filter controls", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          total_count: 1,
          has_next: false,
          facets: {
            sources: [
              { source_id: "openai-news-rss", source_title: "OpenAI News RSS", count: 1 },
              { source_id: "github-blog-rss", source_title: "GitHub Blog RSS", count: 1 },
            ],
            tags: [{ tag: "OpenAI", count: 1 }],
          },
          items: [
            {
              source_id: "openai-news-rss",
              source_title: "OpenAI News RSS",
              external_id: "a",
              canonical_url: "https://example.com/a",
              title: "Item A",
              summary: "Summary A",
              author: "OpenAI",
              published_at: "2026-05-13T10:00:00+00:00",
              created_at: "2026-05-13T10:00:00+00:00",
              tags: ["OpenAI"],
            },
          ],
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          items: [
            {
              source_id: "openai-news-rss",
              title: "OpenAI News RSS",
              enabled: true,
            },
            {
              source_id: "github-blog-rss",
              title: "GitHub Blog RSS",
              enabled: true,
            },
          ],
        }),
      })
      .mockResolvedValue({
        ok: true,
        json: async () => ({
          total_count: 1,
          has_next: false,
          facets: {
            sources: [
              { source_id: "openai-news-rss", source_title: "OpenAI News RSS", count: 1 },
              { source_id: "github-blog-rss", source_title: "GitHub Blog RSS", count: 1 },
            ],
            tags: [{ tag: "OpenAI", count: 1 }],
          },
          items: [
            {
              source_id: "openai-news-rss",
              source_title: "OpenAI News RSS",
              external_id: "a",
              canonical_url: "https://example.com/a",
              title: "Item A",
              summary: "Summary A",
              author: "OpenAI",
              published_at: "2026-05-13T10:00:00+00:00",
              created_at: "2026-05-13T10:00:00+00:00",
              tags: ["OpenAI"],
            },
          ],
        }),
      });

    vi.stubGlobal("fetch", fetchMock);

    render(<CollectedHotPage />);

    await waitFor(() => expect(screen.getByText("Item A")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: /^全部层级/ })).toBeInTheDocument();
    expect(screen.getAllByText("模型与研究").length).toBeGreaterThan(0);

    const user = userEvent.setup();
    await user.selectOptions(screen.getAllByRole("combobox")[0], "openai-news-rss");
    await user.click(screen.getByRole("button", { name: /^OpenAI\s*1$/ }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/api/collected?"),
      ),
    );

    await user.click(screen.getByRole("button", { name: /^GitHub Blog RSS\s*1$/ }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([path]) =>
            typeof path === "string" &&
            path.includes("/api/collected?") &&
            path.includes("source_ids=openai-news-rss%2Cgithub-blog-rss"),
        ),
      ).toBe(true),
    );
  });
});
