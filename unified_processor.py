import http.client
import json
import asyncio
import wave
import io
import os
import uuid
import hmac
import hashlib
import base64
import requests
from urllib import parse
import time
from datetime import datetime, timezone
import aiohttp
import traceback
import math
import struct
import random
import urllib.parse
from typing import Optional, Tuple, AsyncGenerator
import concurrent.futures
import subprocess

class AccessToken:
    """访问令牌管理器，负责阿里云ASR服务的Token获取和刷新"""
    
    def __init__(self, access_key_id: str, access_key_secret: str):
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        self.token = None
        self.expire_time = 0
        self._lock = asyncio.Lock()  # 防止并发刷新token
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    
    async def get_token(self) -> Optional[str]:
        """异步获取访问令牌 - 修复：增加重试+延长超时"""
        current_time = time.time()
        
        # 检查令牌是否有效（提前60秒刷新）
        if self.token and current_time < self.expire_time - 60:
            return self.token
        
        # 使用锁防止并发刷新
        async with self._lock:
            # 再次检查，防止其他协程已经刷新了token
            if self.token and current_time < self.expire_time - 60:
                return self.token
            
            # 生成请求参数
            nonce = str(uuid.uuid4())
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            
            params = {
                "AccessKeyId": self.access_key_id,
                "Action": "CreateToken",
                "Format": "JSON",
                "SignatureMethod": "HMAC-SHA1",
                "SignatureNonce": nonce,
                "SignatureVersion": "1.0",
                "Timestamp": timestamp,
                "Version": "2019-02-28"
            }
            
            # 生成签名
            signature = self._generate_signature(params)
            params["Signature"] = signature
            
            # 请求URL
            url = "https://nls-meta.cn-shanghai.aliyuncs.com/"
            
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    print(f"[DEBUG] 获取ASR Token (尝试 {attempt+1}/{max_retries}): URL={url}")
                    
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, params=params, timeout=30) as response:
                            print(f"[DEBUG] ASR Token响应状态: {response.status}")
                            
                            if response.status == 200:
                                result = await response.json()
                                print(f"[DEBUG] ASR Token原始响应体: {result}")
                                self.token = result["Token"]["Id"]
                                token_expire = result["Token"].get("ExpireTime", 1800)
                                self.expire_time = time.time() + token_expire - 60
                                print(f"[DEBUG] 获取ASR Token成功")
                                return self.token
                            else:
                                response_text = await response.text()
                                print(f"[ERROR] 获取ASR Token失败: HTTP {response.status} - {response_text}")
                except asyncio.TimeoutError:
                    print(f"[ERROR] 获取ASR Token超时 (尝试 {attempt+1}/{max_retries})")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                except Exception as e:
                    print(f"[ERROR] 获取ASR Token异常: {str(e)}")
                    traceback.print_exc()
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
        
        return None
    
    def _generate_signature(self, params: dict) -> str:
        """生成阿里云API签名"""
        sorted_params = sorted(params.items())
        canonicalized_query_string = "&".join(
            [f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(v, safe='')}" 
             for k, v in sorted_params]
        )
        
        string_to_sign = "GET&%2F&" + urllib.parse.quote(canonicalized_query_string, safe="~")
        
        sign_key = f"{self.access_key_secret}&".encode('utf-8')
        h = hmac.new(sign_key, string_to_sign.encode('utf-8'), hashlib.sha1)
        signature = base64.b64encode(h.digest()).decode('utf-8')
        
        return signature


class ASRProvider:
    """阿里云ASR服务提供者"""
    
    def __init__(self, config: dict):
        self.config = config
        self.access_key_id = config.get('access_key_id')
        self.access_key_secret = config.get('access_key_secret')
        self.appkey = config.get('appkey')
        self.token_url = "https://nls-meta.cn-shanghai.aliyuncs.com"
        self.asr_url = "https://nls-gateway.cn-shanghai.aliyuncs.com/stream/v1/asr"
        
        self.token_manager = AccessToken(self.access_key_id, self.access_key_secret)
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        self._validate_config()
    
    def _validate_config(self):
        required_keys = ['access_key_id', 'access_key_secret', 'appkey']
        missing_keys = [key for key in required_keys if not self.config.get(key)]
        if missing_keys:
            raise ValueError(f"ASR配置缺少必要的参数: {', '.join(missing_keys)}")
    
    async def _convert_audio(self, audio_data: bytes) -> bytes:
        try:
            loop = asyncio.get_event_loop()
            converted_audio = await loop.run_in_executor(
                self._executor,
                self._convert_audio_sync,
                audio_data
            )
            return converted_audio
        except Exception as e:
            print(f"[WARNING] 音频转换失败，返回原始数据: {str(e)}")
            return audio_data
    
    def _convert_audio_sync(self, audio_data: bytes) -> bytes:
        try:
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as input_file:
                input_path = input_file.name
                input_file.write(audio_data)
            
            output_path = f"{input_path}_converted.wav"
            try:
                cmd = [
                    'ffmpeg', '-y',
                    '-i', input_path,
                    '-ar', '16000',
                    '-ac', '1',
                    '-acodec', 'pcm_s16le',
                    '-f', 'wav',
                    output_path
                ]
                
                result = subprocess.run(
                    cmd, 
                    capture_output=True, 
                    text=True,
                    timeout=10
                )
                
                if result.returncode != 0:
                    print(f"[WARNING] ffmpeg转换失败: {result.stderr}")
                    return self._simple_audio_conversion(audio_data)
                
                with open(output_path, 'rb') as f:
                    converted_data = f.read()
                
                return converted_data
            finally:
                try:
                    os.unlink(input_path)
                    if os.path.exists(output_path):
                        os.unlink(output_path)
                except:
                    pass
        except subprocess.TimeoutExpired:
            print("[WARNING] 音频转换超时，返回原始数据")
            return audio_data
        except Exception as e:
            print(f"[WARNING] 音频转换异常: {str(e)}")
            return self._simple_audio_conversion(audio_data)
    
    def _simple_audio_conversion(self, audio_data: bytes) -> bytes:
        try:
            with io.BytesIO(audio_data) as bio:
                with wave.open(bio, 'rb') as wav:
                    params = wav.getparams()
                    frames = wav.readframes(params.nframes)
                    
                    if (params.framerate == 16000 and 
                        params.nchannels == 1 and 
                        params.sampwidth == 2):
                        return audio_data
                    
                    output = io.BytesIO()
                    with wave.open(output, 'wb') as out_wav:
                        out_wav.setnchannels(1)
                        out_wav.setsampwidth(2)
                        out_wav.setframerate(16000)
                        out_wav.writeframes(frames)
                    
                    return output.getvalue()
        except:
            print("[WARNING] 无法解析音频格式，返回原始数据")
            return audio_data
    
    def _validate_audio_format(self, audio_data: bytes) -> bool:
        try:
            with io.BytesIO(audio_data) as bio:
                with wave.open(bio, 'rb') as wav:
                    params = wav.getparams()
                    if params.framerate != 16000:
                        print(f"[DEBUG] 音频采样率不匹配: {params.framerate}Hz (需要16000Hz)")
                        return False
                    if params.nchannels != 1:
                        print(f"[DEBUG] 音频通道数不匹配: {params.nchannels} (需要1)")
                        return False
                    if params.sampwidth != 2:
                        print(f"[DEBUG] 音频位深不匹配: {params.sampwidth}字节 (需要2字节)")
                        return False
                    
                    print(f"[DEBUG] 音频格式验证通过: {params.framerate}Hz, {params.nchannels}通道, {params.sampwidth}字节/样本")
                    return True
        except Exception as e:
            print(f"[DEBUG] 无法验证音频格式: {str(e)}")
            return False
    
    async def speech_to_text(self, audio_data: bytes, session_id: str) -> Tuple[Optional[str], Optional[str]]:
        token = await self.token_manager.get_token()
        if not token:
            print("[ERROR] 无法获取有效的ASR Token")
            return None, "获取ASR Token失败"
        
        prepared_audio = audio_data
        
        if not self._validate_audio_format(audio_data):
            print("[DEBUG] 音频格式不符合要求，进行转换...")
            prepared_audio = await self._convert_audio(audio_data)
        
        params = {
            "appkey": self.appkey,
            "token": token,
            "format": "pcm",
            "sample_rate": 16000,
            "channels": 1,
            "bits": 16,
            "enable_punctuation_prediction": "true",
            "enable_inverse_text_normalization": "true"
        }
        
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        url = f"{self.asr_url}?{query_string}"
        
        headers = {
            "Content-Type": "application/octet-stream",
            "X-NLS-Token": token,
            "X-NLS-Session-Id": session_id,
            "User-Agent": "ASR-Client/1.0"
        }
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"[DEBUG] 发送ASR请求 (尝试 {attempt+1}/{max_retries}): URL={url}, 音频长度={len(prepared_audio)}字节")
                
                async with aiohttp.ClientSession() as session:
                    timeout = aiohttp.ClientTimeout(total=30)
                    async with session.post(url, data=prepared_audio, headers=headers, timeout=timeout) as response:
                        raw_response = await response.text()
                        
                        if response.status == 200:
                            result = await response.json()
                            if result.get("status") == 20000000:
                                if result.get("result"):
                                    recognized_text = result["result"]
                                    print(f"[DEBUG] ASR识别成功: {recognized_text}")
                                    return recognized_text, None
                                else:
                                    print(f"[WARNING] ASR识别返回空结果，完整响应: {result}")
                                    return "", "ASR返回空结果"
                            else:
                                error_msg = (
                                    f"ASR识别失败: {result.get('message', '未知错误')} "
                                    f"(状态码: {result.get('status')})"
                                )
                                print(f"[ERROR] {error_msg}")
                                if result.get("status") == 40000004:
                                    print("[DEBUG] Token无效，尝试刷新...")
                                    self.token_manager.token = None
                                    token = await self.token_manager.get_token()
                                    if token and attempt < max_retries - 1:
                                        await asyncio.sleep(1)
                                        continue
                                return None, error_msg
                        else:
                            error_msg = f"ASR请求失败: HTTP {response.status} - {raw_response}"
                            print(f"[ERROR] {error_msg}")
                            if response.status == 408 or response.status >= 500:
                                if attempt < max_retries - 1:
                                    await asyncio.sleep(2 ** attempt)
                                    continue
                            return None, error_msg
            except asyncio.TimeoutError:
                error_msg = f"ASR请求超时 (尝试 {attempt+1}/{max_retries})"
                print(f"[ERROR] {error_msg}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return None, error_msg
            except Exception as e:
                error_msg = f"ASR请求异常: {str(e)}"
                print(f"[ERROR] {error_msg}")
                traceback.print_exc()
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return None, error_msg
        
        return None, "ASR请求失败，达到最大重试次数"
    
    async def process_audio_stream(self, audio_chunks: list, session_id: str) -> Tuple[Optional[str], Optional[str]]:
        if not audio_chunks:
            print("[WARNING] 音频数据为空")
            return "", "音频数据为空"
        
        audio_data = b"".join(audio_chunks)
        return await self.speech_to_text(audio_data, session_id)


class AliBLProvider:
    def __init__(self, config):
        self.access_key_id = config.get('access_key_id')
        self.access_key_secret = config.get('access_key_secret')
        self.api_key = config.get('api_key')
        self.api_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
        self.model = config.get('model', 'qwen-turbo')
        self._validate_config()
    
    def _validate_config(self):
        if not self.api_key:
            raise ValueError("LLM配置缺少api_key")
    
    async def generate_response(self, messages):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        
        data = {
            "model": self.model,
            "input": {
                "messages": messages["messages"]
            },
            "parameters": {
                "result_format": "text"
            }
        }
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"[DEBUG] 发送LLM请求 (尝试 {attempt+1}/{max_retries}): URL={self.api_url}, 消息长度={len(str(data))}字符")
                
                async with aiohttp.ClientSession() as session:
                    timeout = aiohttp.ClientTimeout(total=60)
                    async with session.post(url=self.api_url, json=data, headers=headers, timeout=timeout) as response:
                        response_text = await response.text()
                        print(f"[DEBUG] LLM响应: HTTP {response.status}, 响应长度={len(response_text)}字符")
                        
                        if response.status == 200:
                            result = await response.json()
                            return result["output"]["text"]
                        else:
                            error = f"LLM请求失败: HTTP {response.status} - {response_text[:200]}..."
                            print(f"[ERROR] {error}")
                            if response.status == 429 or response.status >= 500:
                                if attempt < max_retries - 1:
                                    wait_time = 2 ** attempt
                                    print(f"[DEBUG] 等待{wait_time}秒后重试...")
                                    await asyncio.sleep(wait_time)
                                    continue
                            return error
            except asyncio.TimeoutError:
                error = f"LLM请求超时 (尝试 {attempt+1}/{max_retries})"
                print(f"[ERROR] {error}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return error
            except Exception as e:
                error = f"LLM请求异常: {str(e)}"
                print(f"[ERROR] {error}")
                traceback.print_exc()
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return error
        
        return "LLM请求失败，达到最大重试次数"

    async def stream_response(self, messages) -> AsyncGenerator[str, None]:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "X-DashScope-SSE": "enable"
        }
        
        data = {
            "model": self.model,
            "input": {
                "messages": messages["messages"]
            },
            "parameters": {
                "result_format": "text",
                "stream": True,
                "incremental_output": True
            }
        }

        try:
            print(f"[DEBUG] 发送流式LLM请求: URL={self.api_url}")
            async with aiohttp.ClientSession() as session:
                timeout = aiohttp.ClientTimeout(total=120)
                async with session.post(self.api_url, json=data, headers=headers, timeout=timeout) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        print(f"[ERROR] 流式LLM请求失败: HTTP {response.status} - {error_text}")
                        return
                    
                    async for line in response.content:
                        if not line:
                            continue
                        try:
                            line_str = line.decode('utf-8').strip()
                            if line_str.startswith('data:'):
                                chunk = line_str[5:].strip()
                                if chunk:
                                    chunk_data = json.loads(chunk)
                                    if "output" in chunk_data and "text" in chunk_data["output"]:
                                        yield chunk_data["output"]["text"]
                        except Exception as e:
                            print(f"[WARNING] 流式LLM解析异常: {str(e)} - 原始数据: {line}")
        except Exception as e:
            print(f"[ERROR] 流式LLM请求失败: {str(e)}")
            traceback.print_exc()
    
class TTSProvider:
    def __init__(self, config):
        self.access_key_id = config.get('access_key_id')
        self.access_key_secret = config.get('access_key_secret')
        self.appkey = config.get('appkey')
        self.token_url = "https://nls-meta.cn-shanghai.aliyuncs.com"
        self.tts_url = "https://nls-gateway.cn-shanghai.aliyuncs.com/stream/v1/tts"
        self.region_id = "cn-shanghai"
        self.product = "nls-cloud-meta"
        self.voice = config.get('voice', 'xiaoyun')
        self.token = None
        self.token_expire = 0
        self._lock = asyncio.Lock()
        self._validate_config()
    
    def _validate_config(self):
        required_keys = ['access_key_id', 'access_key_secret', 'appkey']
        missing_keys = [key for key in required_keys if not getattr(self, key)]
        if missing_keys:
            raise ValueError(f"TTS配置缺少必要的参数: {', '.join(missing_keys)}")
    
    async def get_tts_token(self):
        """修复核心错误：时间戳格式 %Y-%m-d → %Y-%m-%d"""
        if self.token and time.time() < self.token_expire:
            return self.token
        
        async with self._lock:
            if self.token and time.time() < self.token_expire:
                return self.token
                
            
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            nonce = str(uuid.uuid4())
            
            params = {
                "AccessKeyId": self.access_key_id,
                "Action": "CreateToken",
                "Product": self.product,
                "RegionId": self.region_id,
                "Format": "JSON",
                "SignatureMethod": "HMAC-SHA1",
                "SignatureVersion": "1.0",
                "SignatureNonce": nonce,
                "Timestamp": timestamp,
                "Version": "2019-02-28"
            }
            
            sorted_params = sorted(params.items())
            canonicalized_query_string = "&".join(
                [f"{parse.quote(k, safe='')}={parse.quote(v, safe='')}" for k, v in sorted_params]
            )
            
            string_to_sign = "GET&%2F&" + parse.quote(canonicalized_query_string, safe="")
            
            key = self.access_key_secret + "&"
            h = hmac.new(key.encode('utf-8'), string_to_sign.encode('utf-8'), hashlib.sha1)
            signature = base64.b64encode(h.digest()).decode('utf-8')
            
            params["Signature"] = signature
            
            try:
                print(f"[DEBUG] 获取TTS Token: URL={self.token_url}")
                async with aiohttp.ClientSession() as session:
                    timeout = aiohttp.ClientTimeout(total=30)
                    async with session.get(self.token_url, params=params, timeout=timeout) as response:
                        if response.status == 200:
                            result = await response.json()
                            self.token = result["Token"]["Id"]
                            self.token_expire = time.time() + 1800 - 60
                            print(f"[DEBUG] 获取TTS Token成功")
                            return self.token
                        else:
                            response_text = await response.text()
                            print(f"[ERROR] 获取TTS Token失败: HTTP {response.status} - {response_text[:200]}...")
            except asyncio.TimeoutError:
                print(f"[ERROR] 获取TTS Token超时")
            except Exception as e:
                print(f"[ERROR] 获取TTS Token异常: {str(e)}")
                traceback.print_exc()
        
        return None

    async def text_to_speech(self, text, session_id):
        if not text or len(text.strip()) == 0:
            print("[WARNING] TTS输入文本为空")
            return b""
        
        token = await self.get_tts_token()
        if not token:
            print("[ERROR] 无法获取有效的TTS Token")
            return b""
        
        url = f"{self.tts_url}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "appkey": self.appkey,
            "token": token,
            "text": text,
            "format": "wav",
            "voice": self.voice,
            "session_id": session_id
        }
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"[DEBUG] 发送TTS请求 (尝试 {attempt+1}/{max_retries}): URL={url}, 文本长度={len(text)}字符")
                
                async with aiohttp.ClientSession() as session:
                    timeout = aiohttp.ClientTimeout(total=30)
                    async with session.post(url, json=payload, headers=headers, timeout=timeout) as response:
                        if response.status == 200:
                            audio_data = await response.read()
                            print(f"[DEBUG] TTS合成成功, 音频长度: {len(audio_data)}字节")
                            return audio_data
                        else:
                            error_text = await response.text()
                            error_msg = f"TTS请求失败: HTTP {response.status} - {error_text[:200]}..."
                            print(f"[ERROR] {error_msg}")
                            if "token" in error_text.lower() and attempt < max_retries - 1:
                                print("[DEBUG] Token可能失效，尝试刷新...")
                                self.token = None
                                await asyncio.sleep(1)
                                continue
                            return b""
            except asyncio.TimeoutError:
                print(f"[ERROR] TTS请求超时 (尝试 {attempt+1}/{max_retries})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return b""
            except Exception as e:
                error_msg = f"TTS请求异常: {str(e)}"
                print(f"[ERROR] {error_msg}")
                traceback.print_exc()
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return b""
        
        return b""

    async def stream_speech(self, text, session_id) -> AsyncGenerator[bytes, None]:
        if not text or len(text.strip()) == 0:
            print("[WARNING] 流式TTS输入文本为空")
            return
            
        token = await self.get_tts_token()
        if not token:
            print("[ERROR] 无法获取有效的TTS Token")
            return
        
        url = f"{self.tts_url}?enable_subtitle=true"
        headers = {"Content-Type": "application/json"}
        payload = {
            "appkey": self.appkey,
            "token": token,
            "text": text,
            "format": "pcm",
            "sample_rate": 16000,
            "voice": self.voice,
            "session_id": session_id,
            "stream": True
        }
        
        try:
            print(f"[DEBUG] 发送流式TTS请求: URL={url}, 文本长度={len(text)}字符")
            async with aiohttp.ClientSession() as session:
                timeout = aiohttp.ClientTimeout(total=60)
                async with session.post(url, json=payload, headers=headers, timeout=timeout) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        print(f"[ERROR] 流式TTS请求失败: HTTP {response.status} - {error_text[:200]}...")
                        return
                    
                    async for chunk in response.content.iter_any():
                        if chunk:
                            yield chunk
        except Exception as e:
            print(f"[ERROR] 流式TTS请求异常: {str(e)}")
            traceback.print_exc()


class AliyunProcessor:
    def __init__(self, config):
        asr_config = config.get('asr', {})
        llm_config = config.get('llm', {})
        tts_config = config.get('tts', {})
        
        self._validate_config(asr_config, llm_config, tts_config)
        
        self.asr = ASRProvider(asr_config)
        self.llm = AliBLProvider(llm_config)
        self.tts = TTSProvider(tts_config)
        
        self.stats = {
            "asr_success": 0,
            "asr_failed": 0,
            "llm_success": 0,
            "llm_failed": 0,
            "tts_success": 0,
            "tts_failed": 0,
            "total_processed": 0
        }
    
    def _validate_config(self, asr_config, llm_config, tts_config):
        if not asr_config.get('access_key_id'):
            print("[WARNING] ASR配置缺少access_key_id")
        if not llm_config.get('api_key'):
            print("[WARNING] LLM配置缺少api_key")
        if not tts_config.get('access_key_id'):
            print("[WARNING] TTS配置缺少access_key_id")
    
    async def process(self, audio_data, chat_history=None):
        
        try:
            session_id = f"session_{uuid.uuid4().hex[:8]}"
            print(f"[INFO] 开始处理流程, Session ID: {session_id}")
            self.stats["total_processed"] += 1
            
            text, error = await self.asr.speech_to_text(audio_data, session_id)
            if error or not text:
                error_msg = f"ASR失败: {error}" if error else "ASR返回空结果"
                print(f"[ERROR] {error_msg}")
                self.stats["asr_failed"] += 1
                return {"error": error_msg}
            
            self.stats["asr_success"] += 1
            print(f"[DEBUG] ASR识别成功: '{text[:100]}...'" if len(text) > 100 else f"[DEBUG] ASR识别成功: '{text}'")
            
            print(f"[DEBUG] 调用大模型...")
            # 添加系统Prompt
            messages_for_llm = [
                {
                    "role": "system",
                    "content": """你是名为小云的智能语音助手，你的核心设定如下：
1. 你的名字是小云，是一个友好的智能语音助手；
2. 当用户向你打招呼（比如“你好”“哈喽”“我叫XX”）时，必须先回应“你好，我是小云，一个智能语音助手，请问有什么可以帮到您？”；
3. 回答要简洁、友好，符合智能助手的身份。"""
                }
            ]
            #历史对话上下文
            if chat_history:
                valid_history = [
                    msg for msg in chat_history 
                    if msg.get("role") in ["user", "assistant"] and msg.get("content")
                ]
                messages_for_llm.extend(valid_history)
                print(f"[DEBUG] 加载历史对话: {len(valid_history)} 条有效消息")
            
            messages_for_llm.append({"role": "user", "content": text})
            
            llm_response = await self.llm.generate_response({
                "messages": messages_for_llm
            })
            
            if isinstance(llm_response, str) and (
                llm_response.startswith("LLM请求失败") or 
                llm_response.startswith("LLM请求异常") or
                llm_response.startswith("LLM请求超时") or
                "失败" in llm_response[:100] or
                "错误" in llm_response[:100]
            ):
                error_msg = f"LLM处理失败: {llm_response[:200]}..."
                print(f"[ERROR] {error_msg}")
                self.stats["llm_failed"] += 1
                return {"error": error_msg}
            
            self.stats["llm_success"] += 1
            print(f"[DEBUG] LLM回复成功: '{llm_response[:100]}...'" if len(llm_response) > 100 else f"[DEBUG] LLM回复成功: '{llm_response}'")
            
            print(f"[DEBUG] 开始TTS合成...")
            tts_audio = await self.tts.text_to_speech(llm_response, session_id)
            if not tts_audio or len(tts_audio) < 100:
                error_msg = f"TTS合成失败，音频长度: {len(tts_audio) if tts_audio else 0}字节"
                print(f"[ERROR] {error_msg}")
                self.stats["tts_failed"] += 1
                return {"error": error_msg}
            
            self.stats["tts_success"] += 1
            print(f"[INFO] 处理流程完成")
            
            return {
                "text": text,
                "response": llm_response,
                "audio": tts_audio,
                "session_id": session_id
            }
        except Exception as e:
            error_msg = f"处理流程异常: {str(e)}"
            print(f"[ERROR] {error_msg}")
            traceback.print_exc()
            return {"error": error_msg}
    
    async def process_streaming(self, audio_chunks, session_id=None):
        if not session_id:
            session_id = f"stream_{uuid.uuid4().hex[:8]}"
        
        print(f"[INFO] 开始流式处理流程, Session ID: {session_id}")
        
        text, error = await self.asr.process_audio_stream(audio_chunks, session_id)
        if error or not text:
            return {"error": f"ASR失败: {error}" if error else "ASR返回空结果"}
        
        async def llm_stream():
            # 流式调用添加系统Prompt
            messages = {
                "messages": [
                    {
                        "role": "system",
                        "content": "你是名为小云的智能语音助手，友好且专业，用户打招呼时要回应'你好，我是小云，一个智能语音助手，请问有什么可以帮到您？'"
                    },
                    {"role": "user", "content": text}
                ]
            }
            async for chunk in self.llm.stream_response(messages):
                yield {"type": "llm", "data": chunk}
        
        async def tts_stream(llm_text):
            async for audio_chunk in self.tts.stream_speech(llm_text, session_id):
                yield {"type": "tts", "data": audio_chunk}
        
        return {
            "text": text,
            "llm_stream": llm_stream(),
            "tts_stream": tts_stream
        }
    
    def get_stats(self):
        return self.stats.copy()
    
    async def close(self):
        if hasattr(self.asr, '_executor'):
            self.asr._executor.shutdown(wait=False)
        
        print("[INFO] 处理器资源已清理")


def create_test_audio(duration=3, sample_rate=16000):
    with io.BytesIO() as wav_io:
        with wave.open(wav_io, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            
            frames = b''
            amplitude = 32767 * 0.3
            for i in range(int(sample_rate * duration)):
                base_freq = 250
                formant_freq = 1000
                t = i / sample_rate
                dynamic_freq = base_freq + 50 * math.sin(2 * math.pi * 5 * t)
                
                sample_val = amplitude * (
                    0.5 * (math.sin(2 * math.pi * dynamic_freq * t) + 0.5 * math.sin(4 * math.pi * dynamic_freq * t)) +
                    0.3 * math.sin(2 * math.pi * formant_freq * t) +
                    0.03 * random.uniform(-1, 1))
                
                sample_val = max(-32768, min(32767, sample_val))
                sample = int(sample_val)
                frames += struct.pack('<h', sample)
                
            wav_file.writeframes(frames)
        return wav_io.getvalue()


def check_dependencies():
    missing = []
    try:
        import aiohttp
    except ImportError:
        missing.append("aiohttp")
    
    try:
        import wave
    except ImportError:
        missing.append("wave (Python内置，不应缺失)")
    
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                               capture_output=True, 
                               text=True,
                               timeout=5)
        if result.returncode != 0:
            print("[WARNING] ffmpeg命令执行失败")
    except FileNotFoundError:
        print("[WARNING] ffmpeg未安装，音频转换功能可能受限")
    except subprocess.TimeoutExpired:
        print("[WARNING] ffmpeg检查超时")
    
    if missing:
        print(f"[ERROR] 缺少依赖: {', '.join(missing)}")
        print("请安装: pip install " + " ".join(missing))
        return False
    
    print("[INFO] 所有依赖检查通过")
    return True


SAMPLE_CONFIG = {
    "asr": {
        "sample_rate": 16000,
        "channels": 1,
        "bits": 16,
        "access_key_id": "your_access_key_id",
        "access_key_secret": "your_access_key_secret",
        "appkey": "your_appkey"
    },
    "tts": {
        "access_key_id": "your_access_key_id",
        "access_key_secret": "your_access_key_secret",
        "appkey": "your_appkey",
        "voice": "xiaoyun"
    },
    "llm": {
        "access_key_id": "your_access_key_id",
        "access_key_secret": "your_access_key_secret",
        "api_key": "your_api_key",
        "model": "qwen-turbo"
    }
}


async def main():
    if not check_dependencies():
        return
    
    processor = None
    try:
        processor = AliyunProcessor(SAMPLE_CONFIG)
        test_audio = create_test_audio(duration=2)
        print(f"[INFO] 测试音频创建完成，长度: {len(test_audio)}字节")
        
        result = await processor.process(test_audio)
        
        print("\n=== 处理结果 ===")
        if "error" in result:
            print(f"处理失败: {result['error']}")
        else:
            print(f"识别文本: {result.get('text')}")
            print(f"模型回复: {result.get('response')[:200]}...")
            print(f"音频长度: {len(result.get('audio', b''))} 字节")
            print(f"Session ID: {result.get('session_id')}")
        
        print("\n=== 性能统计 ===")
        stats = processor.get_stats()
        for key, value in stats.items():
            print(f"{key}: {value}")
            
    except Exception as e:
        print(f"[ERROR] 主程序异常: {str(e)}")
        traceback.print_exc()
    finally:
        if processor:
            await processor.close()

class UnifiedProcessorAPI:
    def __init__(self, config: dict):
        self.config = config
        self.processor = None
        
    def initialize(self):
        try:
            self.processor = AliyunProcessor(self.config)
            return True, "初始化成功"
        except Exception as e:
            return False, f"初始化失败: {str(e)}"
    
    async def process_audio(self, audio_data: bytes, session_id: str = None):
        if not self.processor:
            success, message = self.initialize()
            if not success:
                return {"error": message}
        
        try:
            if not session_id:
                session_id = f"gradio_{uuid.uuid4().hex[:8]}"
            
            result = await self.processor.process(audio_data)
            return result
        except Exception as e:
            return {"error": f"处理失败: {str(e)}"}
    
    def get_capabilities(self):
        return {
            "asr": "aliyun" if self.config.get("asr", {}).get("access_key_id") else None,
            "llm": "qwen" if self.config.get("llm", {}).get("api_key") else None,
            "tts": "aliyun" if self.config.get("tts", {}).get("access_key_id") else None,
            "streaming": True,
            "status": "ready" if self.processor else "not_initialized"
        }

class HTTPVoiceHandler:
    def __init__(self, processor_api: UnifiedProcessorAPI):
        self.processor_api = processor_api
    
    async def handle_request(self, request_data: dict, audio_data: bytes = None):
        try:
            username = request_data.get("username", "anonymous")
            session_id = request_data.get("session_id", f"http_{uuid.uuid4().hex[:8]}")
            
            if audio_data is None:
                return {
                    "success": False,
                    "error": "没有提供音频数据"
                }
            
            result = await self.processor_api.process_audio(audio_data, session_id)
            
            if "error" in result:
                return {
                    "success": False,
                    "error": result["error"]
                }
            
            return {
                "success": True,
                "text": result.get("text", ""),
                "response": result.get("response", ""),
                "audio": result.get("audio", b""),
                "session_id": session_id,
                "timestamp": int(time.time())
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"处理请求失败: {str(e)}"
            }

__all__ = [
    "AliyunProcessor",
    "UnifiedProcessorAPI",
    "HTTPVoiceHandler",
    "create_test_audio"
]

if __name__ == "__main__":
    asyncio.run(main())