# RSSRob

**一个轻量、可配置的工具，可为任意网站生成 RSS 订阅源 —— 即使该网站本身并不提供 RSS。**

对于没有订阅源的网站，你只需把 RSSRob 指向某个页面，并（用 CSS 选择器或 XPath）告诉它条目及其字段所在的位置；对于已经发布 RSS/Atom 的网站，直接给出订阅源 URL 即可。无论哪种方式，RSSRob 都会按计划定时运行、构建符合规范的 RSS 订阅源，并通过 HTTP 提供访问。它会记住所有见过的条目，因此你的订阅源会不断累积历史记录，且永远不会重复展示同一条目。

---

## 功能特性

- **四种数据源类型** —— `html` 用 **CSS 选择器或 XPath** 抓取；`rss` 直接解析并重新提供已发布的订阅源（无需选择器）；`wechat` 通过你自己的后台跟踪公众号；`twitter` 通过你自己已登录的会话跟踪 X 账号。
- **内置调度器** —— 单进程即可按各自的间隔抓取每个站点，无需外部 cron。
- **内置 Web 管理界面** —— 浏览器中预览订阅源、调试选择器/过滤器、管理通知目标、备份恢复。
- **多渠道通知** —— 通过 [Apprise](https://github.com/caronc/apprise) 支持 Telegram、Discord、Slack、邮件等 100+ 通知服务。
- **去重 + 历史** —— 用 SQLite 记录所有出现过的条目。条目只入库一次（按 id 去重），订阅源保留最近 N 条的滚动窗口 —— 因此即使条目已从源页面滚走，历史依然保留。
- **符合规范的 RSS** —— 订阅源由 [`feedgen`](https://github.com/lkiesow/python-feedgen) 生成，而非手写 XML。
- **便于调试** —— `run-once` 抓取单个站点并打印提取结果，便于在正式提交前调好选择器。
- **轻量** —— 依赖少，使用标准库的 HTTP 服务器与调度器，单进程运行。

---

## 工作原理

```
                         ┌──────────────────────────────────────┐
                         │             rssrob serve              │
                         │                                       │
   config.yaml ───────▶  │  ┌─────────────┐     ┌─────────────┐  │
                         │  │  scheduler  │     │ http.server │  │
                         │  │  (thread)   │     │ (main)      │  │
                         │  └──────┬──────┘     └──────┬──────┘  │
                         │         │ per-site          │ serves  │
                         │         ▼ interval          ▼         │
   site ────HTTP──▶ requests ─▶ extract (html, lxml) ─┐
                         │      parse   (rss,  feedparser) ─┴▶ store(SQLite) ─▶ feed.xml
                         │                                       (dedup)       (feedgen)
                         └──────────────────────────────────────┘
```

---

## 环境要求

- Python 3.11+
- 依赖：`requests`、`lxml`、`feedgen`、`pyyaml`、`feedparser`、`apprise`、`qrcode`

---

## 安装

```bash
git clone <your-repo-url> RSSRob
cd RSSRob
pip install -r requirements.txt
```

---

## Docker

### 构建镜像

```bash
docker build -t rssrob .
```

### 运行

```bash
docker run -d \
  --name rssrob \
  -p 5000:5000 \
  -v $(pwd)/configs:/app/configs \
  -v $(pwd)/var:/app/var \
  rssrob
```

### Docker Compose

```bash
docker compose up -d
docker compose logs -f    # 查看启动日志
```

访问 `http://localhost:5000` 打开 Web 管理界面。

---

## 快速开始

1. 创建 `configs/sites.yaml`：

```yaml
- name: example-blog
  type: html
  description: "示例博客"
  url: https://example.com/blog
  item: "css:div.post"
  fields:
    title: "css:h2 a"
    link: "css:h2 a@href"
    date: "css:time@datetime"
```

2. 测试选择器：

```bash
rssrob run-once example-blog
```

3. 启动服务：

```bash
rssrob serve
```

4. 在 RSS 阅读器中订阅：`http://127.0.0.1:8080/feeds/example-blog.xml`

---

## 配置

RSSRob 默认从 `configs/` 文件夹加载配置。推荐结构：

```
configs/
├── config.yaml          # 全局设置（output_dir, state_db, http, defaults）
├── sites.yaml           # 所有订阅源（列表格式）
├── ipp-notices.yaml     # 或每个订阅源一个文件
└── ...
```

### 全局选项

| 键 | 默认值 | 说明 |
|-----|---------|------|
| `output_dir` | `./var/feeds` | 生成的 XML 文件目录 |
| `state_db` | `./var/rssrob.db` | SQLite 数据库路径 |
| `http.host` | `127.0.0.1` | 服务器绑定地址 |
| `http.port` | `8080` | 服务器端口 |
| `defaults.interval` | `3600` | 抓取间隔（秒） |
| `defaults.max_items` | `50` | 每个订阅源保留的最大条目数 |

### 单站点选项

| 键 | 必填 | 说明 |
|-----|------|------|
| `name` | 是 | 唯一标识，用作文件名和 CLI 参数 |
| `url` | 是 | 页面 URL（html）或订阅源 URL（rss） |
| `type` | 否 | `html`（默认）、`rss`、`wechat`、`twitter` |
| `description` | 否 | 显示名称，用于 RSS 标题和 UI 展示 |
| `item` | html 必填 | 条目选择器 |
| `fields` | html 必填 | 字段 → 选择器映射 |
| `interval` | 否 | 覆盖默认抓取间隔 |
| `proxy` | 否 | 每订阅源代理 |
| `filter` | 否 | 关键词/正则包含–排除过滤 |

### 选择器语法

```
[css:|xpath:] <selector> [@attribute]
```

| 选择器 | 含义 |
|--------|------|
| `css:h2 a` | `<h2>` 内 `<a>` 的文本 |
| `css:h2 a@href` | 该链接的 `href` 属性 |
| `xpath:.//h2/a` | 第一个匹配链接的文本 |

---

## 通知（Apprise）

RSSRob 使用 [Apprise](https://github.com/caronc/apprise) 发送通知，支持 100+ 服务。
完整通知 URL 列表见 [Apprise Supported Services](https://github.com/caronc/apprise/wiki/Notify-Goodies)。

### 常用通知地址示例

| 服务 | URL 格式 | 示例 |
|------|---------|------|
| Telegram | `tgram://bot_token/chat_id` | `tgram://123456:ABC-DEF/123456789` |
| Discord | `discord://webhook_id/token` | `discord://123456/ABCdefGHI...` |
| Slack | `slack://token/a/b/c` | `slack://T00000000/B00000000/XXXXXXXX...` |
| 邮件 (SMTP) | `mailto://user:pass@smtp_host` | `mailto://you@gmail.com:app_pass@smtp.gmail.com` |
| ntfy | `ntfys://host/topic` | `ntfys://ntfy.yufei.im/RSS` |
| Gotify | `gotify://host/token` | `gotify://gotify.example.com/AaBbCcDd` |
| Pushover | `pover://user_key/token` | `pover://uQiRzcho4Renci6rM2.../AbbCDeFgHiJkLmNoPqRsT` |
| Bark (iOS) | `bark://host/key` | `bark://day.app/xxxx/yyyy` |
| 钉钉 | `dingtalk://token` | `dingtalk://abc123...` |
| 企业微信 | `wecom://token` | `wecom://xxxx...` |
| Chanify | `chanify://token` | `chanify://xxxx...` |
| Feishu | `feishu://token` | `feishu://xxxx...` |

### 配置方式

1. **Web 管理界面**：访问 `/notifications/targets`（地址簿）保存常用通知地址，然后在各订阅源的预览页选择订阅
2. **Web 管理界面**：访问 `/notifications` 管理所有通知目标
3. **命令行**：

```bash
# 预览所有目标的摘要
python -m rssrob.digest --all-subscribers --dry-run

# 发送单个订阅源的摘要
python -m rssrob.digest --site <name>

# 发送给指定目标
python -m rssrob.digest --site <name> --to tgram://bot_token/chat_id
```

---

## 微信公众号

通过你自己注册的公众号后台（mp.weixin.qq.com）获取文章，RSSRob 只读不发。

### 登录

1. 打开 mp.weixin.qq.com 登录你的公众号
2. 复制地址栏中的 token 和浏览器的 Cookie
3. 在 Web 界面 `/wechat/login` 粘贴，或命令行：

```bash
rssrob wechat-login --token 123456789 --cookie "<cookie>"
```

### 添加订阅源

在 Web 界面搜索公众号名称并保存，或命令行：

```bash
rssrob wechat-search "某某公众号" --save my-oa
```

> 建议 `interval` ≥ 7200 秒，避免被限流。

---

## Twitter / X

通过你自己已登录的 X 会话读取，无需付费 API。

### 登录

1. 登录 x.com，复制 Cookie 请求头
2. 在 Web 界面 `/twitter/login` 粘贴，或命令行：

```bash
rssrob twitter-login --cookie "<cookie>"
```

### 添加订阅源

```bash
rssrob twitter-add elonmusk --save elon
```

---

## 命令行

```bash
rssrob serve [--config config.yaml]           # 启动调度器 + 服务器
rssrob run-once <site-name>                   # 单次抓取测试
python -m rssrob.digest --all-subscribers     # 发送通知摘要
python -m rssrob.digest --site <name>         # 发送单个订阅源摘要
python -m rssrob.digest --dry-run             # 预览不发送
```

---

## 项目结构

```
RSSRob/
├── README.md
├── requirements.txt
├── requirements-web.txt
├── config.example.yaml
├── docker-compose.yml
├── Dockerfile
├── configs/                  # 配置文件夹
│   ├── config.yaml           # 全局设置
│   └── sites.yaml            # 订阅源列表
├── rssrob/                   # 核心包
│   ├── cli.py                # 命令行入口
│   ├── config.py             # 配置加载
│   ├── extract.py            # HTML 选择器提取
│   ├── rss.py                # RSS/Atom 解析
│   ├── store.py              # SQLite 存储
│   ├── feed.py               # RSS XML 生成
│   ├── notify.py             # Apprise 通知发送
│   ├── subscribers.py        # 通知目标管理
│   ├── notification_targets.py # 通知地址簿
│   ├── scheduler.py          # 后台调度器
│   └── server.py             # HTTP 服务器
├── web/                      # Web 管理界面
│   ├── webapp.py
│   └── templates/
├── tests/
└── var/                      # 运行时状态（gitignored）
    ├── feeds/                # 生成的 XML
    ├── rssrob.db             # SQLite 数据库
    ├── subscribers.json      # 通知目标
    └── ...
```

---

## 开发

```bash
pip install -r requirements.txt -r requirements-web.txt
pytest
python web/webapp.py          # 启动开发服务器
```

---

## 许可证

TBD.
