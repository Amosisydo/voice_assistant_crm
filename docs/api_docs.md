### 1. API接口文档

#### 1.1 文本聊天接口

**http**

```
POST /chat
Content-Type: application/json

请求参数：
{
    "phone_number": "13800138000",
    "query": "你们有什么产品？"
}

响应：
{
    "user_id": 1,
    "is_new_user": false,
    "intent": "A",
    "response": "我们提供以下产品...",
    "channel": "text",
    "intent_description": "产品咨询-RAG检索",
    "timestamp": "2024-01-01T12:00:00"
}
```

#### 1.2 语音聊天接口

**http**

```
POST /voice/chat
Content-Type: multipart/form-data

参数：
phone_number: 13800138000
audio: [音频文件]

响应：
- 音频格式：返回WAV格式音频
- 文本格式：返回JSON包含识别文本和回复
```

#### 1.3 语音识别接口

**http**

```
POST /voice/recognize
Content-Type: multipart/form-data

参数：
audio: [音频文件]

响应：
{
    "recognized_text": "你好，我想咨询产品",
    "timestamp": "2024-01-01T12:00:00"
}
```

#### 1.4 用户历史接口

**http**

```
GET /user/{phone_number}/history

响应：
{
    "phone_number": "13800138000",
    "user_id": 1,
    "conversation_history": [...]
}
```

### 2. 接口测试

运行 test\test_api_with_audio.py测试脚本即可进行接口测试，api地址(http://localhost:8003)和音频保存(test_audio_local)目录可根据实际情况进行调整.


测试样例

```
(xiaozhi) F:\voice_assistant>C:/Users/L/anaconda3/envs/xiaozhi/python.exe f:/voice_assistant/test_api_with_audio.py
CRM语音助手 API测试工具输入API地址 (默认: http://localhost:8003): http://localhost:8003
输入测试音频目录 (默认: test_audio_local): F:\voice_assistant_crm\test_audio_local

开始综合API测试
📁 响应音频目录: response_audio
📁 测试报告目录: test_report
开始综合API测试
📁 响应音频目录: response_audio
📁 测试报告目录: test_report
===1️⃣ 健康检查:
✅ 健康检查通过
   模型: deepseek-ai/DeepSeek-V2.5
   语音支持: True2️⃣ 文本聊天测试:
📝 测试文本聊天: 你好，我想了解一下产品...
✅ 文本聊天成功
   响应时间: 8803ms
   用户ID: 1
   意图: A
   回复: 您好！感谢您对我们产品的关注。为了更好地为您提供详细的产品信息，请您具体说明您想了解的产品类型或相关...
📝 测试文本聊天: 今天的天气怎么样？...
❌ 文本聊天异常: HTTPConnectionPool(host='localhost', port=8003): Read timed out. (read timeout=10)
📝 测试文本聊天: 请帮我转接人工客服...
✅ 文本聊天成功
   响应时间: 7862ms
   用户ID: 3
   意图: C
   回复: 您好！我理解您希望直接与人工客服沟通。目前我无法直接为您转接人工客服，但我非常乐意帮助您解决问题。请...3️⃣ 语音识别测试 (5 个音频):
🔊 测试语音识别: test_01_你好，我想咨询一下你.wav
✅ 语音识别成功
   响应时间: 11723ms
   识别结果: 你好，我想咨询一下你们的产品。
🔊 测试语音识别: test_02_今天的天气怎么样.wav
✅ 语音识别成功
   响应时间: 1033ms
   识别结果: 今天的天气怎么样？
🔊 测试语音识别: test_03_请帮我转接人工客服.wav
✅ 语音识别成功
   响应时间: 659ms
   识别结果: 请帮我转接人工客服。
🔊 测试语音识别: test_04_这个产品的价格是多少.wav
✅ 语音识别成功
   响应时间: 532ms
   识别结果: 这个产品的价格是多少？
🔊 测试语音识别: test_05_谢谢，再见.wav
✅ 语音识别成功
   响应时间: 517ms
   识别结果: 谢谢，再见。4️⃣ 语音聊天测试 (5 个音频):
🎤 测试语音聊天: test_01_你好，我想咨询一下你.wav
❌ 语音聊天异常: HTTPConnectionPool(host='localhost', port=8003): Read timed out. (read timeout=20)
🎤 测试语音聊天: test_02_今天的天气怎么样.wav
💾 音频已保存到: response_audio\voice_chat_13800138000_1767526268.wav
   文件大小: 1,096,684 字节
✅ 语音聊天成功 (音频回复)
   响应时间: 12400ms
   音频大小: 1096684 字节
   音频已保存到: voice_chat_13800138000_1767526268.wav
🎤 测试语音聊天: test_03_请帮我转接人工客服.wav
💾 音频已保存到: response_audio\voice_chat_13800138000_1767526279.wav
   文件大小: 505,644 字节
✅ 语音聊天成功 (音频回复)
   响应时间: 8506ms
   音频大小: 505644 字节
   音频已保存到: voice_chat_13800138000_1767526279.wav
🎤 测试语音聊天: test_04_这个产品的价格是多少.wav
❌ 语音聊天异常: HTTPConnectionPool(host='localhost', port=8003): Read timed out. (read timeout=20)
🎤 测试语音聊天: test_05_谢谢，再见.wav
💾 音频已保存到: response_audio\voice_chat_13800138000_1767526310.wav
   文件大小: 367,244 字节
✅ 语音聊天成功 (音频回复)
   响应时间: 4719ms
   音频大小: 367244 字节
   音频已保存到: voice_chat_13800138000_1767526310.wav============================================================
测试报告总测试数: 13
成功数: 10
成功率: 76.9%🎯 意图分布:
   A: 1 次
   C: 1 次详细结果:✅ 文本聊天: 你好，我想了解一下产品...
用户ID: 1, 意图: A, 耗时: 8803ms❌ 文本聊天: 今天的天气怎么样？...
错误: HTTPConnectionPool(host='localhost', port=8003): Read timed out. (read timeout=10)✅ 文本聊天: 请帮我转接人工客服...
用户ID: 3, 意图: C, 耗时: 7862ms✅ 语音识别: test_01_你好，我想咨询一下你.wav
识别: 你好，我想咨询一下你们的产品。..., 耗时: 11723ms✅ 语音识别: test_02_今天的天气怎么样.wav
识别: 今天的天气怎么样？..., 耗时: 1033ms✅ 语音识别: test_03_请帮我转接人工客服.wav
识别: 请帮我转接人工客服。..., 耗时: 659ms✅ 语音识别: test_04_这个产品的价格是多少.wav
识别: 这个产品的价格是多少？..., 耗时: 532ms✅ 语音识别: test_05_谢谢，再见.wav
识别: 谢谢，再见。..., 耗时: 517ms❌ 语音聊天: test_01_你好，我想咨询一下你.wav
错误: HTTPConnectionPool(host='localhost', port=8003): Read timed out. (read timeout=20)✅ 语音聊天: test_02_今天的天气怎么样.wav
音频回复: voice_chat_13800138000_1767526268.wav, 大小: 1096684字节, 耗时: 12400ms✅ 语音聊天: test_03_请帮我转接人工客服.wav
音频回复: voice_chat_13800138000_1767526279.wav, 大小: 505644字节, 耗时: 8506ms❌ 语音聊天: test_04_这个产品的价格是多少.wav
错误: HTTPConnectionPool(host='localhost', port=8003): Read timed out. (read timeout=20)✅ 语音聊天: test_05_谢谢，再见.wav
音频回复: voice_chat_13800138000_1767526310.wav, 大小: 367244字节, 耗时: 4719ms📊 详细报告已保存到: test_report\test_report_1767526313.json🎵 响应音频文件 (3 个):voice_chat_13800138000_1767526268.wavvoice_chat_13800138000_1767526279.wavvoice_chat_13800138000_1767526310.wav
```
