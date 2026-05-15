import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import FeedPage from "./FeedPage";
import { useInfiniteFeedItems } from "../hooks/useInfiniteFeedItems";
import { useApiFeedItems } from "../hooks/useUpstreamFeedItems";

vi.mock("../hooks/useUpstreamFeedItems", () => ({
  useApiFeedItems: vi.fn(),
}));

vi.mock("../hooks/useInfiniteFeedItems", () => ({
  useInfiniteFeedItems: vi.fn(),
}));

afterEach(() => {
  cleanup();
});

const items = [
  {
    day: "5月7日",
    time: "08:30",
    source: "OpenAI",
    sourceId: "openai-news-rss",
    sourceTitle: "OpenAI News RSS",
    handle: "@openai",
    title: "OpenAI 更新",
    body: "发布说明",
    quoted: "",
    reason: "重点更新",
    tags: ["OpenAI", "产品更新"],
    hasMedia: false,
    link: "https://example.com/openai",
    origin: "collected",
  },
  {
    day: "5月7日",
    time: "09:00",
    source: "教程源",
    sourceId: null,
    sourceTitle: "教程源",
    handle: "@guide",
    title: "MCP 教程",
    body: "教程内容",
    quoted: "",
    reason: "适合深读",
    tags: ["教程/实践"],
    hasMedia: false,
    link: "https://example.com/guide",
    origin: "seed",
  },
];

describe("FeedPage", () => {
  it("applies page-level filters before rendering timeline counts", () => {
    useApiFeedItems.mockReturnValue({
      items,
      loadError: "",
    });
    useInfiniteFeedItems.mockReturnValue({
      items: [],
      loadError: "",
      hasNext: false,
      isLoading: false,
      loadMore: vi.fn(),
    });

    render(
      <FeedPage
        page={{
          title: "AI 日报",
          subtitle: "聚焦产品更新",
          metaSecondary: "研究与产品优先",
          filter: (item) => item.tags.includes("OpenAI"),
          upstreamPath: "/daily",
          progressiveReveal: false,
        }}
      />,
    );

    expect(screen.getByText("1 条结果")).toBeInTheDocument();
    expect(screen.getByText("OpenAI 更新")).toBeInTheDocument();
    expect(screen.queryByText("MCP 教程")).not.toBeInTheDocument();
  });

  it("renders the full merged timeline on /all without the extra summary panels", async () => {
    useApiFeedItems.mockReturnValue({ items: [], loadError: "" });
    useInfiniteFeedItems.mockReturnValue({
      items,
      loadError: "",
      hasNext: true,
      isLoading: false,
      loadMore: vi.fn(),
    });

    render(
      <FeedPage
        page={{
          path: "/all",
          title: "全部 AI 动态",
          subtitle: "完整浏览当前快照中的 AI 时间线条目",
          metaSecondary: "静态数据视图",
          filter: () => true,
          upstreamPath: "/all",
          progressiveReveal: false,
        }}
      />,
    );

    expect(screen.getByText("OpenAI 更新")).toBeInTheDocument();
    expect(screen.getByText("MCP 教程")).toBeInTheDocument();
    expect(screen.queryByText("采集 1 · 静态 1")).not.toBeInTheDocument();
    expect(screen.queryByText("这里是合并时间线，不是纯采集归档")).not.toBeInTheDocument();
    expect(screen.queryByText("采集来源")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "继续下拉，加载更多动态" })).toBeInTheDocument();
  });
});
