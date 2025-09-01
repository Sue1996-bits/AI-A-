**聚焦A股科技股，利用AI API进行深度情绪与事件分析**——完整、可落地、且亮点突出的技术方案。

---

### **项目名称：** “**Tech-Pulse**” - AI驱动的A股科技股情绪与事件分析系统

### **项目愿景 (Elevator Pitch):**
> 本系统旨在实时捕捉和量化影响中国A股高科技公司的非结构化信息流，通过AI驱动的情绪分析和事件抽取技术，将繁杂的新闻、公告转化为直观的可视化洞察，为理解科技股的价值波动提供一个全新的数据决策维度。

---

### **一、 系统架构图**

这是一个经典且实用的分层架构，清晰地展示了数据流和技术模块。

```mermaid
graph TD
    subgraph 数据源 ["数据源 (Data Sources)"]
        DS1[财经新闻网站<br/>东方财富, 雪球]
        DS2[官方公告<br/>巨潮资讯网]
        DS3[股票行情API<br/>Tushare/AkShare]
    end
    
    subgraph 数据处理层 ["数据处理层 (Data Processing Layer - Python)"]
        P1[数据采集模块<br/>Scrapy/Requests]
        P2[AI分析模块<br/>Baidu NLP API Client]
        P3[定时任务调度<br/>APScheduler]
    end
    
    subgraph 数据存储层 ["数据存储层 (Data Storage Layer)"]
        DB1[MySQL/PostgreSQL<br/>结构化数据]
        DB2[InfluxDB 可选<br/>时序行情数据]
    end
    
    subgraph 后端服务层 ["后端服务层 (Backend Service Layer - Go)"]
        G1[Gin Web框架]
        G2[GORM ORM]
        G3[API接口<br/>RESTful / GraphQL]
    end
    
    subgraph 前端展示层 ["前端展示层 (Frontend Presentation Layer)"]
        F1[Vue 3 + Vite]
        F2[ECharts for Visualization]
        F3[Element Plus UI]
    end
    
    U[用户 User]
    ext_AI[百度智能云NLP API]
    
    %% 数据流连接
    DS1 --> P1
    DS2 --> P1
    DS3 --> P1
    
    P1 --> P3
    P2 --> P3
    
    P1 --> DB1
    P1 --> DB2
    
    P3 --> P1
    P3 --> P2
    
    P2 --> DB1
    P2 --> ext_AI
    ext_AI --> P2
    
    DB1 --> G2
    DB2 --> G2
    G2 --> G1
    G1 --> G3
    
    G3 --> F1
    F1 --> F2
    F1 --> F3
    
    F1 --> U
```

---

### **二、 核心技术栈 (Tech Stack)**

*   **数据处理 (Python):**
    *   **数据采集:** `requests` + `BeautifulSoup` (轻量爬取), `scrapy` (复杂爬取)
    *   **行情获取:** `akshare` 或 `tushare`
    *   **任务调度:** `apscheduler` (定时执行采集和分析任务)
    *   **API调用:** `requests`
*   **后端服务 (Go):**
    *   **Web框架:** `Gin`
    *   **ORM:** `GORM`
    *   **数据库驱动:** `mysql-go` / `pgx`
*   **数据库:**
    *   **主数据库:** **MySQL 8.0** (支持JSON字段，方便存储半结构化数据)
    *   **时序数据库 (可选增强):** **InfluxDB**
*   **前端:**
    *   **框架:** **Vue 3** (使用Composition API) + **Vite** (极速构建)
    *   **UI库:** **Element Plus**
    *   **图表:** **Apache ECharts**
*   **AI服务:**
    *   **百度智能云NLP API:** 核心依赖，用于`情感倾向分析`, `事件抽取`, `文章摘要`。
*   **部署:**
    *   **容器化:** **Docker** & **Docker Compose**
    *   **Web服务器/反向代理:** **Nginx**

---

### **三、 数据库表结构设计 (MySQL)**

这是项目的骨架，设计好能事半功倍。

1.  **`stocks` - 股票信息表**
    *   `id` (PK)
    *   `ticker` (VARCHAR, 股票代码, e.g., '688256.SH', UNIQUE)
    *   `name` (VARCHAR, 股票名称, e.g., '寒武纪')
    *   `industry` (VARCHAR, 行业, e.g., '半导体')
    *   `is_representative` (BOOLEAN, 是否为代表性研究股票)

2.  **`market_data_daily` - 日行情数据表**
    *   `id` (PK)
    *   `stock_ticker` (FK -> stocks.ticker)
    *   `date` (DATE)
    *   `open`, `close`, `high`, `low` (DECIMAL)
    *   `volume` (BIGINT)
    *   UNIQUE KEY `(stock_ticker, date)`

3.  **`news` - 原始新闻表**
    *   `id` (PK)
    *   `url` (VARCHAR, UNIQUE, 防止重复抓取)
    *   `title` (TEXT)
    *   `content` (MEDIUMTEXT)
    *   `publish_time` (DATETIME)
    *   `source` (VARCHAR)
    *   `status` (ENUM('crawled', 'processed', 'failed'), 任务状态)

4.  **`stock_news_relation` - 股票新闻关联表 (多对多)**
    *   `stock_ticker` (FK -> stocks.ticker)
    *   `news_id` (FK -> news.id)
    *   PRIMARY KEY `(stock_ticker, news_id)`

5.  **`sentiments` - 情绪分析结果表**
    *   `id` (PK)
    *   `news_id` (FK -> news.id, UNIQUE)
    *   `sentiment` (ENUM('positive', 'negative', 'neutral'))
    *   `confidence` (FLOAT, 置信度)
    *   `processed_time` (DATETIME)

6.  **`events` - 事件抽取结果表**
    *   `id` (PK)
    *   `news_id` (FK -> news.id)
    *   `stock_ticker` (FK -> stocks.ticker)
    *   `event_type` (VARCHAR, e.g., '产品发布', '战略合作')
    *   `trigger_word` (VARCHAR, 触发词)
    *   `description` (TEXT, 事件描述)
    *   `event_time` (DATETIME, 事件发生时间，从新闻中解析)
    *   `details` (JSON, 存储事件主体、客体等结构化信息)

---

### **四、 核心模块实现要点**

#### **1. Python数据处理层**

*   **定时任务 (`main_scheduler.py`):**
    *   每小时执行`crawl_news()`任务。
    *   每5分钟执行`analyze_news()`任务。
    *   每个交易日下午4点执行`fetch_market_data()`任务。
*   **新闻爬虫 (`crawler.py`):**
    *   针对目标网站编写爬虫逻辑，抓取标题、正文、发布时间。
    *   进行简单的HTML清洗。
    *   对每条新闻，识别出其中提及的代表性股票，建立`stock_news_relation`。
*   **AI分析器 (`analyzer.py`):**
    *   从`news`表查询`status='crawled'`的新闻。
    *   封装调用百度API的函数，做好错误处理和重试机制。
    *   将返回的情绪和事件结果，标准化后存入`sentiments`和`events`表。
    *   更新`news`表的`status`为`processed`。

#### **2. Go后端服务层**

*   **分层结构:**
    *   `main.go`: 程序入口，初始化路由。
    *   `/api`: 定义API路由。
    *   `/controller`: 处理HTTP请求，参数校验，调用Service。
    *   `/service`: 核心业务逻辑，如计算情绪指数、聚合事件数据。
    *   `/dao` (or `/repository`): 数据访问层，封装GORM操作。
    *   `/model`: 定义数据库模型。
*   **核心业务逻辑 (Service):**
    *   **计算情绪指数:** 这是亮点！设计一个聚合算法。例如，可以按天聚合某股票的情绪得分：
      `daily_sentiment_score = SUM( (positive_news * confidence) - (negative_news * confidence) ) / total_news_count`
      可以进一步引入新闻来源、阅读量等作为权重。
    *   **数据聚合API:** 提供给前端的API需要做大量的数据聚合，而不是直接返回原始数据。例如，K线图API需要同时返回行情数据、每日情绪指数和当日发生的事件标记。

#### **3. 前端展示层**

*   **组件化开发:**
    *   `StockSearch.vue`: 股票搜索组件。
    *   `StockChart.vue`: 核心图表组件，内部封装ECharts的初始化和数据更新逻辑。这是最复杂的部分。
    *   `NewsList.vue`: 新闻列表组件，根据情绪显示不同颜色的标签。
    *   `EventTimeline.vue`: 事件时间轴组件。
*   **ECharts高级技巧:**
    *   **双Y轴:** 左Y轴为股价，右Y轴为情绪指数。
    *   **Tooltip联动:** 鼠标在图表上移动时，Tooltip能同时显示股价、成交量、情绪指数、当日事件。
    *   **`markPoint` / `markLine`:** 在图表上精准地标记出事件发生的日期，点击标记可以弹出事件详情。
    *   **`dataZoom`:** 提供时间范围选择和缩放功能。

### **五、 里程碑 (Milestones)**

*   **Week 1:** 完成数据采集和AI分析的Python脚本，能自动抓取新闻、调用API分析，并将结果存入设计好的数据库中。**(后端基础奠定)**
*   **Week 2:** 完成Go后端所有核心API的开发和测试，能为前端提供稳定、聚合好的数据。**(数据通道打通)**
*   **Week 3:** 完成前端核心可视化Dashboard的开发，特别是ECharts图表的实现，能展示K线-情绪叠加图和事件标注。**(核心价值呈现)**
*   **Week 4:** 前后端联调、Bug修复、Docker化部署到云服务器，并撰写项目文档和总结。**(项目闭环与沉淀)**

这个方案为你提供了一张清晰的作战地图。按照这个蓝图，你将能在一个月内，有条不紊地构建出一个技术先进、功能完整、令人印象深刻的毕业设计/求职/申请项目。




---

### **项目名称：** “**Tech-Pulse V2.0**” - 事件驱动的AI金融舆情实时分析系统

### **项目愿景 (Elevator Pitch):**
> 本系统是一套准生产级的金融科技产品原型，旨在通过事件驱动架构和实时通信技术，捕捉并量化影响中国A股高科技公司的信息流。它利用以大语言模型（如Claude 3）为核心的智能AI引擎，将非结构化的新闻、公告转化为精准的情绪指数和结构化事件，并通过WebSocket向前端动态推送，实现真正的实时决策支持。

---

### **一、 系统架构图 (V2.0)**

本系统采用现代化的**事件驱动微服务架构**，确保了高可用性、高扩展性和实时性。

```mermaid
graph TD
    subgraph "数据源 Data Sources"
        DS[财经新闻/公告/行情API]
    end
    
    subgraph "数据处理层 Python - Event-Driven"
        P1[数据采集 Producer]
        MQ[Redis\n消息队列 RQ]
        P2[AI分析 Worker]
    end
    
    subgraph "数据存储层 Data Storage"
        DB[MySQL / PostgreSQL]
        Cache[Redis\nPub/Sub Channel]
    end

    subgraph "后端服务层 Go - Dual-Channel"
        G1[Gin RESTful API\n提供历史/聚合数据]
        G2[WebSocket Server\n实时推送事件]
    end
    
    subgraph "前端展示层 Vue 3"
        F1[动态仪表盘 Dashboard]
    end
    
    U[用户 User Browser]
    ext_AI[智能AI引擎\nClaude 3 / Baidu ERNIE]

    %% 1. 异步数据处理管道
    DS -- "采集" --> P1
    P1 -- "1. 投递任务" --> MQ
    MQ -- "2. 消费任务" --> P2
    P2 -- "3. 调用AI分析" --> ext_AI
    ext_AI -- "返回结果" --> P2
    P2 -- "4a. 持久化结果" --> DB
    P2 -- "4b. 发布事件通知" --> Cache

    %% 2. 双通道后端服务
    DB -- "查询" --> G1
    Cache -- "订阅" --> G2
    
    %% 3. 前端与后端交互
    G1 -- "API Pull" --> F1
    G2 -- "Push" --> F1
    F1 <--> U


```

---

### **二、 核心技术栈 (Tech Stack V2.0)**

*   **数据处理 (Python):**
    *   **数据采集:** `requests` + `BeautifulSoup` / `scrapy`
    *   **消息队列:** `Redis` + `rq` (Python Redis Queue)
    *   **任务调度:** `APScheduler` (用于驱动Producer)
    *   **AI SDK:** `anthropic` (for Claude), `baidu-aip`
*   **后端服务 (Go):**
    *   **Web框架:** `Gin`
    *   **WebSocket:** `gorilla/websocket`
    *   **ORM:** `GORM`
    *   **Redis客户端:** `go-redis`
*   **数据库 & 缓存:**
    *   **主数据库:** **MySQL 8.0**
    *   **消息队列 & Pub/Sub:** **Redis**
*   **前端:**
    *   **框架:** **Vue 3** + **Vite**
    *   **UI库:** **Element Plus**
    *   **图表:** **Apache ECharts**
*   **AI服务:**
    *   **主引擎:** **Anthropic Claude 3** (Sonnet/Haiku)
    *   **备用/降级引擎:** **百度智能云 ERNIE**
*   **部署:**
    *   **容器化:** **Docker** & **Docker Compose**
    *   **Web服务器/反向代理:** **Nginx**

---

### **三、 数据库表结构设计 (保持不变)**

*数据库表结构设计与V1.0方案一致，包含`stocks`, `market_data_daily`, `news`, `stock_news_relation`, `sentiments`, `events`等核心表。*

---

### **四、 核心模块实现要点 (V2.0 升级版)**

#### **1. Python数据处理层 (事件驱动)**
*   **生产者 (`producer.py`):** 由定时任务触发，仅负责抓取新闻，并立即将包含新闻URL和元数据的任务**投递到Redis队列**。自身不做任何耗时处理，确保高吞吐量。
*   **消费者 (`worker.py`):** 独立进程，持续监听Redis队列。获取任务后，调用`CostAwareAnalyzer`进行分析。分析完成后，执行两个关键操作：
    1.  **数据持久化：** 将详细分析结果写入MySQL的`sentiments`和`events`表。
    2.  **事件发布：** 如果判断为重大事件，则向Redis的`realtime-events`频道**发布一条JSON格式的精简消息**（例如 `{"ticker": "688256.SH", "event": "发布重磅新品"}`）。

#### **2. 智能AI分析模块 (`CostAwareAnalyzer`)**
*   **智能分级调用：** 封装一个核心分析函数，内部逻辑优先调用Claude 3 API。通过精心设计的Prompt，力求在**单次API调用**中完成新闻摘要、事件类型判断、情绪打分等多项任务。
*   **成本控制与降级：** 内置预算追踪机制。当调用失败或日成本超预算时，**自动降级**至百度ERNIE API执行基础的情绪分析，保证服务的韧性。

#### **3. Go后端服务层 (双通道)**
*   **RESTful API (Gin):** 职责不变，负责提供“拉取(Pull)”式的数据服务。重点在于**Service层的多因子情绪指数计算逻辑**，它会聚合数据库中的数据，并应用我们设计的时间衰减、来源权重等高级算法。
*   **WebSocket Server (gorilla/websocket):**
    *   启动一个goroutine，使用`go-redis`客户端**订阅`realtime-events`频道**。
    *   维护一个并发安全的连接池，管理所有活跃的前端WebSocket连接。
    *   一旦从Redis频道收到新消息，立即将其**广播**给所有连接的客户端。

#### **4. 前端展示层 (动态实时)**
*   **WebSocket集成：** 在Vue应用的主组件（如`App.vue`）的`onMounted`生命周期钩子中，初始化与后端的WebSocket连接，并设置`onmessage`监听器。
*   **实时反馈：**
    1.  **即时通知:** 当`onmessage`监听到新事件时，调用Element Plus的`ElNotification`组件，在屏幕右上角弹出非侵入式的消息提醒。
    2.  **图表动态更新:** 将收到的事件数据传递给ECharts图表组件，调用ECharts实例的`setOption`方法，**动态地**在图表上增加一个新的`markPoint`，全程无需页面刷新。

### **五、 里程碑 (Milestones V2.0 修订版)**

*   **Week 1: 攻坚智能核心与异步管道**
    *   **目标:** 跑通“生产者(Producer) -> Redis消息队列 -> 消费者(Worker) -> AI分析 -> 数据库”的全异步流程。
    *   **交付:** 一个能在后台默默处理新闻，并把结果存入数据库的健壮数据处理系统。
*   **Week 2: 构建双通道后端服务**
    *   **目标:** 完成所有RESTful API和WebSocket实时推送服务的开发。
    *   **交付:** 一个可以用Postman测试历史数据接口，并用WebSocket客户端接收实时消息的Go后端。
*   **Week 3: 打造动态实时前端**
    *   **目标:** 完成前端Dashboard开发，实现历史数据图表展示，并成功集成WebSocket，能接收并展示实时事件通知和图表标记。
    *   **交付:** 一个功能完整的、具备实时能力的动态Web应用原型。
*   **Week 4: 生产级部署与深度总结**
    *   **目标:** 将包含多个微服务（Go, Python Workers, Redis等）的整套系统通过Docker Compose部署到云端，并产出高质量的项目文档。
    *   **交付:** 一个公网可访问的项目URL，一份突出事件驱动和实时特性的GitHub README，以及一篇分享架构思考的深度技术博客。
