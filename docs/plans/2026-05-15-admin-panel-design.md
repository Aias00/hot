# 管理后台设计文档

## 概述

为 AIHOT 项目添加管理后台，用于管理采集源配置和导航链接。采用配置维护型设计，简单密码保护认证。

## 需求总结

- **用途**: 配置维护型 - 偶尔调整采集源、导航链接
- **认证**: 简单密码保护，密码通过环境变量 `ADMIN_PASSWORD` 配置
- **实现**: 独立管理页面，在现有前端项目中新增 `/admin` 路由

## 页面结构

```
/admin                    → 管理首页（概览仪表板）
/admin/sources            → 采集源管理（列表 + 增删改查）
/admin/navigation         → 导航链接管理（列表 + 增删改查 + 拖拽排序）
/admin/login              → 登录页面
```

## 认证设计

### 流程

```
用户访问 /admin/*
  → 检查 localStorage 中的 token
  → 无 token 或无效 → 重定向到 /admin/login
  → 有效 → 显示管理页面

登录流程：
  → 用户输入密码
  → POST /api/admin/auth { password }
  → 后端验证 ADMIN_PASSWORD 环境变量
  → 成功返回 JWT token（有效期 24h）
  → 前端存储 token 到 localStorage
```

### 环境变量

```bash
ADMIN_PASSWORD=your_secure_password_here
JWT_SECRET=随机生成的密钥（启动时自动生成或手动配置）
```

### API

```
POST /api/admin/auth/login    # { password } → { token, expires_at }
POST /api/admin/auth/logout   # 使 token 失效（可选）
GET  /api/admin/auth/verify   # 验证 token 有效性
```

### 安全措施

| 措施 | 说明 |
|------|------|
| JWT 有效期 | 24 小时，过期需重新登录 |
| HTTPS | 生产环境强制 HTTPS |
| 密码强度 | 部署文档提示设置强密码 |
| 速率限制 | 登录接口限流（可选，后续可加） |

## 采集源管理

### 数据模型（已有）

`collector_sources` 表：

| 字段 | 类型 | 用途 |
|------|------|------|
| `source_id` | TEXT PK | 唯一标识 |
| `adapter_kind` | TEXT | 适配器类型（如 `rss-generic`） |
| `title` | TEXT | 显示名称 |
| `description` | TEXT | 描述 |
| `enabled` | INTEGER | 启用状态 |
| `base_url` | TEXT | 基础 URL |
| `seed_urls_json` | TEXT | 种子 URL 列表 |
| `config_json` | TEXT | 扩展配置 |

### 管理界面

**列表页 `/admin/sources`**
- 表格展示：名称、适配器类型、状态、操作按钮
- 启用/禁用开关（一键切换）
- 编辑、删除按钮
- 顶部新增按钮

**编辑表单**
- 基础字段：source_id、title、description、enabled
- 适配器选择：下拉菜单（`rss-generic`，后续可扩展）
- 种子 URL：多行文本框，每行一个 URL
- 扩展配置：JSON 编辑器（可选，高级功能）

### API

```
GET    /api/admin/sources          # 列表
POST   /api/admin/sources          # 新增
GET    /api/admin/sources/:id      # 详情
PUT    /api/admin/sources/:id      # 更新
DELETE /api/admin/sources/:id      # 删除
PATCH  /api/admin/sources/:id/toggle  # 启用/禁用切换
```

## 导航链接管理

### 数据模型（新增）

新增 `navigation_items` 表：

| 字段 | 类型 | 用途 |
|------|------|------|
| `id` | INTEGER PK | 主键 |
| `icon` | TEXT | 图标字符 |
| `label` | TEXT | 显示文本 |
| `to` | TEXT | 路由路径 |
| `sort_order` | INTEGER | 排序权重 |
| `enabled` | INTEGER | 启用状态 |
| `created_at` | TEXT | 创建时间 |
| `updated_at` | TEXT | 更新时间 |

### 迁移

从 `src/data/navigation.js` 迁移数据到数据库。

### 管理界面

**列表页 `/admin/navigation`**
- 卡片列表：图标 + 标签 + 路径
- 拖拽排序（HTML5 原生拖拽）
- 启用/禁用开关
- 编辑、删除按钮

**编辑表单**
- 图标选择：文本输入
- 标签：文本输入
- 路径：文本输入

### API

```
GET    /api/admin/navigation           # 列表（已排序）
POST   /api/admin/navigation           # 新增
PUT    /api/admin/navigation/:id       # 更新
DELETE /api/admin/navigation/:id       # 删除
PATCH  /api/admin/navigation/:id/toggle # 启用/禁用
PUT    /api/admin/navigation/reorder   # 批量重排序
GET    /api/navigation                 # 前端获取导航配置
```

## 文件结构

### 后端新增

```
backend/src/hot_backend/
├── admin_routes.py       # 管理后台 API 路由
├── auth.py               # JWT 认证逻辑
└── sqlite_store.py       # 新增导航表相关方法（修改现有文件）
```

### 前端新增

```
src/
├── pages/admin/
│   ├── AdminLayout.jsx   # 管理后台布局（侧边栏 + 认证守卫）
│   ├── AdminLogin.jsx    # 登录页
│   ├── SourcesPage.jsx   # 采集源管理
│   └── NavigationPage.jsx # 导航链接管理
├── hooks/
│   └── useAuth.js        # 认证状态管理
└── styles/
    └── admin.css         # 管理后台样式
```

## 实现步骤

| 步骤 | 内容 | 依赖 |
|------|------|------|
| 1 | 后端：JWT 认证模块 + 登录 API | - |
| 2 | 后端：管理 API 中间件保护 | 步骤 1 |
| 3 | 后端：采集源 CRUD API | 步骤 2 |
| 4 | 后端：导航表 + CRUD API + 迁移脚本 | 步骤 2 |
| 5 | 前端：认证流程 + 登录页 | 步骤 1 |
| 6 | 前端：管理布局 + 路由守卫 | 步骤 5 |
| 7 | 前端：采集源管理页面 | 步骤 3, 6 |
| 8 | 前端：导航管理页面 | 步骤 4, 6 |
| 9 | 前端：导航数据动态加载 | 步骤 4 |
| 10 | 测试与文档 | 全部 |

## 预估工作量

- 后端：约 400-500 行新增代码
- 前端：约 600-800 行新增代码
- 总计：约 2-3 天开发时间
