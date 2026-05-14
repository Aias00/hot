import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import PageHeader from "./PageHeader";
import SearchToolbar from "./SearchToolbar";

describe("PageHeader", () => {
  it("renders title, meta, and delegates query changes", async () => {
    const user = userEvent.setup();
    const onQueryChange = vi.fn();

    function Wrapper() {
      const [query, setQuery] = useState("");

      return (
        <PageHeader
          title="精选"
          subtitle="AI 自动挑选的高价值内容"
          metaPrimary="35 条结果"
          metaSecondary="静态设计 fork"
        >
          <SearchToolbar
            query={query}
            onQueryChange={(nextValue) => {
              setQuery(nextValue);
              onQueryChange(nextValue);
            }}
          />
        </PageHeader>
      );
    }

    render(<Wrapper />);

    expect(screen.getByRole("heading", { name: "精选" })).toBeInTheDocument();
    expect(screen.getByText("35 条结果")).toBeInTheDocument();

    await user.type(screen.getByLabelText("搜索标题或摘要"), "AI");

    expect(onQueryChange).toHaveBeenLastCalledWith("AI");
  });
});
