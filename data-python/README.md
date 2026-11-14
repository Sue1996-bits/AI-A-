# Tech-Pulse · data-python（Week 1 实现）

这是 Tech-Pulse V2.0 方案里 **Python 数据处理层** 的代码实现：采集财经新闻 → 进入 Redis 消息队列 → 大模型分析 → 结果写入 MySQL。

## 架构

```
新浪财经首页
   │  requests + BeautifulSoup（每 10 分钟一轮，URL 去重）
   ▼
crawlers/sina_finance_crawler.py  ── 生产者 ──►  Redis 队列 news_processing_queue（RQ）
                                                     │
                                                     ▼
                                   jobs/analysis_worker.py  CostAwareAnalyzer
                                   · 优先调用 Gemini 2.0 Flash，失败或超预算时降级到 DeepSeek
                                   · 一次调用同时产出：摘要、事件类型、核心实体、情绪分（-1~1）、置信度
                                   · 记录每日调用次数和费用，超出预算自动熔断；带重试和超时
                                                     │
                                                     ▼
                                   database.py（SQLAlchemy）→ MySQL：news、analysis_results 两张表
```

## 文件说明

| 文件 | 作用 |
|---|---|
| `config.py` | 从 `.env` 读取 Redis / MySQL 配置，定义队列名、任务超时（600 秒）、请求头 |
| `crawlers/sina_finance_crawler.py` | 生产者：抓首页链接和正文，把新闻打包成任务入队（用 URL 作为 job_id 防止重复入队） |
| `jobs/analysis_worker.py` | `CostAwareAnalyzer`：多模型分级调用、Prompt 设计、JSON 结果解析、费用统计；`main()` 里有正面 / 负面 / 中性新闻的测试用例 |
| `database.py` | ORM 模型和读写封装：保存新闻、保存分析结果、更新处理状态 |

## 运行流程

1. 准备环境：Python 3.10+、Redis、MySQL 8。
   ```bash
   pip install -r ../requirements.txt
   ```
2. 在 `data-python/` 下新建 `.env`（参考 `.env.example`），填入 `DATABASE_URL`、`GEMINI_API_KEY`、`DEEPSEEK_API_KEY`，Redis 不在本机时还要填 `REDIS_HOST` 等。
3. 先单独测试 AI 分析模块（会调用真实 API，产生少量费用）：
   ```bash
   cd data-python
   python jobs/analysis_worker.py
   ```
4. 启动 Redis 后，运行生产者开始抓取并入队：
   ```bash
   python crawlers/sina_finance_crawler.py
   ```
5. 另开一个终端启动 RQ worker 消费队列：
   ```bash
   rq worker news_processing_queue
   ```

## 当前进度

- 已完成：爬虫生产者、Redis/RQ 入队、`CostAwareAnalyzer`（Gemini → DeepSeek 降级、预算控制、重试）、数据库模型。
- 未完成：生产者入队时引用的 `worker.process_news_task_wrapper`（负责把队列任务交给分析器并写库）还没有写进仓库；方案中的 Go 后端、WebSocket 推送和 Vue 前端尚未开始。
- 整理上传时只做了两处修正：补上 `import os` 和 `WORKER_TIMEOUT` 的导入，并把写死的 API 密钥改为从环境变量读取。代码未在整理后重新运行验证。
