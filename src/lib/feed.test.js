import test from "node:test";
import assert from "node:assert/strict";

import {
  filterItemsByQuery,
  getAvatarLabel,
  getAvatarThemeIndex,
  getMediaThemeIndex,
  getSearchText,
  getTimelineItemKey,
  groupItemsByDay,
  normalizeItems,
} from "./feed.js";

const sampleItems = [
  {
    day: "5月7日",
    time: "08:30",
    source: "Apple Machine Learning Research（RSS）",
    handle: "",
    title: "  SpecMD  ",
    body: "  MoE 推理  ",
    quoted: "  引文  ",
    reason: "  研究值得读  ",
    tags: ["推理", "论文/研究"],
    link: "https://example.com/specmd",
  },
  {
    day: "5月7日",
    time: "08:30",
    source: "Apple Machine Learning Research（RSS）",
    handle: "",
    title: "Normalizing Flows",
    body: "",
    quoted: "",
    reason: "另一个方向",
    tags: ["图像生成"],
    link: "https://example.com/flow",
  },
  {
    day: "5月8日",
    time: "09:00",
    source: "OpenAI：Newsroom",
    handle: "@openai",
    title: "OpenAI 更新",
    body: "发布说明",
    quoted: "",
    reason: "重点更新",
    tags: ["OpenAI"],
    link: "https://example.com/openai",
  },
];

test("normalizeItems trims string content while preserving order", () => {
  const normalized = normalizeItems(sampleItems);

  assert.equal(normalized[0].title, "SpecMD");
  assert.equal(normalized[0].body, "MoE 推理");
  assert.equal(normalized[0].quoted, "引文");
  assert.equal(normalized[0].reason, "研究值得读");
  assert.equal(normalized[2].title, "OpenAI 更新");
});

test("groupItemsByDay keeps insertion order and groups correctly", () => {
  const grouped = groupItemsByDay(sampleItems);

  assert.deepEqual(grouped.map(([day]) => day), ["5月7日", "5月8日"]);
  assert.equal(grouped[0][1].length, 2);
  assert.equal(grouped[1][1][0].source, "OpenAI：Newsroom");
});

test("filterItemsByQuery matches lower-cased content across fields", () => {
  const normalized = normalizeItems(sampleItems);

  assert.equal(filterItemsByQuery(normalized, "openai").length, 1);
  assert.equal(filterItemsByQuery(normalized, "论文/研究").length, 1);
  assert.equal(filterItemsByQuery(normalized, "不存在").length, 0);
});

test("getSearchText includes tags and text payload", () => {
  const searchText = getSearchText(sampleItems[0]);

  assert.match(searchText, /apple machine learning research/);
  assert.match(searchText, /论文\/研究/);
  assert.match(searchText, /moe 推理/);
});

test("avatar label strips Chinese source suffixes and punctuation", () => {
  assert.equal(getAvatarLabel("OpenAI：Newsroom（网页）"), "OP");
  assert.equal(getAvatarLabel("向阳乔木"), "向阳");
});

test("theme index helpers stay deterministic", () => {
  assert.equal(getAvatarThemeIndex("OpenAI", 4), getAvatarThemeIndex("OpenAI", 4));
  assert.equal(getMediaThemeIndex("OpenAI", "09:00", 3), getMediaThemeIndex("OpenAI", "09:00", 3));
});

test("timeline item keys include the link to avoid collisions", () => {
  assert.notEqual(getTimelineItemKey(sampleItems[0]), getTimelineItemKey(sampleItems[1]));
});
