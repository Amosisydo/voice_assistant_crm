import logging
import openai
from config import OPENAI_API_KEY, SILICONFLOW_API_BASE, LLM_MODEL

logger = logging.getLogger(__name__)

# 配置OpenAI客户端（使用SiliconFlow）
client = openai.OpenAI(
    api_key=OPENAI_API_KEY,
    base_url=SILICONFLOW_API_BASE
)

class IntentRecognizer:
    def __init__(self):
        self.intent_categories = {
            "A": "产品咨询-RAG检索",
            "B": "实时信息-网络搜索", 
            "C": "常规问答-模型回复"
        }
    
    def detect_intent(self, query: str) -> str:
        """识别用户意图"""
        # 使用模型进行意图分类
        prompt = f"""
        请分析以下用户问题的意图，并返回对应的分类代码（A、B或C）：
        
        A - 产品咨询：涉及具体产品信息、规格、价格等需要检索知识库的问题
        B - 实时信息：需要最新市场信息、新闻、天气等实时数据的问题  
        C - 常规问答：一般性咨询、客服问题、使用指导等
        
        用户问题：{query}
        
        只需返回单个字母A、B或C，不要其他内容。
        """
        
        try:
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=10
            )
            
            intent_code = response.choices[0].message.content.strip().upper()
            
            # 验证返回结果
            if intent_code in ['A', 'B', 'C']:
                return intent_code
            else:
                # 默认返回C
                return 'C'
                
        except Exception as e:
            logger.error(f"意图识别失败: {e}")
            return 'C'  # 失败时默认使用常规回复
    
    def get_intent_description(self, intent_code: str) -> str:
        """获取意图描述"""
        return self.intent_categories.get(intent_code, "未知意图")