import { expect, test } from "@playwright/test";

test("route navigation, search, and theme persistence work across pages", async ({
  page,
}) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "精选" })).toBeVisible();
  await expect(page.locator(".timeline-item")).toHaveCount(5);
  await expect(page.getByText("继续下拉，自动加载 5 条")).toBeVisible();

  const readResultCount = async () => {
    const text = await page.locator(".page-meta span").first().textContent();
    return Number(text?.match(/\d+/)?.[0] || 0);
  };

  await expect.poll(readResultCount).toBeGreaterThan(0);
  const initialCount = await readResultCount();

  await page.getByRole("button", { name: "继续下拉，自动加载 5 条" }).click();
  await expect(page.locator(".timeline-item")).toHaveCount(10);

  await page.getByRole("link", { name: /ai 日报/i }).click();
  await expect(page).toHaveURL(/\/daily$/);
  await expect(page.getByRole("heading", { name: /AI\s*HOT\s*日报/i })).toBeVisible();
  await expect(page.getByText(/VOL\.\s*2026\.05\.08.*AI HOT DAILY/i)).toBeVisible();

  await page.getByRole("link", { name: /公众号爆文/i }).click();
  await expect(page).toHaveURL(/\/mp$/);
  await expect
    .poll(async () => page.locator(".mp-table tbody tr").count())
    .toBeGreaterThan(0);
  await expect(page.getByRole("columnheader", { name: "发文日期" })).toBeVisible();
  await page.getByRole("button", { name: "过去 24h" }).click();
  await expect(page).toHaveURL(/\/mp\?since=24h&page=1/);
  await page.getByRole("button", { name: "过去 30 天" }).click();
  await expect(page).toHaveURL(/\/mp\?since=30d&page=1/);
  await page.getByRole("button", { name: "下一页 ›" }).click();
  await expect(page).toHaveURL(/\/mp\?since=30d&page=2/);

  await page.getByRole("link", { name: /反馈/i }).click();
  await expect(page).toHaveURL(/\/feedback$/);
  await expect(page.getByRole("heading", { name: "反馈", level: 1 })).toBeVisible();

  await page.goto("/");
  const firstTitle = await page.locator(".story-title, .timeline-title").first().textContent();
  const query = (firstTitle || "").trim().slice(0, 4);
  await page.getByLabel("搜索标题或摘要").fill(query);
  const filteredCardCount = await page.locator(".timeline-item").count();
  const filteredCountText = await page.locator(".page-meta span").first().textContent();
  const filteredCount = Number(filteredCountText?.match(/\d+/)?.[0] || 0);
  expect(filteredCardCount).toBeGreaterThan(0);
  expect(filteredCount).toBeGreaterThan(0);
  expect(filteredCount).toBeLessThanOrEqual(initialCount);

  await page.getByLabel("浅色").click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
});
