from flask import Flask, request, jsonify, send_file
from datetime import datetime
import logging
import io
import base64
import threading
import time
from response_engine import ResponseEngine
from database import init_database, UserManager
from config import LLM_MODEL, HTTP_PORT, GRADIO_PORT
from voice_processor import VoiceProcessor

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 初始化数据库
init_database()

# 初始化语音处理器
voice_processor = VoiceProcessor()

def start_gradio_interface():
    """在后台线程中启动Gradio界面"""
    time.sleep(2)  # 等待Flask启动
    
    try:
        print(" 正在启动Gradio Web界面...")
        from gradio_interface import IntegratedCRMInterface
        interface = IntegratedCRMInterface()
        interface.launch(
            share=False,
            inbrowser=True,
            quiet=True
        )
    except Exception as e:
        logger.error(f"启动Gradio界面失败: {e}")
        print(f" Gradio启动失败: {e}")

@app.route('/chat', methods=['POST'])
def chat_api():
    """文本聊天API接口"""
    try:
        data = request.get_json()
        
        # 验证请求数据
        if not data or 'phone_number' not in data or 'query' not in data:
            return jsonify({
                "error": "缺少必要参数: phone_number 和 query"
            }), 400
        
        phone_number = data['phone_number']
        query = data['query']
        
        # 处理聊天请求
        engine = ResponseEngine()
        result = engine.process_query(phone_number, query, channel='text')
        result["timestamp"] = datetime.now().isoformat()
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"API处理错误: {e}")
        return jsonify({
            "error": "服务器内部错误",
            "message": str(e)
        }), 500

@app.route('/voice/chat', methods=['POST'])
async def voice_chat_api():
    """语音聊天API接口"""
    try:
        # 获取请求数据
        phone_number = request.form.get('phone_number')
        audio_file = request.files.get('audio')
        
        if not phone_number or not audio_file:
            return jsonify({
                "error": "缺少必要参数: phone_number 和 audio"
            }), 400
        
        # 读取音频数据
        audio_data = audio_file.read()
        
        # 处理语音请求
        engine = ResponseEngine()
        result = await engine.process_voice_query(phone_number, audio_data)
        
        if "error" in result:
            return jsonify(result), 400
        
        result["timestamp"] = datetime.now().isoformat()
        
        # 如果有音频回复，返回音频
        if result.get("audio_response"):
            return send_file(
                io.BytesIO(result["audio_response"]),
                mimetype='audio/wav',
                as_attachment=False,
                download_name='response.wav'
            )
        else:
            # 确保返回的JSON结构正确
            # 检查并确保必要字段存在
            response_data = {
                "user_id": result.get("user_id", 0),
                "is_new_user": result.get("is_new_user", False),
                "intent": result.get("intent", "C"),
                "response": result.get("response", ""),
                "recognized_text": result.get("recognized_text", ""),
                "channel": result.get("channel", "voice"),
                "intent_description": result.get("intent_description", ""),
                "timestamp": result.get("timestamp")
            }
            return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"语音API处理错误: {e}")
        return jsonify({
            "error": "服务器内部错误",
            "message": str(e)
        }), 500

@app.route('/voice/recognize', methods=['POST'])
async def voice_recognize_api():
    """语音识别API"""
    try:
        audio_file = request.files.get('audio')
        if not audio_file:
            return jsonify({"error": "缺少音频文件"}), 400
        
        audio_data = audio_file.read()
        text, error = await voice_processor.speech_to_text(audio_data)
        
        if error:
            return jsonify({"error": error}), 400
        
        return jsonify({
            "recognized_text": text,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"语音识别错误: {e}")
        return jsonify({"error": str(e)}), 500



@app.route('/user/<phone_number>/history', methods=['GET'])
def get_user_history(phone_number):
    """获取用户对话历史"""
    try:
        user_manager = UserManager()
        user_id, _ = user_manager.get_or_create_user(phone_number)
        history = user_manager.get_user_conversations(user_id)
        
        return jsonify({
            "phone_number": phone_number,
            "user_id": user_id,
            "conversation_history": history
        })
        
    except Exception as e:
        logger.error(f"获取用户历史失败: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """健康检查端点"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "model": LLM_MODEL,
        "voice_enabled": voice_processor.processor is not None
    })

if __name__ == '__main__':
    print("=" * 60)
    print(" CRM语音助手系统启动中...")
    print("=" * 60)
    
    # 打印API信息
    print(f" 后端API服务:")
    print(f"   - 文本聊天API: http://localhost:{HTTP_PORT}/chat")
    print(f"   - 语音聊天API: http://localhost:{HTTP_PORT}/voice/chat")
    print(f"   - 语音识别API: http://localhost:{HTTP_PORT}/voice/recognize")
    print(f"   - 健康检查: http://localhost:{HTTP_PORT}/health")
    print()
    print(f" Web界面将在Flask启动后自动打开...")
    print("=" * 60)
    
    # 在后台线程中启动Gradio界面
    gradio_thread = threading.Thread(target=start_gradio_interface, daemon=True)
    gradio_thread.start()
    
    # 启动Flask应用
    app.run(host='0.0.0.0', port=HTTP_PORT, debug=False)