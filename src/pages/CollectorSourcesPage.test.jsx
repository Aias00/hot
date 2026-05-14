import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";

import CollectorSourcesPage from "./CollectorSourcesPage";

describe("CollectorSourcesPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("loads adapter kinds and existing sources, then triggers dry-run execution", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ items: ["rss-generic"] }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          items: [
            {
              source_id: "openai-news-rss",
              adapter_kind: "rss-generic",
              title: "OpenAI News RSS",
              description: "sample",
              enabled: true,
              base_url: null,
              seed_urls: ["https://openai.com/news/rss.xml"],
              config_json: {},
            },
            {
              source_id: "aws-machine-learning-blog-rss",
              adapter_kind: "rss-generic",
              title: "AWS Machine Learning Blog RSS",
              description: "sample",
              enabled: true,
              base_url: null,
              seed_urls: ["https://aws.amazon.com/blogs/machine-learning/feed/"],
              config_json: {},
            },
          ],
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          items: [
            {
              run_id: "run-1",
              source_id: "openai-news-rss",
              status: "completed",
              summary: { normalized_count: 2 },
            },
            {
              run_id: "run-aws",
              source_id: "aws-machine-learning-blog-rss",
              status: "completed",
              summary: { normalized_count: 3 },
            },
          ],
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          run_id: "run-2",
          workflow: "hot-collect",
          status: "completed",
          summary: { discovered_count: 2, normalized_count: 2 },
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          items: [
            {
              run_id: "run-2",
              source_id: "rss-generic-sample",
              status: "completed",
              summary: { normalized_count: 2 },
            },
          ],
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          run: {
            run_id: "run-2",
            source_id: "openai-news-rss",
            status: "completed",
            summary: { normalized_count: 2 },
          },
          events: [{ node: "discover_candidates", message: "ok", created_at: "now" }],
        }),
      });

    vi.stubGlobal("fetch", fetchMock);

    render(<CollectorSourcesPage />);

    await waitFor(() =>
      expect(screen.getByText("OpenAI News RSS")).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: /^全部层级/ })).toBeInTheDocument();
    expect(screen.getByText(/先 Dry run，再正式采集/)).toBeInTheDocument();
    expect(screen.getByText(/重点看运行诊断/)).toBeInTheDocument();
    expect(screen.getByText("AWS Machine Learning Blog RSS")).toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /云与推理基础设施/ }));
    expect(screen.queryByText("OpenAI News RSS")).not.toBeInTheDocument();
    expect(screen.getByText("AWS Machine Learning Blog RSS")).toBeInTheDocument();
    expect(screen.getByText(/最近运行 · 1/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Dry run" }));

    await waitFor(() =>
      expect(screen.getByText(/最近执行/)).toBeInTheDocument(),
    );
    expect(fetchMock).toHaveBeenCalledWith("/api/collect/adapter-kinds", undefined);
    expect(fetchMock).toHaveBeenCalledWith("/api/collect/sources", undefined);
    expect(fetchMock).toHaveBeenCalledWith("/api/collect/runs?limit=20", undefined);
  });
});
