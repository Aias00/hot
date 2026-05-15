export const feedPageDefinitions = [
  {
    path: "/",
    upstreamPath: "/",
    title: "精选",
    subtitle: "AI 自动挑选的高价值内容",
    metaSecondary: "静态设计 fork",
    filter: () => true,
    progressiveReveal: true,
  },
  {
    path: "/all",
    upstreamPath: "/all",
    title: "全部 AI 动态",
    subtitle: "统一浏览采集结果与静态快照的完整时间线",
    metaSecondary: "合并视图 · 默认全部展开",
    filter: () => true,
    progressiveReveal: false,
  },
];

export const infoPageDefinitions = [
  {
    path: "/about",
    title: "关于",
    subtitle: "AI 热点聚合平台",
    metaSecondary: "React 结构化版本",
    sections: [
      {
        kicker: "About",
        title: "AIHOT",
        copy:
          "聚合 AI 动态、导航入口与采集归档的本地优先信息站点。左侧导航、深色卡片、时间轴和推荐理由区，帮助你快速了解 AI 领域最新动态。",
        tags: ["React", "Vite", "Python", "FastAPI"],
      },
      {
        kicker: "Feature",
        title: "核心功能",
        copy:
          "精选 AI 高价值内容、每日 AI 日报、公众号爆文聚合、RSS 自动采集、导航中心。支持深色主题、响应式布局。",
        tags: ["Timeline UI", "Dark Theme", "RSS"],
      },
    ],
    wechatQR: true,
  },
  {
    path: "/feedback",
    title: "反馈",
    subtitle: "当前是静态 fork，所以反馈入口先以说明和外链为主",
    metaSecondary: "欢迎继续扩展",
    sections: [
      {
        kicker: "Next Step",
        title: "如果要继续做成真正应用",
        copy:
          "最自然的下一步是接真实数据源、用路由级 loader 管数据、再补上组件和端到端测试，让导航、筛选和多页内容都具备产品级行为。",
        tags: ["router", "loader", "tests"],
      },
      {
        kicker: "Reference",
        title: "原站反馈页",
        copy:
          "如果你只是想参考原站的反馈入口和内容组织，可以直接打开原站反馈页对照；当前页面主要承担导航不再是 stub 的职责。",
        actions: [
          {
            label: "打开原站反馈页",
            href: "https://aihot.virxact.com/feedback",
            external: true,
          },
          {
            label: "返回首页",
            to: "/",
            external: false,
          },
        ],
      },
    ],
  },
];
