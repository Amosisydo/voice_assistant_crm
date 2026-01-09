import logging
import openai
from config import (OPENAI_API_KEY, API_BASE, LLM_MODEL, LLM_TEMPERATURE, 
                    ENABLE_RAG,ENABLE_WEB_SEARCH, RAG_DOCUMENTS_PATH, VECTOR_STORE_PATH,
                    EMBEDDING_MODEL, TAVILY_API_KEY)
from database import UserManager
from intent_recognizer import IntentRecognizer
from voice_processor import VoiceProcessor
from rag import get_rag_processor
from tools import get_web_tools
logger = logging.getLogger(__name__)

# 配置OpenAI客户端
client = openai.OpenAI(
    api_key=OPENAI_API_KEY,
    base_url=API_BASE
)

class ResponseEngine:
    def __init__(self):
        self.user_manager = UserManager()
        self.intent_recognizer = IntentRecognizer()
        self.voice_processor = VoiceProcessor()

        # 初始化RAG处理器
        self.rag_processor = None
        if ENABLE_RAG:
            try:
                self.rag_processor = get_rag_processor()
                if self.rag_processor.retriever:
                    logger.info("RAG处理器初始化成功")
                else:
                    logger.warning("RAG处理器初始化失败，产品咨询功能将受限")
            except Exception as e:
                logger.error(f"RAG处理器初始化异常: {e}")
        
        # 初始化Web搜索工具
        self.web_tools = None
        if ENABLE_WEB_SEARCH:
            try:
                self.web_tools = get_web_tools()
                if self.web_tools.tools:
                    logger.info(f"Web搜索工具初始化成功，共 {len(self.web_tools.tools)} 个工具")
                else:
                    logger.warning("Web搜索工具初始化失败，实时信息功能将受限")
            except Exception as e:
                logger.error(f"Web搜索工具初始化异常: {e}")
    
    def process_query(self, phone_number: str, query: str, channel: str = 'text') -> dict:
        """处理用户查询，支持文本和语音渠道"""
        # 用户识别和管理
        user_id, is_new_user = self.user_manager.get_or_create_user(phone_number, channel)
        
        # 获取用户对话历史
        chat_history = self.user_manager.get_user_conversations(user_id)
        
        # 记录用户提问
        metadata = {}
        if channel == 'voice':
            metadata = {"channel": "voice", "duration": len(query)/10}  # 示例元数据
        
        self.user_manager.add_conversation(
            user_id, channel, "user", query, 
            audio_path=None, metadata=metadata
        )
        
        # 意图识别
        intent_code = self.intent_recognizer.detect_intent(query)
        logger.info(f"用户{phone_number} 意图识别: {intent_code} (渠道: {channel})")
        
        # 根据意图处理查询
        context = ""
        if intent_code == "A":
            context = self.rag_retrieval(query)
        elif intent_code == "B":
            context = self.web_search(query)
        else:
            context = "对话历史: " + str(chat_history[-5:]) if chat_history else "无历史对话"
        
        # 生成回复
        response = self.generate_response(query, context, intent_code)
        
        # 记录助手回复
        self.user_manager.add_conversation(
            user_id, channel, "assistant", response, intent_code
        )
        
        # 准备返回结果
        result = {
            "user_id": user_id,
            "is_new_user": is_new_user,
            "intent": intent_code,
            "response": response,
            "channel": channel,
            "intent_description": self.intent_recognizer.intent_categories.get(intent_code, "")
        }
        
        return result
    
    async def process_voice_query(self, phone_number: str, audio_data: bytes) -> dict:
        """专门处理语音查询"""
        # 使用语音处理器处理
        result = await self.voice_processor.process_voice_query(audio_data, phone_number)
        return result

    def generate_response(self, query: str, context: str, intent: str) -> str:
        """生成最终回复"""
        prompt_templates = {
            "A": f"""
            你是一个专业的客服助手。基于以下信息回复用户：
            
            用户问题：{query}
            检索到的产品信息：{context}
            用户历史对话：请参考对话历史提供连贯的回复
            
            请提供专业、准确的产品咨询回复。
            """,
            "B": f"""
            你是一个信息助手。基于以下信息回复用户：
            
            用户问题：{query}
            实时搜索信息：{context}
            
            请提供最新、准确的实时信息。
            """,
            "C": f"""
            你是一个友好的客服助手。回复用户问题：
            
            用户问题：{query}
            对话上下文：{context}
            
            请提供有帮助的、友好的回复。
            """
        }
        
        prompt = prompt_templates.get(intent, prompt_templates["C"])
        
        try:
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=LLM_TEMPERATURE,
                max_tokens=1000
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"模型回复生成失败: {e}")
            return "抱歉，我暂时无法处理您的问题，请稍后再试。"
        
    def rag_retrieval(self, query: str) -> str:
        """RAG检索处理 - 从本地知识库获取产品信息"""
        logger.info(f"执行RAG检索: {query}")
        
        if not self.rag_processor or not self.rag_processor.retriever:
            logger.warning("RAG功能未启用或初始化失败")
            return "产品咨询功能暂不可用，请检查系统配置。"
        
        try:
            # 使用RAG检索相关信息
            retrieved_info = self.rag_processor.search(query)
            
            if not retrieved_info or "未找到相关产品信息" in retrieved_info:
                logger.warning(f"RAG检索未找到相关信息: {query}")
                return "暂时没有找到相关的产品信息。您可以尝试更具体的查询，或联系客服获取帮助。"
            
            logger.info(f"RAG检索成功，获取到 {len(retrieved_info)} 字符的信息")
            return retrieved_info
            
        except Exception as e:
            logger.error(f"RAG检索失败: {e}")
            return "产品信息检索失败，请稍后重试。"
    
    def web_search(self, query: str) -> str:
        """网络搜索处理 - 获取实时信息"""
        logger.info(f"执行网络搜索: {query}")
        
        if not self.web_tools or not self.web_tools.tools:
            logger.warning("Web搜索功能未启用或初始化失败")
            return "实时信息查询功能暂不可用，请检查系统配置。"
        
        try:
            # 分析查询类型，选择合适的工具
            tool_name = self._select_search_tool(query)
            
            # 执行搜索
            search_results = self.web_tools.search(query, tool_name)
            
            if not search_results or "未找到相关信息" in search_results:
                logger.warning(f"网络搜索未找到相关信息: {query}")
                return "暂时无法获取相关的实时信息。您可以尝试调整搜索关键词或稍后重试。"
            
            logger.info(f"网络搜索成功，使用工具: {tool_name}")
            return search_results
            
        except Exception as e:
            logger.error(f"网络搜索失败: {e}")
            return "实时信息获取失败，请稍后重试。"
    
    def _select_search_tool(self, query: str) -> str:
        """根据查询内容选择合适的搜索工具"""
        query_lower = query.lower()
        
        # 检查是否包含天气相关关键词
        weather_keywords = ['天气', '气温', '温度', '预报', '下雨', '下雪', '晴', '阴']
        if any(keyword in query_lower for keyword in weather_keywords):
            return "WeatherSearch"
        
        # 检查是否包含新闻相关关键词
        news_keywords = ['新闻', '最新', '头条', '热点', '时事', '报道']
        if any(keyword in query_lower for keyword in news_keywords):
            return "NewsSearch"
        
        # 检查是否包含价格相关关键词
        price_keywords = ['价格', '价钱', '多少钱', '报价', '行情', '市场价']
        if any(keyword in query_lower for keyword in price_keywords):
            return "PriceSearch"
        
        # 默认使用通用搜索
        return "WebSearch"
    
    def generate_response(self, query: str, context: str, intent: str) -> str:
        """生成最终回复 - 增强版，包含RAG和搜索上下文"""
        prompt_templates = {
            "A": f"""
            你是一个专业的CRM产品客服助手。基于以下检索到的产品信息回答用户的问题：
            
            用户问题：{query}
            
            检索到的产品信息：
            {context}
            
            请注意：
            1. 如果检索到的信息中有直接答案，请优先使用检索到的信息
            2. 如果信息不完整，可以基于常识补充，但要注明哪些是检索信息，哪些是补充信息
            3. 保持回答的专业性和准确性
            4. 如果用户询问产品文档中没有的信息，可以建议用户提供更多细节或联系技术支持
            
            请提供专业、准确的产品咨询回复。
            """,
            "B": f"""
            你是一个精准的实时信息助手。基于以下搜索到的实时信息回答用户的问题：
            
            用户问题：{query}
            搜索到的实时信息：
            {context}
            
            【强制要求】：
            1. 必须提炼核心数据（如天气需包含温度、天气状况；价格需包含具体数值；新闻需包含核心事件）；
            2. 回答要简洁、直接，不要使用"请访问链接"等模糊表述，直接给出具体数值/状态；
            3. 信息格式要结构化（如：深圳今日天气：晴，气温18℃，东风2级）；
            4. 仅使用搜索到的信息回答，不要编造数据；如果信息不足，明确说明核心数据，但不要推荐外部链接。
            
            请提供精准、结构化的实时信息回复，不要冗余内容。
            """,
            "C": f"""
            你是一个友好的CRM客服助手。回复用户问题：
            
            用户问题：{query}
            对话上下文：{context}
            
            请提供有帮助的、友好的回复。
            如果你是第一次与用户交流，请先自我介绍："你好，我是CRM智能助手小云，请问有什么可以帮您？"
            """
        }
        
        prompt = prompt_templates.get(intent, prompt_templates["C"])
        
        try:
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=LLM_TEMPERATURE,
                max_tokens=1000
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"模型回复生成失败: {e}")
            # 提供降级回复
            fallback_responses = {
                "A": "抱歉，我暂时无法查询到详细的产品信息。您可以联系我们的产品专家获取更详细的解答。",
                "B": "抱歉，目前无法获取到最新的实时信息。请您稍后再试或尝试其他查询方式。",
                "C": "抱歉，我暂时无法处理您的问题，请稍后再试。"
            }
            return fallback_responses.get(intent, "抱歉，我暂时无法处理您的问题，请稍后再试。")
    
    # 添加RAG管理方法
    def add_document_to_knowledge_base(self, file_path: str) -> bool:
        """添加文档到知识库"""
        if not self.rag_processor:
            logger.error("RAG处理器未初始化")
            return False
        
        try:
            return self.rag_processor.add_document(file_path)
        except Exception as e:
            logger.error(f"添加文档到知识库失败: {e}")
            return False
    
    def get_rag_status(self) -> dict:
        """获取RAG系统状态"""
        if not self.rag_processor:
            return {"enabled": False, "status": "未初始化"}
        
        try:
            return {
                "enabled": True,
                "status": "运行中",
                "document_path": RAG_DOCUMENTS_PATH,
                "vector_store_path": VECTOR_STORE_PATH
            }
        except:
            return {"enabled": False, "status": "异常"}
    
    def get_web_search_status(self) -> dict:
        """获取Web搜索系统状态"""
        if not self.web_tools:
            return {"enabled": False, "status": "未初始化"}
        
        try:
            return {
                "enabled": True,
                "status": "运行中",
                "tools_count": len(self.web_tools.tools),
                "api_key_configured": bool(TAVILY_API_KEY)
            }
        except:
            return {"enabled": False, "status": "异常"}