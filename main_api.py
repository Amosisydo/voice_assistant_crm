import uvicorn
import base64
import logging
from fastapi import FastAPI, Request, UploadFile, File, Body, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from datetime import datetime
import asyncio

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 导入项目模块
from config import DATABASE_PATH, LLM_MODEL, HTTP_PORT, GRADIO_PORT,ASR_ACCESS_KEY_ID, TTS_ACCESS_KEY_ID, OPENAI_API_KEY, FASTAPI_PORT
from database import init_database
from response_engine import ResponseEngine

# 初始化数据库
init_database()

# 初始化FastAPI
app = FastAPI(
    title="CRM智能语音客服系统",
    description="整合文本聊天和语音交互的CRM客服系统",
    version="1.0.0"
)

# 配置跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化响应引擎
engine = ResponseEngine()

# 标准化响应
def standard_response(success: bool, data: dict = None, message: str = ""):
    return JSONResponse({
        "success": success,
        "message": message,
        "data": data,
        "timestamp": datetime.now().isoformat()
    })

# ==================== API接口 ====================
@app.get("/health", summary="健康检查")
async def health_check():
    """系统健康检查"""
    voice_caps = engine.get_voice_capabilities()
    return standard_response(
        success=True,
        data={
            "status": "healthy",
            "crm_model": LLM_MODEL,
            "voice_capabilities": voice_caps,
            "database": DATABASE_PATH
        },
        message="系统运行正常"
    )

@app.post("/chat/text", summary="文本聊天")
async def text_chat(request: Request):
    """文本聊天接口"""
    try:
        data = await request.json()
        
        # 验证参数
        if not data or 'phone_number' not in data or 'query' not in data:
            return standard_response(
                success=False,
                message="缺少必要参数: phone_number 和 query"
            )
        
        phone_number = data['phone_number']
        query = data['query']
        
        # 处理文本查询
        result = engine.process_text_query(phone_number, query)
        
        return standard_response(
            success=True,
            data=result,
            message="文本查询处理成功"
        )
        
    except Exception as e:
        logger.error(f"文本聊天处理错误: {e}")
        return standard_response(
            success=False,
            message=f"服务器内部错误: {str(e)}"
        )

@app.post("/chat/voice", summary="语音聊天")
async def voice_chat(
    phone_number: str = Body(..., embed=True),
    audio_file: UploadFile = File(...)
):
    """语音聊天接口"""
    try:
        # 读取音频文件
        audio_data = await audio_file.read()
        if len(audio_data) < 100:
            return standard_response(
                success=False,
                message="音频文件为空或过小"
            )
        
        # 处理语音查询
        result = await engine.process_voice_query(phone_number, audio_data)
        
        if "error" in result:
            return standard_response(
                success=False,
                message=result["error"],
                data=result
            )
        
        # 处理音频数据（转为base64）
        if result.get("audio"):
            result["audio_base64"] = base64.b64encode(result["audio"]).decode("utf-8")
            del result["audio"]  # 移除二进制数据
        
        return standard_response(
            success=True,
            data=result,
            message="语音查询处理成功"
        )
        
    except Exception as e:
        logger.error(f"语音聊天处理错误: {e}")
        return standard_response(
            success=False,
            message=f"服务器内部错误: {str(e)}"
        )

@app.get("/user/{phone_number}/history", summary="获取用户对话历史")
async def get_user_history(phone_number: str):
    """获取用户对话历史"""
    result = engine.get_user_history(phone_number)
    return standard_response(
        success=result["success"],
        data=result if result["success"] else None,
        message=result.get("error", "获取历史记录成功")
    )

@app.get("/tts/generate", summary="文本转语音")
async def generate_tts(text: str):
    """单独的文本转语音接口"""
    try:
        if not text:
            return standard_response(
                success=False,
                message="文本内容不能为空"
            )
        
        audio, error = await engine.voice_processor.text_to_voice(text)
        if error or not audio:
            return standard_response(
                success=False,
                message=f"TTS合成失败: {error}"
            )
        
        # 返回音频文件
        return Response(
            content=audio,
            media_type="audio/wav",
            headers={"Content-Disposition": f"attachment; filename=tts_{datetime.now().timestamp()}.wav"}
        )
        
    except Exception as e:
        logger.error(f"TTS生成错误: {e}")
        return standard_response(
            success=False,
            message=f"服务器内部错误: {str(e)}"
        )

# 启动函数
def main():
    """启动FastAPI服务"""
    def print_config_status():
        """打印配置状态（替代原voice_config.print_config_status()）"""
        print("="*60)
        print("📝 配置状态检查")
        print("="*60)
        print(f"✅ 数据库路径: {DATABASE_PATH}")
        print(f"✅ LLM模型: {LLM_MODEL}")
        print(f"✅ ASR密钥配置: {'已配置' if ASR_ACCESS_KEY_ID else '缺失'}")
        print(f"✅ TTS密钥配置: {'已配置' if TTS_ACCESS_KEY_ID else '缺失'}")
        print(f"✅ OpenAI API Key: {'已配置' if OPENAI_API_KEY else '缺失'}")
        print(f"✅ 端口配置 - HTTP: {HTTP_PORT}, Gradio: {GRADIO_PORT}, FastAPI: {FASTAPI_PORT}")
        print("="*60)

    # 打印配置状态
    print_config_status()
    
    # 获取端口配置
    port = FASTAPI_PORT
    
    print(f"\n CRM智能语音客服系统启动中...")
    print(f" API地址: http://0.0.0.0:{port}")
    print(f" API文档: http://0.0.0.0:{port}/docs")
    
    # 启动服务
    uvicorn.run(
        "main_api:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    main()