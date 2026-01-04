import logging
import openai
from config import OPENAI_API_KEY, SILICONFLOW_API_BASE, LLM_MODEL, LLM_TEMPERATURE
from database import UserManager
from intent_recognizer import IntentRecognizer
from voice_processor import VoiceProcessor

logger = logging.getLogger(__name__)

# 配置OpenAI客户端
client = openai.OpenAI(
    api_key=OPENAI_API_KEY,
    base_url=SILICONFLOW_API_BASE
)

class ResponseEngine:
    def __init__(self):
        self.user_manager = UserManager()
        self.intent_recognizer = IntentRecognizer()
        self.voice_processor = VoiceProcessor()
    
    def process_query(self, phone_number: str, query: str, channel: str = 'text') -> dict:
        """处理用户查询，支持文本和语音渠道"""
        # 1. 用户识别和管理
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
        
        # 2. 意图识别
        intent_code = self.intent_recognizer.detect_intent(query)
        logger.info(f"用户{phone_number} 意图识别: {intent_code} (渠道: {channel})")
        
        # 3. 根据意图处理查询
        context = ""
        if intent_code == "A":
            context = self.rag_retrieval(query)
        elif intent_code == "B":
            context = self.web_search(query)
        else:
            context = "对话历史: " + str(chat_history[-5:]) if chat_history else "无历史对话"
        
        # 4. 生成回复
        response = self.generate_response(query, context, intent_code)
        
        # 5. 记录助手回复
        self.user_manager.add_conversation(
            user_id, channel, "assistant", response, intent_code
        )
        
        # 6. 准备返回结果
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
    
    def rag_retrieval(self, query: str) -> str:
        """RAG检索处理"""
        # 这里实现您的RAG检索逻辑
        # 示例：从向量数据库检索相关信息
        try:
            # 模拟RAG检索过程
            retrieved_info = f"基于知识库检索到的相关信息：用户询问了'{query}'的相关产品信息"
            return retrieved_info
        except Exception as e:
            logger.error(f"RAG检索失败: {e}")
            return "暂时无法获取产品详细信息"
    
    def web_search(self, query: str) -> str:
        """网络搜索处理"""
        # 这里实现您的网络搜索逻辑
        try:
            # 模拟网络搜索过程
            search_results = f"网络搜索到的实时信息：关于'{query}'的最新资讯"
            return search_results
        except Exception as e:
            logger.error(f"网络搜索失败: {e}")
            return "暂时无法获取实时信息"
    
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