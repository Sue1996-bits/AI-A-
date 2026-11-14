# config.py
import os
from redis import Redis
from dotenv import load_dotenv

# 加载.env文件中的环境变量
load_dotenv()

# Redis配置
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD') or None

# 队列配置
QUEUE_NAME = 'news_processing_queue'
WORKER_TIMEOUT = 600  # Worker任务超时时间（秒），增加以适应AI分析

# Redis连接实例 (用于RQ同步操作和Pub/Sub)
redis_conn = Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    password=REDIS_PASSWORD,
    decode_responses=True # 确保从Redis读取的字符串是Python str
)

# 数据库配置
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("数据库连接字符串 'DATABASE_URL' 未在.env文件中设置")

# 新浪财经配置
SINA_FINANCE_URL = "https://finance.sina.com.cn/"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}