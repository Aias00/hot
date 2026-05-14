function parseHtmlDocument(html) {
  return new DOMParser().parseFromString(html, "text/html");
}

function parsePageFromHref(href) {
  if (!href) {
    return 1;
  }

  const url = new URL(href, "https://aihot.virxact.com");
  return Number(url.searchParams.get("page") || "1");
}

function getText(node, selector) {
  return node.querySelector(selector)?.textContent?.trim() || "";
}

function getReasonText(item) {
  const container = item.querySelector(".timeline-reason");

  if (!container) {
    return "";
  }

  return container.textContent.replace(/^推荐理由：/, "").trim();
}

function parseDailySidebar(document) {
  const latest = document.querySelector(".daily-side-latest");
  const months = [...document.querySelectorAll(".daily-side-month")].map((month) => ({
    month: getText(month, ".daily-side-month-name"),
    count: getText(month, ".daily-side-month-count"),
    issues: [...month.querySelectorAll(".daily-side-day")].map((issue) => ({
      day: getText(issue, ".daily-side-day-num"),
      title: getText(issue, ".daily-side-day-headline"),
      href: issue.getAttribute("href") || "",
      active: issue.classList.contains("is-active"),
    })),
  }));

  return {
    latest: latest
      ? {
          href: latest.getAttribute("href") || "/daily",
          label: getText(latest, ".daily-side-latest-label"),
          date: getText(latest, ".daily-side-latest-date"),
        }
      : null,
    archiveHref: document.querySelector(".daily-side-archive")?.getAttribute("href") || "/daily/archive",
    months,
  };
}

export function parseFeedHtml(html) {
  const document = parseHtmlDocument(html);
  const days = [...document.querySelectorAll(".timeline-day")];

  return days.flatMap((day) => {
    const dayLabel = getText(day, ".timeline-date");

    return [...day.querySelectorAll(".timeline-item")].map((item) => ({
      day: dayLabel,
      time: getText(item, ".timeline-time"),
      source: getText(item, ".timeline-source"),
      handle: getText(item, ".timeline-handle"),
      badge: getText(item, ".timeline-selected-badge"),
      score: getText(item, ".timeline-score"),
      title: getText(item, ".timeline-title"),
      body: getText(item, ".timeline-summary") || getText(item, ".story-body"),
      quoted: getText(item, ".uc-quoted"),
      reason: getReasonText(item),
      tags: [...item.querySelectorAll(".timeline-tags .tag")].map((tag) =>
        tag.textContent?.trim(),
      ).filter(Boolean),
      hasMedia: Boolean(
        item.querySelector(
          ".timeline-media, .timeline-link-preview, .timeline-media-card, img, video, iframe",
        ),
      ),
      link:
        item.querySelector(".timeline-title")?.getAttribute("href") ||
        item.querySelector("a[href]")?.getAttribute("href") ||
        "",
    }));
  });
}

export function parseDailyIssueHtml(html) {
  const document = parseHtmlDocument(html);
  const sidebar = parseDailySidebar(document);
  const masthead = document.querySelector(".daily-masthead");
  const sections = [...document.querySelectorAll(".daily-section")].map((section) => ({
    number: getText(section, ".daily-section-no"),
    title: getText(section, ".daily-section-title"),
    english: getText(section, ".daily-section-subtitle"),
    count: getText(section, ".daily-section-count strong"),
    stories: [...section.querySelectorAll(".daily-article")].map((story) => ({
      title: getText(story, ".daily-article-title"),
      href: story.querySelector(".daily-article-title a")?.getAttribute("href") || "",
      sourceRole: getText(story, ".daily-article-source .role-tag"),
      source: [...story.querySelectorAll(".daily-article-source span")]
        .map((node) => node.textContent?.trim())
        .filter(Boolean)
        .join(" ")
        .replace(getText(story, ".daily-article-source .role-tag"), "")
        .trim(),
      summary: getText(story, ".daily-article-summary"),
    })),
  }));

  return {
    mode: "issue",
    sidebar,
    masthead: {
      eyebrow: masthead
        ? [...masthead.querySelectorAll(".daily-masthead-eyebrow span:not(.sep)")]
            .map((node) => node.textContent?.trim())
            .filter(Boolean)
            .join(" · ")
        : "",
      title: getText(masthead || document, ".daily-masthead-title"),
      date: getText(masthead || document, ".daily-masthead-date"),
      tagline: getText(masthead || document, ".daily-masthead-tagline"),
    },
    sections,
  };
}

export function parseDailyArchiveHtml(html) {
  const document = parseHtmlDocument(html);
  const sidebar = parseDailySidebar(document);

  return {
    mode: "archive",
    sidebar,
    archive: {
      title: getText(document, ".daily-index-title"),
      subtitle: getText(document, ".daily-index-subtitle"),
      entries: [...document.querySelectorAll(".daily-index-row")].map((entry) => ({
        href: entry.getAttribute("href") || "",
        date: getText(entry, ".daily-index-date"),
        headline: getText(entry, ".daily-index-headline"),
        events: getText(entry, ".daily-index-events"),
      })),
    },
  };
}

export function parseMpHtml(html) {
  const document = parseHtmlDocument(html);
  const form = document.querySelector('form.filter-form[action="/mp"]');
  const pagination = document.querySelector(".feed-pagination");
  const rows = [...document.querySelectorAll(".mp-table tbody tr")].map((row) => {
    const cells = row.querySelectorAll("td");
    const titleLink = row.querySelector(".mp-title-link");
    const accountLink = row.querySelector(".mp-account-cell");

    return {
      date: cells[0]?.textContent?.trim() || "",
      title: titleLink?.textContent?.trim() || "",
      href: titleLink?.getAttribute("href") || "",
      account: accountLink?.textContent?.replace(/\s+/g, " ").trim() || "",
      accountHref: accountLink?.getAttribute("href") || "",
      badge: row.querySelector(".mp-badge")?.textContent?.trim() || "",
      reads: cells[2]?.textContent?.trim() || "",
      likes: cells[3]?.textContent?.trim() || "",
      shares: cells[4]?.textContent?.trim() || "",
      outlier: cells[5]?.textContent?.trim() || "",
    };
  });

  return {
    title: getText(document, ".page-title") || "公众号爆文",
    subtitle: getText(document, ".page-subtitle"),
    pagerLabel: document.querySelector(".page-meta span")?.textContent?.trim() || "",
    pageMeta: [...document.querySelectorAll(".page-meta span")]
      .map((node) => node.textContent?.trim())
      .filter(Boolean),
    filters: {
      query: form?.querySelector('input[name="q"]')?.getAttribute("value") || "",
      since: form?.querySelector('select[name="since"] option[selected]')?.getAttribute("value") || "30d",
      options: form
        ? [...form.querySelectorAll('select[name="since"] option')].map((option) => ({
            label: option.textContent?.trim() || "",
            value: option.getAttribute("value") || "",
          }))
        : [],
    },
    pagination: pagination
      ? {
          currentPage: Number(
            pagination.querySelector(".feed-pagination-num.is-current")?.textContent?.trim() || "1",
          ),
          pages: [...pagination.querySelectorAll(".feed-pagination-pages .feed-pagination-num")]
            .map((node) => ({
              label: node.textContent?.trim() || "",
              page: node.matches("a")
                ? parsePageFromHref(node.getAttribute("href"))
                : Number(node.textContent?.trim() || "1"),
              current: node.classList.contains("is-current"),
            }))
            .filter((entry) => entry.label),
          prevPage: parsePageFromHref(
            pagination.querySelector('.feed-pagination-btn[href*="page"], .feed-pagination-btn[href="/mp"], .feed-pagination-btn[href*="?since="]')?.getAttribute("href"),
          ),
          nextPage: parsePageFromHref(
            [...pagination.querySelectorAll(".feed-pagination-btn")]
              .find((node) => node.textContent?.includes("下一页"))
              ?.getAttribute("href"),
          ),
          hasPrev: Boolean(
            [...pagination.querySelectorAll(".feed-pagination-btn")]
              .find((node) => node.textContent?.includes("上一页") && node.matches("a")),
          ),
          hasNext: Boolean(
            [...pagination.querySelectorAll(".feed-pagination-btn")]
              .find((node) => node.textContent?.includes("下一页") && node.matches("a")),
          ),
        }
      : null,
    rows,
  };
}
