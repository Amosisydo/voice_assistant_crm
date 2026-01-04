import asyncio
import logging
import uuid
from typing import Dict, Any, Optional, Tuple
from unified_processor import AliyunProcessor

logger = logging.getLogger(__name__)

class VoiceProcessor:
    """语音处理器，封装阿里云语音服务"""
    
    def __init__(self):
        self.processor = None
        self._initialize_processor()
    
    def _initialize_processor(self):
        """初始化语音处理器"""
        try:
            from config import (
                ASR_ACCESS_KEY_ID,
                ASR_ACCESS_KEY_SECRET,
                ASR_APPKEY,
                TTS_ACCESS_KEY_ID,
                TTS_ACCESS_KEY_SECRET,
                TTS_APPKEY,
                TTS_VOICE,
                ALIYUN_LLM_API_KEY,
                ALIYUN_LLM_MODEL
            )
            
            config = {
                "asr": {
                    "access_key_id": ASR_ACCESS_KEY_ID,
                    "access_key_secret": ASR_ACCESS_KEY_SECRET,
                    "appkey": ASR_APPKEY
                },
                "llm": {
                    "api_key": ALIYUN_LLM_API_KEY,
                    "model": ALIYUN_LLM_MODEL
                },
                "tts": {
                    "access_key_id": TTS_ACCESS_KEY_ID,
                    "access_key_secret": TTS_ACCESS_KEY_SECRET,
                    "appkey": TTS_APPKEY,
                    "voice": TTS_VOICE
                }
            }
            
            self.processor = AliyunProcessor(config)
            logger.info("语音处理器初始化成功")
            return True
        except Exception as e:
            logger.error(f"语音处理器初始化失败: {e}")
            self.processor = None
            return False
    
    async def speech_to_text(self, audio_data: bytes) -> Tuple[Optional[str], Optional[str]]:
        """语音转文本"""
        if not self.processor:
            return None, "语音处理器未初始化"
        
        try:
            session_id = f"crm_{uuid.uuid4().hex[:8]}"
            text, error = await self.processor.asr.speech_to_text(audio_data, session_id)
            return text, error
        except Exception as e:
            logger.error(f"语音识别失败: {e}")
            return None, str(e)
    
    async def text_to_speech(self, text: str) -> Tuple[Optional[bytes], Optional[str]]:
        """文本转语音"""
        if not self.processor:
            return None, "语音处理器未初始化"
        
        try:
            session_id = f"crm_{uuid.uuid4().hex[:8]}"
            audio_data = await self.processor.tts.text_to_speech(text, session_id)
            if not audio_data or len(audio_data) < 100:
                return None, "语音合成失败"
            return audio_data, None
        except Exception as e:
            logger.error(f"语音合成失败: {e}")
            return None, str(e)
    
    async def process_voice_query(self, audio_data: bytes, phone_number: str) -> Dict[str, Any]:
        """处理完整的语音查询"""
        # 语音转文本
        text, error = await self.speech_to_text(audio_data)
        if error or not text:
            return {
                "error": f"语音识别失败: {error}",
                "recognized_text": "",
                "response": "抱歉，我没听清楚，请再说一遍"
            }
        
        # 使用CRM的响应引擎处理文本
        from response_engine import ResponseEngine
        engine = ResponseEngine()
        
        # 设置语音通道
        result = engine.process_query(phone_number, text, channel='voice')
        
        # 文本转语音
        if result.get("response"):
            audio_response, tts_error = await self.text_to_speech(result["response"])
            if tts_error:
                logger.warning(f"语音合成失败，使用文本回复: {tts_error}")
                result["audio_response"] = None
            else:
                result["audio_response"] = audio_response
        
        result["recognized_text"] = text
        result["channel"] = 'voice'
        
        return result