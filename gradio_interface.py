import gradio as gr
import requests
import json
from datetime import datetime, timezone, timedelta
import logging
import tempfile
import os
import sys

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API 配置
from config import HTTP_PORT
API_BASE_URL = f"http://localhost:{HTTP_PORT}"

class IntegratedCRMInterface:
    def __init__(self, api_base_url=API_BASE_URL):
        self.api_base_url = api_base_url
        self.app = None
        # 检测Gradio版本
        self.gradio_version = self._detect_gradio_version()
        logger.info(f"检测到Gradio版本: {self.gradio_version}")
    
    def _detect_gradio_version(self):
        """检测Gradio版本"""
        try:
            import gradio as gr
            return gr.__version__
        except (ImportError, AttributeError):
            return "unknown"
    
    def _utc_to_local(self, utc_time_str):
        """将UTC时间字符串转换为本地时间（北京时间）"""
        if not utc_time_str:
            return ""
        
        try:
            # 尝试解析不同的时间格式
            for fmt in [
                "%Y-%m-%dT%H:%M:%S.%f",  # ISO格式带毫秒
                "%Y-%m-%dT%H:%M:%S",     # ISO格式不带毫秒
                "%Y-%m-%d %H:%M:%S.%f",  # 空格分隔带毫秒
                "%Y-%m-%d %H:%M:%S"      # 空格分隔不带毫秒
            ]:
                try:
                    # 解析UTC时间
                    utc_dt = datetime.strptime(utc_time_str, fmt)
                    # 标记为UTC时间
                    utc_dt = utc_dt.replace(tzinfo=timezone.utc)
                    # 北京时间
                    beijing_tz = timezone(timedelta(hours=8))
                    local_dt = utc_dt.astimezone(beijing_tz)
                    # 返回格式化的时间
                    return local_dt.strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    continue
            
            # 如果所有格式都失败，返回原始字符串
            return utc_time_str
        except Exception as e:
            logger.error(f"时间转换失败: {utc_time_str} - {e}")
            return utc_time_str
    
    def _ensure_message_format(self, history):
        """
        确保历史记录是消息格式 [{"role": "...", "content": "..."}, ...]
        兼容Gradio 6.x
        """
        if history is None:
            return []
        
        # 如果已经是空列表，直接返回
        if history == []:
            return []
        
        # 检查第一个元素来判断格式
        if history and isinstance(history[0], list):
            messages = []
            for pair in history:
                if isinstance(pair, list) and len(pair) == 2:
                    user_msg, bot_msg = pair
                    messages.append({"role": "user", "content": str(user_msg)})
                    messages.append({"role": "assistant", "content": str(bot_msg)})
            return messages
        elif history and isinstance(history[0], dict) and "role" in history[0]:
            # 已经是消息格式
            return history
        else:
            # 未知格式，返回空
            return []
    
    def test_connection(self):
        """测试与后端的连接"""
        try:
            response = requests.get(f"{self.api_base_url}/health")
            if response.status_code == 200:
                data = response.json()
                status = f"连接正常\n模型: {data.get('model')}\n语音支持: {'已启用' if data.get('voice_enabled') else '未启用'}"
                return status
            else:
                return f"连接异常: {response.text}"
        except Exception as e:
            return f"连接失败: {str(e)}"
    
    def send_text_message(self, phone_number, message, history):
        """发送文本消息"""
        if not phone_number or not message:
            return history, "请填写手机号码和消息内容"
        
        try:
            payload = {
                "phone_number": phone_number,
                "query": message
            }
            
            logger.info(f"发送文本消息: {phone_number} - {message}")
            
            response = requests.post(
                f"{self.api_base_url}/chat",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # 确保历史是消息格式
                current_messages = self._ensure_message_format(history)
                
                # 添加新消息
                current_messages.append({
                    "role": "user", 
                    "content": message
                })
                current_messages.append({
                    "role": "assistant", 
                    "content": result["response"]
                })
                
                details = self._format_response_details(result)
                return current_messages, details
            else:
                error_msg = f"API错误: {response.status_code} - {response.text}"
                return history, error_msg
                
        except Exception as e:
            error_msg = f"请求失败: {str(e)}"
            return history, error_msg
    
    def send_voice_message(self, phone_number, audio_file, history):
        """发送语音消息 - 修复：同时获取文本回复和音频回复"""
        if not phone_number or not audio_file:
            return history, "请填写手机号码并录制语音"
        
        try:
            # 读取音频文件
            with open(audio_file, 'rb') as f:
                audio_data = f.read()
            
            files = {
                'audio': ('audio.wav', audio_data, 'audio/wav')
            }
            data = {
                'phone_number': phone_number
            }
            
            logger.info(f"发送语音消息: {phone_number}")
            
            # 语音识别
            recognize_files = {'audio': ('audio.wav', audio_data, 'audio/wav')}
            recognize_response = requests.post(
                f"{self.api_base_url}/voice/recognize",
                files=recognize_files
            )
            
            user_text = ""
            if recognize_response.status_code == 200:
                recognize_data = recognize_response.json()
                user_text = recognize_data.get('recognized_text', '')
                user_message = f"[语音] {user_text}"
            else:
                user_message = "[语音消息]"
            
            # 确保历史是消息格式
            current_messages = self._ensure_message_format(history)
            
            # 发送文本查询以获取文本回复
            text_response = None
            if user_text:
                try:
                    text_payload = {
                        "phone_number": phone_number,
                        "query": user_text
                    }
                    text_response = requests.post(
                        f"{self.api_base_url}/chat",
                        json=text_payload,
                        headers={"Content-Type": "application/json"}
                    )
                except Exception as e:
                    logger.error(f"文本查询失败: {e}")
            
            # 发送语音聊天请求获取音频回复
            voice_response = requests.post(
                f"{self.api_base_url}/voice/chat",
                files=files,
                data=data
            )
            
            audio_path = None
            assistant_text_response = ""
            
            if voice_response.status_code == 200:
                content_type = voice_response.headers.get('content-type', '')
                
                if 'audio' in content_type:
                    # 语音回复
                    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                        tmp_file.write(voice_response.content)
                        audio_path = tmp_file.name
                    
                    # 从文本响应中获取回复文本
                    if text_response and text_response.status_code == 200:
                        text_result = text_response.json()
                        assistant_text_response = text_result.get('response', '已收到语音回复，请稍候播放')
                    else:
                        # 如果文本查询失败，使用通用回复
                        assistant_text_response = "已收到语音回复，请稍候播放"
                else:
                    # 文本回复（不应该发生，但保持兼容）
                    voice_result = voice_response.json()
                    assistant_text_response = voice_result.get('response', '')
                    
                    # 从文本响应获取更多详情
                    if text_response and text_response.status_code == 200:
                        text_result = text_response.json()
                        details = self._format_response_details(text_result)
                    else:
                        details = f"收到语音消息，回复为文本\n回复内容: {assistant_text_response}"
            else:
                error_msg = f"语音API错误: {voice_response.status_code} - {voice_response.text}"
                return history, error_msg, None
            
            # 添加消息到历史
            current_messages.append({
                "role": "user", 
                "content": user_message
            })
            current_messages.append({
                "role": "assistant", 
                "content": assistant_text_response
            })
            
            # 格式化详情信息
            if text_response and text_response.status_code == 200:
                text_result = text_response.json()
                details = self._format_response_details(text_result)
            else:
                details = f"收到语音消息并回复\n回复内容: {assistant_text_response}"
            
            return current_messages, details, audio_path
                
        except Exception as e:
            error_msg = f"语音请求失败: {str(e)}"
            return history, error_msg, None
    
    def _format_response_details(self, result):
        """格式化响应详情"""
        # 转换时间
        timestamp_str = result.get('timestamp', '')
        local_time = self._utc_to_local(timestamp_str)
        time_display = local_time[11:19] if local_time else datetime.now().strftime("%H:%M:%S")
        
        details = f"""
**回复详情:**
{result['response']}

**意图**: {result['intent']} ({result.get('intent_description', '')})
**用户ID**: {result['user_id']} | **渠道**: {result.get('channel', 'text')}
**类型**: {'新用户' if result['is_new_user'] else '老用户'}
**时间**: {time_display}
"""
        return details
    
    def get_user_history(self, phone_number):
        """获取用户对话历史"""
        if not phone_number:
            return "请先输入手机号码"
        
        try:
            response = requests.get(f"{self.api_base_url}/user/{phone_number}/history")
            
            if response.status_code == 200:
                data = response.json()
                return self._format_history_display(data)
            else:
                return f"获取历史失败: {response.text}"
                
        except Exception as e:
            return f"请求失败: {str(e)}"
    
    def _format_history_display(self, data):
        """格式化历史记录显示"""
        history = data.get("conversation_history", [])
        
        if not history:
            return "该用户暂无对话历史"
        
        # 显示最近10条记录
        recent_history = history[-10:] if len(history) > 10 else history
        recent_history.reverse()  # 按时间顺序显示，最新的在最后
        
        formatted = f"**用户 {data['phone_number']} 的对话历史 (共{len(history)}条，显示最近{len(recent_history)}条):**\n\n"
        
        for i, conv in enumerate(recent_history, 1):
            intent_info = f" ({conv.get('intent', 'N/A')})" if conv.get("intent") else ""
            
            # 处理时间显示
            timestamp_str = conv.get('timestamp', '')
            local_time = self._utc_to_local(timestamp_str)
            
            if local_time:
                time_str = local_time

            else:
                time_str = "时间未知"
            
            formatted += f"{i}. {conv['role'].title()} {intent_info}\n"
            formatted += f"   时间: {time_str}\n"
            formatted += f"   内容: {conv['content'][:60]}{'...' if len(conv['content']) > 60 else ''}\n\n"
        
        return formatted
    
    def create_integrated_interface(self):
        """创建整合的界面"""
        with gr.Blocks(title="CRM聊天系统", theme=gr.themes.Soft()) as interface:
            
            gr.Markdown("# CRM聊天系统")
            
            with gr.Row():
                # 左侧主面板
                with gr.Column(scale=2):
                    # 用户信息
                    phone_input = gr.Textbox(
                        label="手机号码", 
                        value="13800138000", 
                        placeholder="请输入手机号码"
                    )
                    
                    
                    chatbot = gr.Chatbot(
                        height=400,
                        label="对话记录",
                        type="messages"
                    )
                    
                    # 输入方式标签页
                    with gr.Tabs():
                        with gr.TabItem("文本输入"):
                            text_input = gr.Textbox(
                                placeholder="输入消息...", 
                                show_label=False,
                                max_lines=3
                            )
                            text_send_btn = gr.Button("发送文本", variant="primary")
                        
                        with gr.TabItem("语音输入"):
                            voice_input = gr.Audio(
                                sources="microphone",
                                type="filepath",
                                label="点击录音"
                            )
                            voice_send_btn = gr.Button("发送语音", variant="primary")
                
                # 右侧侧边栏
                with gr.Column(scale=1):
                    # 操作按钮
                    with gr.Row():
                        status_btn = gr.Button("连接状态", size="sm")
                        history_btn = gr.Button("历史记录", size="sm")
                        clear_btn = gr.Button("清空对话", size="sm")
                    
                    # 详细信息标签页
                    with gr.Tabs():
                        with gr.TabItem("响应详情"):
                            response_details = gr.Markdown(
                                value="发送消息后，这里将显示详细的响应信息..."
                            )
                        with gr.TabItem("用户历史"):
                            history_output = gr.Markdown(
                                value="点击历史记录按钮获取用户对话历史..."
                            )
                        with gr.TabItem("语音回复"):
                            
                            voice_output = gr.Audio(
                                label="语音回复",
                                type="filepath",
                                interactive=False,
                                autoplay=True
                            )
                        with gr.TabItem("系统说明"):
                            gr.Markdown("""
                            **使用说明:**
                            1. 输入手机号码识别用户
                            2. 选择文本或语音输入方式
                            3. 发送消息获取智能回复
                            
                            **意图分类:**
                            - A: 产品咨询 (RAG检索)
                            - B: 实时信息 (网络搜索)  
                            - C: 常规问答 (模型回复)
                            
                            **语音功能:**
                            - 支持语音输入和语音回复
                            - 语音消息会自动转换为文字
                            - 系统回复可自动转换为语音（自动播放）
                            """)
            
            # 绑定事件
            text_send_btn.click(
                self.send_text_message,
                inputs=[phone_input, text_input, chatbot],
                outputs=[chatbot, response_details]
            ).then(
                lambda: "",
                outputs=text_input
            )
            
            text_input.submit(
                self.send_text_message,
                inputs=[phone_input, text_input, chatbot],
                outputs=[chatbot, response_details]
            ).then(
                lambda: "",
                outputs=text_input
            )
            
            voice_send_btn.click(
                self.send_voice_message,
                inputs=[phone_input, voice_input, chatbot],
                outputs=[chatbot, response_details, voice_output]
            )
            
            history_btn.click(
                self.get_user_history,
                inputs=phone_input,
                outputs=history_output
            )
            
            status_btn.click(
                self.test_connection,
                outputs=response_details
            )
            
            clear_btn.click(
                lambda: ([], "对话已清空"),
                outputs=[chatbot, response_details]
            )
            
            self.app = interface
            return interface
    
    def launch(self, share=False, inbrowser=True, quiet=True):
        """启动Gradio界面"""
        if not self.app:
            self.create_integrated_interface()
        
        from config import GRADIO_PORT
        return self.app.launch(
            server_name="0.0.0.0",
            server_port=GRADIO_PORT,
            share=share,
            inbrowser=inbrowser,
            quiet=quiet
        )

def run_gradio_interface():
    """单独运行Gradio界面"""
    print(" 启动CRM聊天界面...")
    print(f" 后端API: {API_BASE_URL}")
    
    # 创建界面实例并启动
    interface = IntegratedCRMInterface()
    interface.create_integrated_interface()
    interface.launch()

if __name__ == "__main__":
    run_gradio_interface()