# Claude Blog Follower

追踪和分析 Anthropic 博客文章的命令行工具。通过 Claude API 对文章进行智能摘要和分析，生成 HTML 报告，并支持邮件周报推送。

## 功能

- **存量分析**：抓取 Anthropic 全部历史博客（~195 篇），用 AI 生成摘要和关键技术/观点提取，输出 HTML 时间线报告
- **增量监控**：定期检查新文章，自动分析并发送邮件周报
- **本地存储**：SQLite 数据库保存所有文章和分析结果

## 安装

```bash
git clone <repo-url>
cd Claude-Blog-Follower
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 配置

复制 `.env.example` 为 `.env` 并填写：

```bash
cp .env.example .env
```

```env
# Claude API（必需）
ANTHROPIC_API_KEY=sk-ant-...

# 邮件推送（可选，仅周报功能需要）
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@email.com
SMTP_PASS=app-password
EMAIL_TO=your@email.com
```

## 使用

### 存量分析（一次性）

```bash
# 1. 抓取全部历史文章
python main.py fetch --all

# 2. 用 Claude API 分析所有文章
python main.py analyze

# 3. 生成 HTML 分析报告
python main.py report
# 报告输出到 output/report.html，用浏览器打开即可
```

### 增量监控

```bash
# 手动执行：抓取新文章 + 分析 + 发送周报
python main.py weekly

# 自动执行：设置每周一 9:00 自动运行
python main.py schedule
```

### 其他命令

```bash
python main.py list              # 查看已有文章列表
python main.py list --count 50   # 查看更多
python main.py stats             # 查看统计信息
python main.py analyze --limit 5 # 只分析前 5 篇（测试用）
```

## 技术架构

| 模块 | 说明 |
|------|------|
| `scraper.py` | 通过 sitemap.xml 发现文章 + BeautifulSoup 提取内容 |
| `analyzer.py` | Claude API 调用（Haiku 做单篇摘要，Sonnet 做全局分析） |
| `storage.py` | SQLite 数据库存储 |
| `report.py` | Jinja2 模板生成 HTML 报告 |
| `emailer.py` | SMTP 邮件发送 |
| `cli.py` | argparse 命令行接口 |

## 数据源

通过 `https://www.anthropic.com/sitemap.xml` 获取所有 `/news/` 路径下的博客文章。
