# analyzer.py

import os
import json
import logging
import time
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum
import asyncio
import aiohttp
import re # 用于JSON解析
from datetime import datetime, date, timedelta

# Configure logging  设置全局日志格式与级别（INFO）。
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class APIProvider(Enum):
    GEMINI = "gemini"
    DEEPSEEK = "deepseek"

#数据结构：NewsAnalysisResult，外部可直接使用的结构化分析结果数据模型。
@dataclass
class NewsAnalysisResult:
    """结构化的新闻分析结果"""
    summary: str
    event_type: str
    core_entities: list
    timestamp: Optional[str] # 保持str，便于直接显示，如需datetime可在外部转换
    location: Optional[str]
    sentiment_score: float  # -1 到 1 之间的情绪分值
    confidence: float
    api_used: str
    processing_time: float #度量端到端耗时

#数据结构：APIUsageStats（费用/调用统计 + 日清）
@dataclass
class APIUsageStats:
    """API使用统计"""
    gemini_calls: int = 0
    deepseek_calls: int = 0
    gemini_cost: float = 0.0
    deepseek_cost: float = 0.0
    total_cost: float = 0.0
    last_reset_date: date = date.today() # 记录上次重置日期

    def add_usage(self, provider: APIProvider, estimated_cost: float = 0.0):
        self._check_and_reset_daily_stats() # 每次添加前检查是否需要重置

        if provider == APIProvider.GEMINI:
            self.gemini_calls += 1
            self.gemini_cost += estimated_cost
        else:
            self.deepseek_calls += 1
            self.deepseek_cost += estimated_cost
        self.total_cost = self.gemini_cost + self.deepseek_cost

    def _check_and_reset_daily_stats(self):
        """每日检查并重置统计，模拟每日预算"""
        today = date.today()
        if today > self.last_reset_date:
            logger.info(f"Daily API usage stats reset from {self.last_reset_date} to {today}.")
            self.gemini_calls = 0
            self.deepseek_calls = 0
            self.gemini_cost = 0.0
            self.deepseek_cost = 0.0
            self.total_cost = 0.0
            self.last_reset_date = today

class CostAwareAnalyzer:
    """智能分级AI内容分析器 - 支持gemini/deepseek降级策略"""
    
    def __init__(self, 
                 gemini_api_key: str,
                 deepseek_api_key: str,
                 budget_limit: float = 100.0, # 每日预算
                 gemini_timeout: int = 10,
                 deepseek_timeout: int = 15,
                 max_retries: int = 3,
                 retry_delay_seconds: int = 2):
        """
        初始化分析器
        
        Args:
            gemini_api_key: Gemini API密钥
            deepseek_api_key: DeepSeek API密钥
            budget_limit: 每日预算限制（美元）
            gemini_timeout: Gemini API超时时间（秒）
            deepseek_timeout: DeepSeek API超时时间（秒）
            max_retries: API调用失败最大重试次数
            retry_delay_seconds: 每次重试的延迟时间（秒），可在此基础上实现指数退避
        """
        self.gemini_api_key = gemini_api_key
        self.deepseek_api_key = deepseek_api_key
        self.budget_limit = budget_limit
        self.gemini_timeout = gemini_timeout
        self.deepseek_timeout = deepseek_timeout
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
        
        # 使用统计 (初始化时加载持久化数据，这里简化为内存)
        self.usage_stats = APIUsageStats() 
        
        # API端点配置
        self.gemini_endpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
        self.deepseek_endpoint = "https://api.deepseek.com/chat/completions"
        
        # 价格配置 (每1K tokens的估算成本) - 假定Gemini比DeepSeek更贵
        self.pricing = {
            APIProvider.GEMINI: {"input": 0.0005, "output": 0.0015}, # 估算价格
            APIProvider.DEEPSEEK: {"input": 0.00014, "output": 0.00028} # 估算价格
        }
        
        # aiohttp session
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建aiohttp客户端会话"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close_session(self):
        """关闭aiohttp客户端会话"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
            logger.info("aiohttp client session closed.")

    def _create_gemini_prompt(self, news_content: str) -> str:
        """创建Gemini超级Prompt"""
        return f"""
作为专业的新闻分析AI，请对以下新闻内容进行全面分析，并以JSON格式返回结果：

新闻内容：
{news_content}

请提供以下分析结果（严格按照JSON格式）：
{{
    "summary": "新闻摘要（100字以内）",
    "event_type": "事件类型（如：财经、政治、科技、体育等）",
    "core_entities": ["核心实体1", "核心实体2", "核心实体3"],
    "timestamp": "事件发生时间（尽量具体，如2023-10-26或模糊描述如“最近”），如果没有明确时间可留空",
    "location": "事件发生地点（如：北京、全球市场），如果没有明确地点可留空",
    "sentiment_score": 情绪分值（-1到1之间的浮点数，-1极端负面，0中性，1极端正面）,
    "confidence": 分析置信度（0到1之间的浮点数，0最低，1最高）
}}

要求：
1. 摘要要简洁明了，突出核心信息
2. 事件类型要准确分类
3. 核心实体包括人物、组织、产品、地点等关键要素
4. 情绪分值要客观准确，基于新闻tone和内容影响
5. 置信度反映分析的准确性
6. 必须返回有效的JSON格式，确保所有键值对都存在，即使为空或为默认值
"""

    def _create_deepseek_prompt(self, news_content: str) -> str:
        """创建DeepSeek Prompt（功能对标Gemini）"""
        return f"""
你是一个专业的新闻分析助手。请分析以下新闻内容，并返回JSON格式的分析结果：

新闻内容：
{news_content}

分析要求：
1. 生成简洁摘要（100字内）
2. 识别事件类型（如：财经、政治、科技、体育等）
3. 提取核心实体（人物、机构、地点等）
4. 判断情绪倾向（-1到1分值，-1极端负面，0中性，1极端正面）
5. 评估分析置信度（0到1分值，0最低，1最高）
6. 明确提供事件发生时间（如果没有明确时间可留空）
7. 明确提供事件发生地点（如果没有明确地点可留空）

请返回严格的JSON格式：
{{
    "summary": "摘要内容",
    "event_type": "事件分类",
    "core_entities": ["实体1", "实体2"],
    "timestamp": "时间（如有）",
    "location": "地点（如有）",
    "sentiment_score": 数值,
    "confidence": 数值
}}
"""
    #构建 HTTP 请求 → 调用第三方 API → 解析提取文本 → 估算成本并记录 → 返回已解析的 JSON（Python dict）。
    async def _call_api_with_retry(self, provider: APIProvider, news_content: str, is_gemini: bool) -> Dict[str, Any]:
        """封装API调用，支持重试和指数退避"""
        session = await self._get_session()
        
        headers = { "Content-Type": "application/json" }
        payload = {}
        url = ""
        timeout = 0
        
        if is_gemini:
            headers = { "Content-Type": "application/json" } # Gemini不需要Bearer token
            payload = {
                "contents": [{ "parts": [{ "text": self._create_gemini_prompt(news_content) }] }],
                "generationConfig": { "temperature": 0.1, "maxOutputTokens": 1000 }
            }
            url = f"{self.gemini_endpoint}?key={self.gemini_api_key}"
            timeout = self.gemini_timeout
        else: # DeepSeek
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.deepseek_api_key}"
            }
            payload = {
                "model": "deepseek-chat",
                "messages": [{ "role": "user", "content": self._create_deepseek_prompt(news_content) }],
                "temperature": 0.1,
                "max_tokens": 1000,
                "stream": False # 明确指定 stream
            }
            url = self.deepseek_endpoint
            timeout = self.deepseek_timeout
        #重试循环
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Attempt {attempt + 1}/{self.max_retries} to call {provider.value} API...")
                async with session.post(url, headers=headers, json=payload, timeout=timeout) as response:
                    response.raise_for_status() # Raises an error for bad status codes
                    result = await response.json()
                    #抽取模型“文本内容”（两家返回结构不同）：
                    content = ""
                    if is_gemini:
                        if 'candidates' in result and len(result['candidates']) > 0:
                            content = result['candidates'][0]['content']['parts'][0]['text']
                        else:
                            raise ValueError("Gemini API returned empty candidates.")
                    else: # DeepSeek
                        if 'choices' in result and len(result['choices']) > 0:
                            content = result['choices'][0]['message']['content']
                        else:
                            raise ValueError("DeepSeek API returned empty choices.")
                    
                    # 估算成本并记录
                    estimated_cost = self._estimate_cost(news_content, content, provider)
                    self.usage_stats.add_usage(provider, estimated_cost)  #记账
                    logger.info(f"{provider.value} API call successful. Estimated cost: {estimated_cost:.4f} USD.")
                    
                    return self._parse_api_response(content)  # 解析并返回

            except aiohttp.ClientError as e:
                logger.warning(f"{provider.value} API ClientError (attempt {attempt + 1}): {e}")    # 网络或HTTP错误
            except asyncio.TimeoutError:
                logger.warning(f"{provider.value} API Timeout (attempt {attempt + 1}).")
            except ValueError as e: # JSON解析失败或API返回内容不符合预期
                logger.warning(f"{provider.value} API response parsing error (attempt {attempt + 1}): {e}. Raw: {result if 'result' in locals() else 'N/A'}")
            except Exception as e:
                logger.error(f"{provider.value} API unexpected error (attempt {attempt + 1}): {e}")

            if attempt < self.max_retries - 1:
                delay = self.retry_delay_seconds * (2 ** attempt) # 指数退避
                logger.info(f"Retrying {provider.value} API in {delay} seconds...")
                await asyncio.sleep(delay)
            else:
                logger.error(f"Max retries reached for {provider.value} API. Failed to get response.")
                raise

        raise Exception(f"Failed to call {provider.value} API after {self.max_retries} attempts.")
    
    def _parse_api_response(self, response_text: str) -> Dict[str, Any]:
        """解析API响应的JSON内容,从模型文本中稳妥拿到 JSON（容错）。"""
        try:
            # 尝试直接解析JSON
            if response_text.strip().startswith('{') and response_text.strip().endswith('}'):
                return json.loads(response_text.strip())
            
            # 尝试从markdown代码块中提取JSON
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
            
            # 尝试查找JSON对象（更宽松的匹配）
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            
            raise ValueError(f"无法从响应中提取有效JSON: {response_text[:200]}...") # 打印部分响应
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {str(e)}. 原始响应: {response_text[:200]}...")
            raise ValueError(f"JSON解析错误: {str(e)}")
    
    def _estimate_cost(self, input_text: str, output_text: str, provider: APIProvider) -> float:
        """估算API调用成本"""
        # 简单的token估算（1个英文单词或2个汉字 ≈ 1 token，这里简化为字符数）
        # 生产环境中应使用对应模型的tokenizer
        input_tokens = len(input_text) // 2 # 假设平均1字符0.5 token
        output_tokens = len(output_text) // 2
        
        pricing = self.pricing[provider]
        cost = (input_tokens / 1000 * pricing["input"]) + (output_tokens / 1000 * pricing["output"])
        
        return cost
    
    def _check_budget(self) -> bool:
        """检查预算限制"""
        self.usage_stats._check_and_reset_daily_stats() # 确保在使用前检查并重置
        return self.usage_stats.total_cost < self.budget_limit
    
    async def analyze_news(self, news_content: str, force_provider: Optional[APIProvider] = None) -> NewsAnalysisResult:
        """
        分析新闻内容的主要方法
        
        Args:
            news_content: 新闻文本内容
            force_provider: 强制使用指定的API提供商
            
        Returns:
            NewsAnalysisResult: 分析结果
        """
        start_time = time.time()  #计算处理时长。
        
        # 预算检查
        if not self._check_budget():
            logger.error(f"已超出每日预算限制: {self.budget_limit}美元. 当前成本: {self.usage_stats.total_cost:.4f}美元")
            raise Exception(f"已超出每日预算限制: {self.budget_limit}美元")
        
        api_used = None
        analysis_data = {} # 存储API返回的原始数据
        
        try:
            # 如果指定了提供商，直接使用
            if force_provider:
                if force_provider == APIProvider.GEMINI:
                    analysis_data = await self._call_api_with_retry(APIProvider.GEMINI, news_content, is_gemini=True)
                    api_used = "gemini"
                else: # DeepSeek
                    analysis_data = await self._call_api_with_retry(APIProvider.DEEPSEEK, news_content, is_gemini=False)
                    api_used = "deepseek"
            else:
                # 默认策略：优先使用Gemini，失败时降级到DeepSeek
                try:
                    logger.info("尝试使用Gemini API进行分析...")
                    analysis_data = await self._call_api_with_retry(APIProvider.GEMINI, news_content, is_gemini=True)
                    api_used = "gemini"
                    logger.info("Gemini API调用成功")
                    
                except Exception as gemini_error:
                    logger.warning(f"Gemini API失败，降级到DeepSeek: {str(gemini_error)}")
                    
                    try:
                        analysis_data = await self._call_api_with_retry(APIProvider.DEEPSEEK, news_content, is_gemini=False)
                        api_used = "deepseek"
                        logger.info("DeepSeek API调用成功")
                    except Exception as deepseek_error:
                        logger.error(f"DeepSeek API也失败: {str(deepseek_error)}")
                        raise Exception(f"所有API调用都失败 - Gemini: {str(gemini_error)}, DeepSeek: {str(deepseek_error)}")
        
        except Exception as e:
            logger.error(f"新闻分析主流程失败: {str(e)}")
            raise
        
        processing_time = time.time() - start_time
        
        # 构造结果对象，确保所有字段都存在且类型正确。调用方拿到的是稳定类型的数据对象，少做健壮性处理。
        return NewsAnalysisResult(
            summary=analysis_data.get('summary', 'N/A'),
            event_type=analysis_data.get('event_type', '未知'),
            core_entities=analysis_data.get('core_entities', []),
            timestamp=analysis_data.get('timestamp'),
            location=analysis_data.get('location'),
            sentiment_score=float(analysis_data.get('sentiment_score', 0.0)),
            confidence=float(analysis_data.get('confidence', 0.0)),
            api_used=api_used,
            processing_time=processing_time
        )
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """获取API使用统计信息"""
        self.usage_stats._check_and_reset_daily_stats() # 获取前也检查确保最新
        return {
            "gemini_calls": self.usage_stats.gemini_calls,
            "deepseek_calls": self.usage_stats.deepseek_calls,
            "gemini_cost": round(self.usage_stats.gemini_cost, 4),
            "deepseek_cost": round(self.usage_stats.deepseek_cost, 4),
            "total_cost": round(self.usage_stats.total_cost, 4),
            "budget_limit": self.budget_limit,
            "budget_remaining": round(self.budget_limit - self.usage_stats.total_cost, 4),
            "budget_used_percentage": round((self.usage_stats.total_cost / self.budget_limit) * 100, 2) if self.budget_limit > 0 else 0.0
        }
    
    def reset_usage_stats(self):
        """重置使用统计"""
        self.usage_stats = APIUsageStats() # 创建一个新的实例，会默认重置日期
        logger.info("使用统计已重置")

# 使用示例和测试代码 (需要将if __name__ == "__main__": 块修改为异步运行)
async def main():
    # API keys are read from environment variables (see .env.example); never hard-code them
    from dotenv import load_dotenv
    load_dotenv()

    analyzer = CostAwareAnalyzer(
        gemini_api_key=os.environ.get("GEMINI_API_KEY"),
        deepseek_api_key=os.environ.get("DEEPSEEK_API_KEY"),
        budget_limit=1.0 # 设置一个较低的预算进行测试
    )
    
    #定义三段测试新闻（正/负/中性），以及一次强制 DeepSeek 调用。
    test_news_positive = """
    新浪财经讯，特斯拉公司今日发布第三季度财报，营收达到233.5亿美元，
    同比增长9%，净利润为18.5亿美元。CEO马斯克在财报电话会议中表示，
    公司将继续扩大在中国市场的投资，预计明年在上海超级工厂的产能将
    提升30%。受此消息影响，特斯拉股价盘后上涨5.2%。
    """

    test_news_negative = """
    【突发】某科技巨头因数据泄露面临巨额罚款，股价暴跌15%。
    公司高管表示将彻查此事，但市场信心严重受挫。
    """
    
    test_news_neutral = """
    北京时间周二上午，某国际会议在维也纳召开，主要议题围绕全球经济合作与发展。
    各方代表就贸易政策和气候变化等问题进行了深入讨论，预计本周晚些时候将发布联合声明。
    """

    try:
        print("\n--- 分析积极新闻 ---")
        result_pos = await analyzer.analyze_news(test_news_positive)
        print(f"摘要: {result_pos.summary}")
        print(f"情绪分值: {result_pos.sentiment_score}")
        print(f"使用API: {result_pos.api_used}")
        
        print("\n--- 分析消极新闻 ---")
        result_neg = await analyzer.analyze_news(test_news_negative)
        print(f"摘要: {result_neg.summary}")
        print(f"情绪分值: {result_neg.sentiment_score}")
        print(f"使用API: {result_neg.api_used}")

        print("\n--- 分析中性新闻 ---")
        result_neu = await analyzer.analyze_news(test_news_neutral)
        print(f"摘要: {result_neu.summary}")
        print(f"情绪分值: {result_neu.sentiment_score}")
        print(f"使用API: {result_neu.api_used}")

        print("\n=== 强制使用 DeepSeek 分析 === ")
        result_force_deepseek = await analyzer.analyze_news(test_news_positive, force_provider=APIProvider.DEEPSEEK)
        print(f"摘要: {result_force_deepseek.summary}")
        print(f"情绪分值: {result_force_deepseek.sentiment_score}")
        print(f"使用API: {result_force_deepseek.api_used}")

        print("\n=== 尝试超出预算限制 ===")
        # 连续调用直到超出预算
        while True:
            try:
                current_stats = analyzer.get_usage_stats()
                if current_stats['budget_remaining'] < analyzer.pricing[APIProvider.GEMINI]["input"] / 1000 * (len(test_news_positive) // 2): # 确保至少能触发一次API
                     logger.warning("预算即将耗尽，下一次调用可能触发预算限制。")
                await analyzer.analyze_news(test_news_positive)
                print(f"调用成功，当前总成本: {analyzer.get_usage_stats()['total_cost']:.4f}美元")
                await asyncio.sleep(0.5) # 避免太快
            except Exception as e:
                print(f"捕获到异常: {e}")
                break
        
        print("\n=== 最终使用统计 ===")
        stats = analyzer.get_usage_stats()
        for key, value in stats.items():
            print(f"{key}: {value}")
            
    except Exception as e:
        print(f"主程序分析失败: {str(e)}")
    finally:
        await analyzer.close_session()

if __name__ == "__main__":
    asyncio.run(main())