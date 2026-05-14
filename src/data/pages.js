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
    subtitle: "这个 fork 保留了 AIHOT 的终端式信息设计和浏览节奏",
    metaSecondary: "React 结构化版本",
    sections: [
      {
        kicker: "Design",
        title: "保留原站的视觉节奏",
        copy:
          "左侧导航、深色卡片、时间轴和推荐理由区都尽量贴近原站；当前版本更重视可维护的前端结构，而不是 1:1 产品复刻。",
        tags: ["React", "Vite", "Timeline UI"],
      },
      {
        kicker: "Data",
        title: "当前仍是静态快照数据",
        copy:
          "首页和各个子页都从同一份静态 feed 快照派生，适合先验证信息架构、视觉和交互；后续可以无缝换成真实 API。",
        tags: ["JSON", "Mock Data", "Future API"],
      },
      {
        kicker: "Scope",
        title: "为继续工程化预留了空间",
        copy:
          "现在已经拆分出 components、hooks、data、lib，后续继续加 router loader、真实数据源、测试基建和样式模块会顺手很多。",
        tags: ["components", "hooks", "data", "lib"],
      },
    ],
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
