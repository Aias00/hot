# AIHOT Fork

基于 `Vite + React + Python FastAPI + SQLite` 的 AIHOT fork，当前后端已切换到 vendored `x_atuo` 宿主，并为后续 X / AI 自动化采集预留了完整扩展面。

- 左侧固定导航与主题切换
- 深色卡片时间轴和推荐理由区
- 搜索筛选交互
- 移动端顶部压缩导航

## Stack

- Vite
- React
- Python FastAPI
- SQLite
- vendored `x_atuo`
- 原生 CSS

## Run

```bash
npm install
uv sync --project backend --extra dev
npm run dev
```

默认会同时启动：
- 前端：`http://127.0.0.1:5173/`
- 后端：`http://127.0.0.1:18000/`

也可以单独启动：

```bash
npm run dev:frontend
npm run dev:backend
```

## Build

```bash
npm run build
```

## Test

```bash
npm test
npm run test:e2e
```

## Structure

- `index.html`: Vite 入口 HTML
- `backend/`: Python FastAPI backend, vendored `x_atuo`, SQLite seed and runtime data
- `src/main.jsx`: React 挂载入口
- `src/App.jsx`: 顶层编排层
- `src/components/`: 视图组件
- `src/hooks/`: 数据加载和主题状态
- `src/data/`: 导航、页面定义、视觉常量和数据入口
- `src/lib/`: 纯函数和内置回归测试
- `src/pages/`: 路由页组件
- `src/router/`: 路由编排
- `src/styles/`: 分片样式入口与模块化 CSS
- `public/feed-snapshot.json`: 从目标站提取的静态条目快照
- `public/favicon.svg`: 图标
- `e2e/`: Playwright 端到端测试

当前组件拆分大致如下：

```text
src/
  components/
    states/
  data/
  hooks/
  lib/
  pages/
  router/
  styles/
  App.jsx
  main.jsx

backend/
  data/
    seed/
  src/
    hot_backend/
    x_atuo/
```

## Routes

- `/`: 精选
- `/all`: 全部 AI 动态
- `/daily`: AI 日报
- `/mp`: 公众号爆文
- `/about`: 关于
- `/feedback`: 反馈

## Backend APIs

- `GET /api/feed`
- `GET /api/daily?view=issue&date=YYYY-MM-DD`
- `GET /api/daily?view=archive`
- `GET /api/mp?q=&since=&page=`

同时保留 `x_atuo` 原生能力入口，例如：

- `GET /healthz`
- `GET /analytics/account`
- `GET /notifications`
- `GET /twitter/search`

## Collector Framework

新增了一个 Python 侧的热点采集 graph 框架骨架：

- `GET /api/collect/sources`
- `POST /api/collect/execute`
- `GET /api/collect/runs/{run_id}`

当前默认带一个 `mock-hot-source` 适配器，用来验证多来源采集框架和 LangGraph 运行链路。

同时提供一个可执行的 `rss-generic-sample`：

```bash
curl -s -X POST http://127.0.0.1:18000/api/collect/execute \
  -H 'content-type: application/json' \
  -d '{"source_id":"rss-generic-sample","dry_run":true,"limit":2}' | jq
```

也可以创建你自己的可配置 RSS source：

```bash
curl -s -X POST http://127.0.0.1:18000/api/collect/sources \
  -H 'content-type: application/json' \
  -d '{
    "source_id": "my-rss-source",
    "adapter_kind": "rss-generic",
    "title": "My RSS Source",
    "description": "Configurable RSS source",
    "enabled": true,
    "seed_urls": ["file:///ABS/PATH/TO/feed.xml"],
    "config_json": {}
  }' | jq

curl -s -X POST http://127.0.0.1:18000/api/collect/execute \
  -H 'content-type: application/json' \
  -d '{"source_id":"my-rss-source","dry_run":true,"limit":10}' | jq
```

`rss-generic` 当前支持的 URL scheme：
- `file://`
- `http://`
- `https://`

默认已接入的真实线上 RSS source：
- `openai-news-rss`
- `github-blog-rss`
- `huggingface-blog-rss`

Source 管理接口：

- `GET /api/collect/adapter-kinds`
- `GET /api/collect/sources`
- `GET /api/collect/sources/{source_id}`
- `POST /api/collect/sources`
- `PUT /api/collect/sources/{source_id}`
- `DELETE /api/collect/sources/{source_id}`

批量采集默认 RSS 并回流到首页 feed：

```bash
npm run collect:rss
```

采集成功后，设置 `dry_run=false` 的结果会写入 `hot_items`，并回流到 `/api/feed`：

```bash
curl -s -X POST http://127.0.0.1:18000/api/collect/execute \
  -H 'content-type: application/json' \
  -d '{"source_id":"rss-generic-sample","dry_run":false,"limit":1}' | jq

curl -s http://127.0.0.1:18000/api/feed | jq '.items[0]'
```
