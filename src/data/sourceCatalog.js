const SOURCE_GROUPS = [
  {
    key: "models-research",
    label: "模型与研究",
    description: "更偏模型发布、研究进展和前沿能力演化的官方来源。",
    sourceIds: [
      "openai-news-rss",
      "google-deepmind-news-rss",
      "google-blog-ai-rss",
      "google-blog-deepmind-rss",
    ],
  },
  {
    key: "developer-platforms",
    label: "开发者平台",
    description: "更偏 Agent、SDK、工作流和开发者工具链的官方来源。",
    sourceIds: [
      "github-blog-rss",
      "huggingface-blog-rss",
      "google-developers-blog-rss",
      "google-developers-tech-blog-rss",
      "microsoft-foundry-blog-rss",
      "microsoft-semantic-kernel-blog-rss",
      "langgraph-blog-rss",
      "ollama-blog-rss",
      "kaggle-blog-rss",
    ],
  },
  {
    key: "infra-cloud",
    label: "云与推理基础设施",
    description: "更偏推理性能、模型部署、云平台与运行时能力。",
    sourceIds: [
      "aws-machine-learning-blog-rss",
      "vercel-news-rss",
      "together-ai-blog-rss",
      "sambanova-blog-rss",
    ],
  },
  {
    key: "creative-products",
    label: "创意与生成工具",
    description: "更偏图像、视频和创意生成产品更新。",
    sourceIds: [
      "midjourney-updates-rss",
      "replicate-blog-rss",
    ],
  },
];

const SOURCE_ID_TO_GROUP = new Map(
  SOURCE_GROUPS.flatMap((group) =>
    group.sourceIds.map((sourceId) => [sourceId, group]),
  ),
);

export function getSourceGroupMeta(source) {
  const sourceId = typeof source === "string" ? source : source?.source_id;
  return (
    SOURCE_ID_TO_GROUP.get(sourceId) || {
      key: "custom-rss",
      label: "自定义 RSS",
      description: "未纳入默认分层的外部或临时来源。",
    }
  );
}

export function groupSourcesForDisplay(sources) {
  const grouped = new Map();

  for (const source of sources) {
    const meta = getSourceGroupMeta(source);
    if (!grouped.has(meta.key)) {
      grouped.set(meta.key, { ...meta, items: [] });
    }
    grouped.get(meta.key).items.push(source);
  }

  const ordered = [];
  for (const meta of SOURCE_GROUPS) {
    const group = grouped.get(meta.key);
    if (group) {
      ordered.push({
        ...group,
        items: group.items.slice().sort((left, right) => left.title.localeCompare(right.title)),
      });
    }
  }

  const fallback = grouped.get("custom-rss");
  if (fallback) {
    ordered.push({
      ...fallback,
      items: fallback.items.slice().sort((left, right) => left.title.localeCompare(right.title)),
    });
  }

  return ordered;
}

export function listSourceGroups() {
  return SOURCE_GROUPS.map((group) => ({
    key: group.key,
    label: group.label,
    description: group.description,
  }));
}
