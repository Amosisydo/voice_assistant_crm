import requests
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional
import wave

class APIAudioTester:
    """API音频测试器 - 优化版"""
    
    def __init__(self, base_url: str = "http://localhost:8003"):
        self.base_url = base_url
        self.test_results = []
        
        # 设置音频保存目录和测试报告目录
        self.response_audio_dir = Path("response_audio")
        self.test_report_dir = Path("test_report")
        self.setup_directories()
    
    def setup_directories(self):
        """设置音频保存目录和测试报告目录"""
        # 创建音频保存目录
        if not self.response_audio_dir.exists():
            self.response_audio_dir.mkdir(exist_ok=True)
            print(f"📁 创建音频保存目录: {self.response_audio_dir}")
        
        # 创建测试报告目录
        if not self.test_report_dir.exists():
            self.test_report_dir.mkdir(exist_ok=True)
            print(f"📁 创建测试报告目录: {self.test_report_dir}")
    
    def save_audio_response(self, audio_data: bytes, test_name: str = "response") -> str:
        """保存音频响应到response_audio目录"""
        timestamp = int(time.time())
        filename = f"{test_name}_{timestamp}.wav"
        filepath = self.response_audio_dir / filename
        
        try:
            with open(filepath, 'wb') as f:
                f.write(audio_data)
            print(f"💾 音频已保存到: {filepath}")
            print(f"   文件大小: {len(audio_data):,} 字节")
            return str(filepath)
        except Exception as e:
            print(f"❌ 保存音频文件失败: {e}")
            # 保存到当前目录作为备选
            temp_file = f"temp_{timestamp}.wav"
            with open(temp_file, 'wb') as f:
                f.write(audio_data)
            print(f"⚠️  音频已保存到临时文件: {temp_file}")
            return temp_file
    
    def test_health(self) -> bool:
        """测试健康检查接口"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 健康检查通过")
                print(f"   模型: {data.get('model')}")
                print(f"   语音支持: {data.get('voice_enabled')}")
                return True
            else:
                print(f"❌ 健康检查失败: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ 健康检查异常: {e}")
            return False
    
    def test_text_chat(self, phone_number: str, text: str) -> Optional[Dict]:
        """测试文本聊天"""
        try:
            payload = {
                "phone_number": phone_number,
                "query": text
            }
            
            print(f"📝 测试文本聊天: {text[:30]}...")
            start_time = time.time()
            
            response = requests.post(
                f"{self.base_url}/chat",
                json=payload,
                timeout=40
            )
            
            response_time = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 文本聊天成功")
                print(f"   响应时间: {response_time:.0f}ms")
                print(f"   用户ID: {data.get('user_id')}")
                print(f"   意图: {data.get('intent')}")  # 添加意图打印
                print(f"   回复: {data.get('response')[:50]}...")
                
                return {
                    "success": True,
                    "response_time": response_time,
                    "data": data
                }
            else:
                print(f"❌ 文本聊天失败: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}"
                }
                
        except Exception as e:
            print(f"❌ 文本聊天异常: {e}")
            return {"success": False, "error": str(e)}
    
    def test_voice_recognize(self, audio_file_path: str) -> Optional[Dict]:
        """测试语音识别"""
        try:
            if not os.path.exists(audio_file_path):
                print(f"❌ 音频文件不存在: {audio_file_path}")
                return None
            
            print(f"🔊 测试语音识别: {os.path.basename(audio_file_path)}")
            start_time = time.time()
            
            with open(audio_file_path, 'rb') as audio_file:
                files = {'audio': audio_file}
                response = requests.post(
                    f"{self.base_url}/voice/recognize",
                    files=files,
                    timeout=60
                )
            
            response_time = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 语音识别成功")
                print(f"   响应时间: {response_time:.0f}ms")
                print(f"   识别结果: {data.get('recognized_text', '')}")
                
                return {
                    "success": True,
                    "response_time": response_time,
                    "data": data
                }
            else:
                print(f"❌ 语音识别失败: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}"
                }
                
        except Exception as e:
            print(f"❌ 语音识别异常: {e}")
            return {"success": False, "error": str(e)}
    
    def test_voice_chat(self, phone_number: str, audio_file_path: str) -> Optional[Dict]:
        """测试语音聊天"""
        try:
            if not os.path.exists(audio_file_path):
                print(f"❌ 音频文件不存在: {audio_file_path}")
                return None
            
            print(f"🎤 测试语音聊天: {os.path.basename(audio_file_path)}")
            start_time = time.time()
            
            with open(audio_file_path, 'rb') as audio_file:
                files = {'audio': audio_file}
                data = {'phone_number': phone_number}
                response = requests.post(
                    f"{self.base_url}/voice/chat",
                    files=files,
                    data=data,
                    timeout=60
                )
            
            response_time = (time.time() - start_time) * 1000
            content_type = response.headers.get('Content-Type', '')
            
            result = {
                "success": response.status_code == 200,
                "response_time": response_time,
                "content_type": content_type
            }
            
            if response.status_code == 200:
                if 'audio/wav' in content_type:
                    # 音频响应 - 保存到response_audio目录
                    test_name = f"voice_chat_{phone_number}"
                    audio_path = self.save_audio_response(response.content, test_name)
                    
                    print(f"✅ 语音聊天成功 (音频回复)")
                    print(f"   响应时间: {response_time:.0f}ms")
                    print(f"   音频大小: {len(response.content)} 字节")
                    print(f"   音频已保存到: {os.path.basename(audio_path)}")
                    
                    result["audio_file"] = audio_path
                    result["audio_size"] = len(response.content)
                    
                elif 'application/json' in content_type:
                    # 文本响应
                    response_data = response.json()
                    print(f"✅ 语音聊天成功 (文本回复)")
                    print(f"   响应时间: {response_time:.0f}ms")
                    print(f"   识别文本: {response_data.get('recognized_text', '')}")
                    print(f"   回复内容: {response_data.get('response', '')[:50]}...")
                    print(f"   意图: {response_data.get('intent', '')}")  # 添加意图打印
                    
                    result["data"] = response_data
                    
                    # 如果有音频响应字段，也保存到response_audio目录
                    if response_data.get('audio_response'):
                        test_name = f"voice_chat_json_{phone_number}"
                        audio_path = self.save_audio_response(
                            response_data['audio_response'], 
                            test_name
                        )
                        result["audio_file"] = audio_path
                        result["audio_size"] = len(response_data['audio_response'])
                else:
                    print(f"⚠️  未知响应类型: {content_type}")
                    result["success"] = False
            else:
                print(f"❌ 语音聊天失败: {response.status_code} - {response.text[:100]}")
                result["error"] = f"HTTP {response.status_code}"
            
            return result
                
        except Exception as e:
            print(f"❌ 语音聊天异常: {e}")
            return {"success": False, "error": str(e)}
    
    def run_comprehensive_test(self, audio_dir: str = "test_audio"):
        """运行综合测试"""
        print("=" * 60)
        print("开始综合API测试")
        print(f"📁 响应音频目录: {self.response_audio_dir}")
        print(f"📁 测试报告目录: {self.test_report_dir}")
        print("=" * 60)
        
        # 健康检查
        print("\n1️⃣ 健康检查:")
        if not self.test_health():
            print("❌ 健康检查失败，终止测试")
            return
        
        # 文本聊天测试
        print("\n2️⃣ 文本聊天测试:")
        text_cases = [
            ("13800138000", "你好，我想了解一下产品"),
            ("13800138001", "今天的天气怎么样？"),
            ("13800138002", "请帮我转接人工客服")
        ]
        
        for phone, text in text_cases:
            result = self.test_text_chat(phone, text)
            self.test_results.append({
                "type": "text_chat",
                "phone": phone,
                "text": text,
                "result": result
            })
            time.sleep(1)  # 避免请求过快
        
        # 测试音频文件
        audio_dir_path = Path(audio_dir)
        if audio_dir_path.exists():
            audio_files = list(audio_dir_path.glob("*.wav"))[:5]
            
            if audio_files:
                print(f"\n3️⃣ 语音识别测试 ({len(audio_files)} 个音频):")
                for audio_file in audio_files:
                    result = self.test_voice_recognize(str(audio_file))
                    self.test_results.append({
                        "type": "voice_recognize",
                        "file": audio_file.name,
                        "result": result
                    })
                    time.sleep(2)  # 避免请求过快
                
                print(f"\n4️⃣ 语音聊天测试 ({len(audio_files)} 个音频):")
                for audio_file in audio_files:
                    result = self.test_voice_chat("13800138000", str(audio_file))
                    self.test_results.append({
                        "type": "voice_chat",
                        "file": audio_file.name,
                        "result": result
                    })
                    time.sleep(3)  # 避免请求过快
        
        # 生成测试报告并保存到test_report目录
        self.generate_test_report()
    
    def generate_test_report(self):
        """生成测试报告并保存到test_report目录"""
        print("\n" + "=" * 60)
        print("测试报告")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        successful_tests = sum(1 for r in self.test_results if r.get("result", {}).get("success"))
        
        print(f"总测试数: {total_tests}")
        print(f"成功数: {successful_tests}")
        print(f"成功率: {successful_tests/total_tests*100:.1f}%" if total_tests > 0 else "0.0%")
        
        # 统计意图分布
        intent_stats = {}
        for test in self.test_results:
            result = test.get("result", {})
            if result.get("success"):
                data = result.get("data", {})
                intent = data.get("intent")
                if intent:
                    intent_stats[intent] = intent_stats.get(intent, 0) + 1
        
        if intent_stats:
            print(f"\n🎯 意图分布:")
            for intent, count in intent_stats.items():
                print(f"   {intent}: {count} 次")
        
        # 详细结果
        print("\n详细结果:")
        for i, test in enumerate(self.test_results, 1):
            result = test.get("result", {})
            success = result.get("success", False)
            status = "✅" if success else "❌"
            
            if test["type"] == "text_chat":
                print(f"{i}. {status} 文本聊天: {test['text'][:30]}...")
                if success:
                    print(f"   用户ID: {result['data'].get('user_id')}, "
                          f"意图: {result['data'].get('intent')}, "
                          f"耗时: {result.get('response_time', 0):.0f}ms")
            elif test["type"] == "voice_recognize":
                print(f"{i}. {status} 语音识别: {test['file']}")
                if success:
                    text = result['data'].get('recognized_text', '')
                    print(f"   识别: {text[:30]}..., "
                          f"耗时: {result.get('response_time', 0):.0f}ms")
            elif test["type"] == "voice_chat":
                print(f"{i}. {status} 语音聊天: {test['file']}")
                if success:
                    if 'audio_file' in result:
                        audio_filename = os.path.basename(result['audio_file'])
                        print(f"   音频回复: {audio_filename}, "
                              f"大小: {result.get('audio_size', 0)}字节, "
                              f"耗时: {result.get('response_time', 0):.0f}ms")
                    elif 'data' in result:
                        data = result['data']
                        print(f"   文本回复: {data.get('response', '')[:30]}..., "
                              f"意图: {data.get('intent')}, "
                              f"耗时: {result.get('response_time', 0):.0f}ms")
            
            if not success:
                print(f"   错误: {result.get('error', '未知错误')}")
        
        # 保存报告到test_report目录
        timestamp = int(time.time())
        report_file = self.test_report_dir / f"test_report_{timestamp}.json"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump({
                "timestamp": timestamp,
                "total_tests": total_tests,
                "successful_tests": successful_tests,
                "success_rate": successful_tests/total_tests*100 if total_tests > 0 else 0,
                "intent_stats": intent_stats,
                "results": self.test_results
            }, f, ensure_ascii=False, indent=2)
        
        print(f"\n📊 详细报告已保存到: {report_file}")
        
        # 显示response_audio目录中的音频文件
        audio_files = list(self.response_audio_dir.glob("*.wav"))
        if audio_files:
            print(f"\n🎵 响应音频文件 ({len(audio_files)} 个):")
            for audio_file in audio_files[-5:]:  # 显示最近5个
                print(f"   - {audio_file.name}")
            if len(audio_files) > 5:
                print(f"   ... 还有 {len(audio_files) - 5} 个文件")

def main():
    """主函数"""
    print("CRM语音助手 API测试工具")
    print("=" * 60)
    
    # 配置
    base_url = input("输入API地址 (默认: http://localhost:8003): ").strip()
    if not base_url:
        base_url = "http://localhost:8003"

    audio_dir = input("输入测试音频目录 (默认: test_audio_local): ").strip()
    if not audio_dir:
        audio_dir = "test_audio_local"
    
    # 创建测试器并运行
    tester = APIAudioTester(base_url)
    tester.run_comprehensive_test(audio_dir)

if __name__ == "__main__":
    main()