import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import NavHubPage from "./NavHubPage";

describe("NavHubPage", () => {
  it("renders the imported navigation hub and filters links by category and search", async () => {
    render(<NavHubPage />);

    expect(screen.getByRole("heading", { name: "导航中心" })).toBeInTheDocument();
    expect(screen.getByAltText("AIHOT")).toBeInTheDocument();
    expect(screen.getByText("GitHub")).toBeInTheDocument();
    expect(screen.getByText("Claude")).toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "AI 工具" }));

    expect(screen.getByText("Perplexity")).toBeInTheDocument();
    expect(screen.queryByText("GitHub")).not.toBeInTheDocument();

    await user.type(screen.getByPlaceholderText("搜索链接..."), "搜索");

    expect(screen.getByText("Perplexity")).toBeInTheDocument();
    expect(screen.queryByText("Midjourney")).not.toBeInTheDocument();
  });
});
