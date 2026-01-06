import os
import logging
import re
import datetime
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
            # 初始化Tavily
            self.tavily_search = TavilySearch(max_results=MAX_SEARCH_RESULTS)
            
            # 创建工具列表
            self.tools = [
                Tool(
                    name="WebSearch",
                    func=self._simple_search,
                    description="通用网络搜索"
                ),
                Tool(
                    name="WeatherSearch",
                    func=self._robust_weather_search,
                    description="天气查询，获取实时天气信息"
                ),
                Tool(
                    name="NewsSearch",
                    func=self._simple_search,
                    description="新闻搜索"
                ),
                Tool(
                    name="PriceSearch",
                    func=self._simple_search,
                    description="价格查询"
                )
            ]
            
            logger.info(f"Web搜索工具初始化成功，共 {len(self.tools)} 个工具")
            
        except Exception as e:
            logger.error(f"Web搜索工具初始化失败: {e}")
            self.tavily_search = None
    
    def _simple_search(self, query: str) -> str:
        """简单稳定的搜索"""
        try:
            if not self.tavily_search:
                return "搜索功能暂不可用"
            
            # 直接运行搜索，不做复杂处理
            result = self.tavily_search.run(query)
            
            # 安全处理结果
            if result is None:
                return f"未找到关于'{query}'的信息。"
            
            result_str = str(result)
            
            # 限制长度
            if len(result_str) > 500:
                return result_str[:497] + "..."
            
            return result_str
            
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return f"搜索失败: {str(e)}"
    
    def _robust_weather_search(self, location: str) -> str:
        """天气搜索"""
        try:
            logger.info(f"开始天气搜索: {location}")
            
            if not self.tavily_search:
                return "天气搜索功能暂不可用"
            
            # 方案1: 尝试专业查询
            weather_info = self._try_professional_weather_query(location)
            if weather_info and "失败" not in weather_info and "暂不可用" not in weather_info:
                return weather_info
            
            # 方案2: 尝试简单查询
            weather_info = self._try_simple_weather_query(location)
            if weather_info and "失败" not in weather_info and "暂不可用" not in weather_info:
                return weather_info
            
            # 方案3: 使用备用方案
            return self._fallback_weather_info(location)
            
        except Exception as e:
            logger.error(f"天气搜索失败: {e}")
            return f"无法获取{location}的天气信息，请稍后再试。"
    
    def _try_professional_weather_query(self, location: str) -> str:
        """尝试专业天气查询"""
        try:
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            query = f"{today} {location} 天气 实时 气温 湿度 风力"
            
            logger.debug(f"专业查询: {query}")
            result = self.tavily_search.run(query)
            
            if not result:
                return ""
            
            # 转换为字符串并安全处理
            result_str = str(result) if result else ""
            
            # 提取天气信息
            weather_data = self._parse_weather_from_text(result_str, location)
            if weather_data:
                return weather_data
            
            # 如果无法解析，返回原始结果
            if len(result_str) > 300:
                return f" {location}天气信息：{result_str[:297]}..."
            return f" {location}天气信息：{result_str}"
            
        except Exception as e:
            logger.debug(f"专业查询失败: {e}")
            return ""
    
    def _try_simple_weather_query(self, location: str) -> str:
        """尝试简单天气查询"""
        try:
            query = f"{location} 今天天气"
            
            logger.debug(f"简单查询: {query}")
            result = self.tavily_search.run(query)
            
            if not result:
                return ""
            
            result_str = str(result) if result else ""
            
            # 检查是否包含天气关键词
            weather_keywords = ['天气', '气温', '温度', '度', '晴', '雨', '云', '风']
            if any(keyword in result_str for keyword in weather_keywords):
                if len(result_str) > 200:
                    return f" {location}天气：{result_str[:197]}..."
                return f" {location}天气：{result_str}"
            
            return ""
            
        except Exception as e:
            logger.debug(f"简单查询失败: {e}")
            return ""
    
    def _parse_weather_from_text(self, text: str, location: str) -> str:
        """从文本中解析天气信息"""
        if not text or not isinstance(text, str):
            return ""
        
        # 确保text是字符串
        text_str = str(text)
        
        # 查找温度信息
        temp_match = None
        temp_patterns = [
            r'(\d+)\s*[℃°C度]',
            r'气温[：:]\s*(\d+)',
            r'温度[：:]\s*(\d+)'
        ]
        
        for pattern in temp_patterns:
            match = re.search(pattern, text_str)
            if match:
                temp_match = match
                break
        
        # 查找天气状况
        weather_match = None
        weather_keywords = ['晴', '多云', '阴', '雨', '小雨', '中雨', '大雨', '雪', '雾']
        for keyword in weather_keywords:
            if keyword in text_str:
                weather_match = keyword
                break
        
        # 查找风力
        wind_match = None
        wind_patterns = [
            r'([东南西北]风\s*\d*级)',
            r'风力[：:]\s*([^，。\n]+)',
            r'风[：:]\s*([^，。\n]+)'
        ]
        
        for pattern in wind_patterns:
            match = re.search(pattern, text_str)
            if match:
                wind_match = match.group(1)
                break
        
        # 构建结果
        if temp_match or weather_match or wind_match:
            result = f" {location}当前天气：\n"
            
            if temp_match:
                temp_value = temp_match.group(1)
                result += f" 温度：{temp_value}°C\n"
            
            if weather_match:
                result += f" 天气：{weather_match}\n"
            
            if wind_match:
                result += f" 风力：{wind_match}\n"
            
            # 添加时间
            current_time = datetime.datetime.now().strftime("%H:%M")
            result += f" 更新时间：{current_time}"
            
            return result
        
        return ""
    
    def _fallback_weather_info(self, location: str) -> str:
        """备用天气信息"""
        try:
            # 尝试直接搜索
            query = f"{location} weather"
            result = self.tavily_search.run(query)
            
            if result:
                result_str = str(result)
                if len(result_str) > 100:
                    return f" {location}天气信息：{result_str[:100]}..."
                return f" {location}天气信息：{result_str}"
            
            # 最终备用
            return f" 暂时无法获取{location}的详细天气信息。\n建议使用天气APP或查看中国天气网获取实时信息。"
            
        except Exception:
            return f" 暂时无法获取{location}的天气信息，请稍后再试。"
    
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
            return self._simple_search(query)
            
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