# AI Digest

基于 `Vite + React + Python FastAPI + SQLite` 的 AI Digest，当前后端已切换到 vendored `x_atuo` 宿主，并为后续 X / AI 自动化采集预留了完整扩展面。

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
- `/admin`: 管理后台（需登录）

## Admin Panel

管理后台用于管理采集源和导航链接。

### 配置

启动前需要设置管理员密码。两种方式任选其一：

```bash
export ADMIN_PASSWORD="your-secure-password"
```

或创建本地开发用的 `backend/.env`（可从 `backend/.env.example` 复制）：

```bash
cp backend/.env.example backend/.env
```

可选：设置 JWT 密钥（不设置时会根据 ADMIN_PASSWORD 自动生成）：

```bash
export JWT_SECRET="your-jwt-secret"
```

如果要启用后台图片上传，还需要配置 Cloudflare R2 和公开 CDN 域名：

```bash
export MEDIA_CDN_BASE_URL="https://static.cloudbase.eu.org"
export R2_ACCOUNT_ID="your-cloudflare-account-id"
export R2_BUCKET="your-r2-bucket"
export R2_ACCESS_KEY_ID="your-r2-access-key-id"
export R2_SECRET_ACCESS_KEY="your-r2-secret-access-key"
```

当前 Phase 1 的公开 URL 合同固定为：

- `https://static.cloudbase.eu.org/original/<asset-id>.<ext>`
- `https://static.cloudbase.eu.org/cover/<asset-id>.webp`
- `https://static.cloudbase.eu.org/thumb/<asset-id>.webp`

`https://static.cloudbase.eu.org` 是当前默认且推荐的 rollout host；运行时也可以通过 `MEDIA_CDN_BASE_URL` 覆盖到其他 CDN 域名，但推荐优先保持默认值，这样管理后台上传、公开 `/about` 页面和后续采集镜像链路都会落在同一套稳定 URL 约定下。

后台图片上传还要求运行环境提供 `ffmpeg` 和 `cwebp` 命令。这里没有新增 Python 运行时依赖，因为标准库本身无法安全地产生 WebP 缩略图，当前实现使用 `ffmpeg` 做解码/缩放，再用 `cwebp` 编码 `cover` / `thumb` 变体。

### 访问

1. 访问 `http://127.0.0.1:5173/admin`
2. 输入管理员密码登录
3. Token 有效期 24 小时

### 功能

- **采集源管理**：添加、编辑、删除、启用/禁用 RSS 采集源
- **导航管理**：添加、编辑、删除、排序导航链接
- **图片资产上传**：上传后台图片并返回 `static.cloudbase.eu.org` 下的稳定 CDN URL（`original` / `cover` / `thumb`）

### 关于页二维码上传流程

1. 登录 `http://127.0.0.1:5173/admin`
2. 进入“关于页面”管理页
3. 在“上传二维码图片”中选择图片文件
4. 上传成功后，表单里的 `qr_code_url` 会自动写入返回的 `original_url`
5. 管理页会立即用这条同样的 `original_url` 做当前二维码预览
6. 点击保存后，这个 `qr_code_url` 才会持久化到 `about_config.qr_code_url`，公开 `/about` 页面随后继续消费同一条 URL 渲染二维码图片

当前推荐的 URL 用法如下：

- `original_url`：用于 `/admin/about` 的 `qr_code_url` 流程；管理页上传成功后会先把它填进表单并预览，同一条 URL 在保存后会由公开 `/about` 页面消费，保留原始清晰度以避免扫码质量下降
- `cover_url`：为后续列表卡片或较大封面位预留
- `thumb_url`：为后续小缩略图列表位预留

本阶段只打通后台上传和统一资产 URL 合同；collector 侧的远程图片镜像仍刻意留到下一阶段实现，避免当前 Phase 1 把上传资产与采集镜像逻辑耦合在一起。

### Admin APIs

认证相关：

- `POST /api/admin/auth/login` - 登录获取 JWT token
- `GET /api/admin/auth/verify` - 验证 token 有效性

采集源管理：

- `GET /api/admin/sources` - 列表
- `POST /api/admin/sources` - 新增
- `GET /api/admin/sources/:id` - 详情
- `PUT /api/admin/sources/:id` - 更新
- `DELETE /api/admin/sources/:id` - 删除
- `PATCH /api/admin/sources/:id/toggle` - 启用/禁用

导航管理：

- `GET /api/admin/navigation` - 列表
- `POST /api/admin/navigation` - 新增
- `PUT /api/admin/navigation/:id` - 更新
- `DELETE /api/admin/navigation/:id` - 删除
- `PATCH /api/admin/navigation/:id/toggle` - 启用/禁用
- `PUT /api/admin/navigation/reorder` - 重排序

媒体资产：

- `POST /api/admin/media-assets/upload` - 上传后台图片，返回 `asset_id`、`original_url`、`cover_url`、`thumb_url`
  - 无法解码或无法生成变体的坏图会返回 `400`
  - R2/网络暂时不可用时会返回 `503`

公开 API：

- `GET /api/navigation` - 获取导航配置（前端渲染用）

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
