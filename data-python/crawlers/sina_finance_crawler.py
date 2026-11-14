# news_crawler.py
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import logging
import time
from rq import Queue
from config import redis_conn, QUEUE_NAME, WORKER_TIMEOUT, SINA_FINANCE_URL, HEADERS

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [PRODUCER] - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/crawler.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SinaFinanceNewsCrawler:
    def __init__(self):
        self.queue = Queue(QUEUE_NAME, connection=redis_conn)
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.crawled_urls = set() # 简单去重

    def extract_news_detail(self, news_url):
        try:
            response = self.session.get(news_url, timeout=10)
            response.raise_for_status()
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'lxml')
            content_selectors = ['#artibody', '.article-content', '.article']
            content_element = next((soup.select_one(s) for s in content_selectors if soup.select_one(s)), None)
            return content_element.get_text(strip=True, separator='\n') if content_element else "内容抓取失败"
        except Exception as e:
            logger.error(f"抓取新闻详情失败 {news_url}: {e}")
            return "内容抓取失败"

    def crawl_and_enqueue(self):
        logger.info("开始抓取新浪财经新闻...")
        try:
            response = self.session.get(SINA_FINANCE_URL, timeout=15)
            response.raise_for_status()
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'lxml')
            
            news_links = soup.select('a[href*="finance.sina.com.cn/"]')
            enqueued_count = 0

            for link in news_links:
                title = link.get_text(strip=True)
                url = link.get('href')
                if not title or not url or len(title) < 10: continue

                if url.startswith('//'): url = 'https:' + url
                if not url.startswith('http'): continue
                if url in self.crawled_urls: continue

                self.crawled_urls.add(url)
                logger.info(f"发现新闻: {title}")
                
                news_content = self.extract_news_detail(url)
                if "内容抓取失败" in news_content: continue

                news_item = {
                    'title': title,
                    'url': url,
                    'content': news_content,
                    'publish_time': datetime.now().isoformat(), # 简化处理，实际应解析
                    'source': '新浪财经',
                    'crawl_time': datetime.now().isoformat()
                }
                
                # 将任务放入Redis队列，调用worker.py中的包装函数
                job = self.queue.enqueue(
                    'worker.process_news_task_wrapper',
                    news_item,
                    job_timeout=WORKER_TIMEOUT,
                    result_ttl=86400, # 结果保留一天
                    job_id=f"news_task:{url}" # 使用URL作为job_id防止重复入队
                )
                enqueued_count += 1
                logger.info(f"任务已入队: {job.id}")
                time.sleep(1) # 避免请求过于频繁

            logger.info(f"抓取完成，共 {enqueued_count} 条新任务入队。")

        except Exception as e:
            logger.error(f"新闻抓取主流程发生错误: {e}", exc_info=True)

def main():
    if not os.path.exists('logs'): os.makedirs('logs')
    crawler = SinaFinanceNewsCrawler()
    while True:
        crawler.crawl_and_enqueue()
        logger.info("本轮抓取结束，等待600秒后开始下一轮...")
        time.sleep(600) # 每10分钟抓取一次

if __name__ == "__main__":
    main()