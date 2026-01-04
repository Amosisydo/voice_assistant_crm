import os
from dotenv import load_dotenv

load_dotenv()

# 数据库配置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, 'crm_system.db')

# LLM配置
LLM_MODEL = os.getenv("MODEL_NAME", "deepseek-ai/DeepSeek-V2.5")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", 0.3))
SILICONFLOW_API_BASE = os.getenv("SILICONFLOW_API_BASE", "https://api.siliconflow.cn/v1")
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