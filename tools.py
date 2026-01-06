import os
import logging
from typing import List, Optional, Dict, Any
from langchain.tools import Tool
from config import TAVILY_API_KEY, MAX_SEARCH_RESULTS, ENABLE_WEB_SEARCH
from langchain_tavily import TavilySearch

logger = logging.getLogger(__name__)

class WebSearchTools:
    """网络搜索工具集"""
    
    def __init__(self):
        self.tools = []
        self.tavily_search = None
        self._initialize_tools()
    
    def _initialize_tools(self):
        """初始化搜索工具"""
        if not ENABLE_WEB_SEARCH:
            logger.info("Web搜索功能已禁用")
            return
        
        if not TAVILY_API_KEY:
            logger.warning("Tavily API密钥未配置，Web搜索功能将不可用")
            return
        
        try:
            os.environ['TAVILY_API_KEY'] = TAVILY_API_KEY
            
            # 配置Tavily参数，要求直接返回答案+深度搜索
            self.tavily_search = TavilySearch(
                max_results=MAX_SEARCH_RESULTS,
                search_depth="deep",  # 深度搜索，获取更精准结果
                include_answer=True,   # 要求Tavily直接返回总结性答案
                include_raw_content=True,  # 包含原始内容，便于提取核心信息
                include_images=False,
                api_key=TAVILY_API_KEY
            )
            
            # 创建工具列表
            self.tools = [
                Tool(
                    name="WebSearch",
                    func=self._general_search,
                    description="通用网络搜索，用于获取最新的市场信息、新闻、价格等实时数据"
                ),
                Tool(
                    name="WeatherSearch",
                    func=self._weather_search,
                    description="天气查询，用于获取指定地区的实时气温、天气状况、风力、湿度等精准数据"
                ),
                Tool(
                    name="NewsSearch",
                    func=self._news_search,
                    description="新闻搜索，用于获取最新的新闻和时事信息"
                ),
                Tool(
                    name="PriceSearch",
                    func=self._price_search,
                    description="价格查询，用于获取商品价格、市场行情等信息"
                )
            ]
            
            logger.info(f"Web搜索工具初始化成功，共 {len(self.tools)} 个工具")
            
        except ImportError:
            logger.warning("Tavily搜索库未安装，请运行: pip install tavily-python")
        except Exception as e:
            logger.error(f"Web搜索工具初始化失败: {e}")
    
    def _general_search(self, query: str) -> str:
        """通用网络搜索"""
        try:
            if not self.tavily_search:
                return "Web搜索功能暂不可用"
            
            # 执行搜索
            results = self.tavily_search.invoke({
                "query": query,
                "search_depth": "deep",
                "include_answer": True
            })
            
            # 优先提取Tavily的直接答案
            final_result = self._extract_core_info(results, query_type="general")
            return self._format_search_results(final_result, prefix="")
            
        except Exception as e:
            logger.error(f"通用搜索失败: {e}")
            return f"搜索失败: {str(e)}"
    
    def _weather_search(self, location: str) -> str:
        """天气搜索"""
        try:
            if not self.tavily_search:
                return "天气搜索功能暂不可用"
            
            # 优化关键词：指定日期、核心维度（实时气温、天气状况、风力、湿度）
            import datetime
            today = datetime.date.today().strftime("%Y年%m月%d日")
            precise_query = f"{today} {location} 实时天气 气温 天气状况 湿度 风力 空气质量"
            
            # 执行精准搜索
            results = self.tavily_search.invoke({
                "query": precise_query,
                "search_depth": "deep",
                "include_answer": True  # 要求Tavily直接返回总结答案
            })
            
            # 提取天气核心信息（温度、天气、风力等）
            final_result = self._extract_core_info(results, query_type="weather")
            return self._format_search_results(final_result, prefix=f"{location}今日天气：")
            
        except Exception as e:
            logger.error(f"天气搜索失败: {e}")
            return f"天气查询失败: {str(e)}"
    
    def _news_search(self, topic: str) -> str:
        """新闻搜索（优化关键词）"""
        try:
            if not self.tavily_search:
                return "新闻搜索功能暂不可用"
            
            # 优化关键词：指定时间范围、核心要素
            precise_query = f"{topic} 最新新闻 2026 核心内容 摘要 来源"
            results = self.tavily_search.invoke({
                "query": precise_query,
                "search_depth": "deep",
                "include_answer": True
            })
            
            final_result = self._extract_core_info(results, query_type="news")
            return self._format_search_results(final_result, prefix=f"{topic}最新新闻：")
            
        except Exception as e:
            logger.error(f"新闻搜索失败: {e}")
            return f"新闻搜索失败: {str(e)}"
    
    def _price_search(self, product: str) -> str:
        """价格搜索（优化关键词）"""
        try:
            if not self.tavily_search:
                return "价格搜索功能暂不可用"
            
            # 优化关键词：指定实时、核心价格维度
            precise_query = f"{product} 实时价格 2026 市场价 报价 优惠活动"
            results = self.tavily_search.invoke({
                "query": precise_query,
                "search_depth": "deep",
                "include_answer": True
            })
            
            final_result = self._extract_core_info(results, query_type="price")
            return self._format_search_results(final_result, prefix=f"{product}价格信息：")
            
        except Exception as e:
            logger.error(f"价格搜索失败: {e}")
            return f"价格查询失败: {str(e)}"
    
    def _extract_core_info(self, results: Any, query_type: str) -> str:
        """提取核心信息"""
        # 优先使用Tavily直接返回的答案
        if isinstance(results, dict) and results.get('answer'):
            return results['answer']
        
        # 处理列表格式的结果，提取核心信息
        core_info = ""
        if isinstance(results, list):
            for result in results[:MAX_SEARCH_RESULTS]:
                if isinstance(result, dict):
                    # 提取核心内容
                    content = result.get('content', '') or result.get('raw_content', '')
                    core_info += content + "\n\n"
        
        # 针对不同类型做结构化提取
        if query_type == "weather":
            # 提取天气核心数据的关键词
            import re
            # 匹配温度（如 15℃、20度、气温18℃）
            temp_match = re.search(r'(\d{1,2})[℃度]', core_info)
            # 匹配天气状况（晴、多云、阴、小雨、大雨）
            weather_match = re.search(r'(晴|多云|阴|小雨|中雨|大雨|暴雨|雪|雾|雷阵雨)', core_info)
            # 匹配风力（如 微风、3级、东风2级）
            wind_match = re.search(r'([东西南北]风\s*\d*级|微风|无风|阵风)', core_info)
            
            # 结构化天气信息
            structured_weather = []
            if temp_match:
                structured_weather.append(f"气温：{temp_match.group(1)}℃")
            if weather_match:
                structured_weather.append(f"天气：{weather_match.group(1)}")
            if wind_match:
                structured_weather.append(f"风力：{wind_match.group(1)}")
            
            if structured_weather:
                core_info = "，".join(structured_weather)
            else:
                core_info = core_info[:300]  # 无结构化信息则取前300字
        
        return core_info.strip() or "未找到精准的核心信息"
    
    def _format_search_results(self, results: Any, prefix: str = "") -> str:
        """格式化搜索结果（优化版：优先核心信息）"""
        if not results:
            return "未找到相关信息。"
        
        # 如果是字符串且已有核心信息，直接返回
        if isinstance(results, str):
            return f"{prefix}{results}" if prefix else results
        
        return f"{prefix}暂无精准数据，请参考以下信息：\n{str(results)[:500]}" if prefix else str(results)[:500]
    
    def get_tools(self) -> List[Tool]:
        """获取所有可用的工具"""
        return self.tools
    
    def search(self, query: str, tool_name: str = "WebSearch") -> str:
        """使用指定工具进行搜索"""
        try:
            for tool in self.tools:
                if tool.name == tool_name:
                    return tool.func(query)
            
            # 如果没有找到指定工具，使用通用搜索
            return self._general_search(query)
            
        except Exception as e:
            logger.error(f"工具搜索失败: {e}")
            return f"搜索过程出错: {str(e)}"

# 单例实例
web_tools = None

def get_web_tools():
    """获取Web工具单例"""
    global web_tools
    if web_tools is None:
        web_tools = WebSearchTools()
    return web_tools