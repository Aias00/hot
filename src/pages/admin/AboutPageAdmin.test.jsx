import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import AboutPageAdmin from "./AboutPageAdmin";

function createDeferred() {
  let resolve;
  const promise = new Promise((nextResolve) => {
    resolve = nextResolve;
  });
  return { promise, resolve };
}

describe("AboutPageAdmin", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it("uploads an image and stores returned CDN URL into qr_code_url", async () => {
    const uploadedUrl = "https://static.cloudbase.eu.org/original/asset-123.png";
    const fetchMock = vi.fn(async (input, init) => {
      if (input === "/api/about") {
        return {
          ok: true,
          json: async () => ({
            title: "关于我们",
            description: "desc",
            qr_code_url: "/wechat-qr.png",
            follow_link: "",
            contact_info: "",
            links: [],
          }),
        };
      }

      if (input === "/api/admin/media-assets/upload") {
        return {
          ok: true,
          json: async () => ({
            asset_id: "asset-123",
            original_url: uploadedUrl,
            cover_url: "https://static.cloudbase.eu.org/cover/asset-123.webp",
            thumb_url: "https://static.cloudbase.eu.org/thumb/asset-123.webp",
          }),
        };
      }

      if (input === "/api/admin/about") {
        return {
          ok: true,
          json: async () => ({}),
        };
      }

      throw new Error(`Unexpected fetch call: ${input}`);
    });

    vi.stubGlobal("fetch", fetchMock);
    localStorage.setItem("admin_token", "test-token");

    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <AboutPageAdmin />
      </MemoryRouter>,
    );

    await screen.findByDisplayValue("/wechat-qr.png");

    await user.upload(
      screen.getByLabelText("上传二维码图片"),
      new File(["qr-bytes"], "qr.png", { type: "image/png" }),
    );

    expect(await screen.findByDisplayValue(uploadedUrl)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "保存更改" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/admin/about",
        expect.objectContaining({
          method: "PUT",
          headers: expect.objectContaining({
            Authorization: "Bearer test-token",
            "Content-Type": "application/json",
          }),
          body: expect.stringContaining(uploadedUrl),
        }),
      ),
    );
  });

  it("disables qr_code_url editing while an upload is in flight", async () => {
    const uploadResponse = createDeferred();
    const fetchMock = vi.fn(async (input) => {
      if (input === "/api/about") {
        return {
          ok: true,
          json: async () => ({
            title: "关于我们",
            description: "desc",
            qr_code_url: "/wechat-qr.png",
            follow_link: "",
            contact_info: "",
            links: [],
          }),
        };
      }

      if (input === "/api/admin/media-assets/upload") {
        return uploadResponse.promise;
      }

      throw new Error(`Unexpected fetch call: ${input}`);
    });

    vi.stubGlobal("fetch", fetchMock);
    localStorage.setItem("admin_token", "test-token");

    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <AboutPageAdmin />
      </MemoryRouter>,
    );

    const qrInput = await screen.findByLabelText("二维码图片 URL");
    expect(qrInput).toBeEnabled();

    await user.upload(
      screen.getByLabelText("上传二维码图片"),
      new File(["qr-bytes"], "qr.png", { type: "image/png" }),
    );

    expect(qrInput).toBeDisabled();

    uploadResponse.resolve({
      ok: true,
      json: async () => ({
        asset_id: "asset-123",
        original_url: "https://static.cloudbase.eu.org/original/asset-123.png",
        cover_url: "https://static.cloudbase.eu.org/cover/asset-123.webp",
        thumb_url: "https://static.cloudbase.eu.org/thumb/asset-123.webp",
      }),
    });

    await screen.findByDisplayValue("https://static.cloudbase.eu.org/original/asset-123.png");
    expect(qrInput).toBeEnabled();
  });
});
