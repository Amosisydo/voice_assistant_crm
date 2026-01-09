import os
from dotenv import load_dotenv

load_dotenv()

# 数据库配置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, 'crm_system.db')

# LLM配置
# BAIDU_API_KEY = os.getenv("baidu_api_key")
# BAIDU_LLM_MODEL = os.getenv("BAIDU_LLM_MODEL", "ERNIE-4.0-8K")
# BAIDU_EMBEDDING_MODEL = os.getenv("BAIDU_EMBEDDING_MODEL", "Embedding-V1")
# BAIDU_API_BASE_URL = os.getenv("baidu_api_base_url", "https://qianfan.baidubce.com/v2/chat/completions")


# # 使用本地嵌入模型
# EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"
# EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "")
EMBEDDING_MODEL = "BAAI/bge-m3"
EMBEDDING_MODEL_DEVICE = "cpu"  # 使用CPU即可，如需GPU加速可改为 "cuda"

LLM_MODEL = os.getenv("MODEL_NAME", "deepseek-ai/DeepSeek-V2.5")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", 0.3))
API_BASE = os.getenv("SILICONFLOW_API_BASE", "https://api.siliconflow.cn/v1")
OPENAI_API_KEY = os.getenv("openai_api_key")


# 阿里云语音配置
ASR_ACCESS_KEY_ID = os.getenv("ASR_ACCESS_KEY_ID")
ASR_ACCESS_KEY_SECRET = os.getenv("ASR_ACCESS_KEY_SECRET")
ASR_APPKEY = os.getenv("ASR_APPKEY")
TTS_ACCESS_KEY_ID = os.getenv("TTS_ACCESS_KEY_ID")
TTS_ACCESS_KEY_SECRET = os.getenv("TTS_ACCESS_KEY_SECRET")
TTS_APPKEY = os.getenv("TTS_APPKEY")
TTS_VOICE = os.getenv("TTS_VOICE", "xiaoyun")
ALIYUN_LLM_API_KEY = os.getenv("LLM_API_KEY")
ALIYUN_LLM_MODEL = os.getenv("LLM_MODEL", "qwen-turbo")

# 服务器配置
HTTP_PORT = int(os.getenv("SERVER_HTTP_PORT", "8003"))
GRADIO_PORT = int(os.getenv("GRADIO_PORT", "7860"))
FASTAPI_PORT = int(os.getenv("FASTAPI_PORT", "8000"))

# RAG配置
RAG_DOCUMENTS_PATH = os.path.join(BASE_DIR, 'data_documents')
VECTOR_STORE_PATH = os.path.join(BASE_DIR, 'vector_store')


# 网络搜索工具配置
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
MAX_SEARCH_RESULTS = int(os.getenv("MAX_SEARCH_RESULTS", 3))

# 工具启用开关
ENABLE_RAG = os.getenv("ENABLE_RAG", "True").lower() == "true"
ENABLE_WEB_SEARCH = os.getenv("ENABLE_WEB_SEARCH", "True").lower() == "true"