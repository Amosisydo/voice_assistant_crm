"""
使用本地TTS库生成测试音频
"""

import os
import sys
import time
from pathlib import Path
import subprocess
from typing import List, Optional

class LocalTTSGenerator:
    """本地TTS生成器"""
    
    def __init__(self):
        self.test_phrases = [
            "你好，我叫小明",
            "今天深圳的天气怎么样",
            "请你介绍一下你们的产品参数",
            "这个产品的价格是多少",
            "谢谢，再见"
        ]
        
        # 检查可用的TTS引擎
        self.available_engines = self._detect_tts_engines()
    
    def _detect_tts_engines(self):
        """检测可用的TTS引擎"""
        engines = {}
        
        # 检查edge-tts
        try:
            import edge_tts
            engines["edge-tts"] = True
            print("✅ 检测到 edge-tts")
        except ImportError:
            engines["edge-tts"] = False
            print("❌ 未安装 edge-tts，可以运行: pip install edge-tts")
        
        # 检查pyttsx3（系统TTS）
        try:
            import pyttsx3
            engines["pyttsx3"] = True
            print("✅ 检测到 pyttsx3")
        except ImportError:
            engines["pyttsx3"] = False
            print("❌ 未安装 pyttsx3，可以运行: pip install pyttsx3")
        
        # 检查gTTS（Google TTS）
        try:
            from gtts import gTTS
            engines["gtts"] = True
            print("✅ 检测到 gTTS")
        except ImportError:
            engines["gtts"] = False
            print("❌ 未安装 gTTS，可以运行: pip install gtts")
        
        return engines
    
    def generate_with_edge_tts(self, text: str, output_path: Path) -> bool:
        """使用edge-tts生成语音"""
        try:
            import asyncio
            import edge_tts
            
            async def _generate():
                tts = edge_tts.Communicate(text=text, voice="zh-CN-XiaoxiaoNeural")
                await tts.save(str(output_path))
                return True
            
            # 运行异步函数
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(_generate())
            loop.close()
            
            if result and output_path.exists():
                print(f"  ✅ edge-tts: {text[:30]}...")
                return True
            return False
        except Exception as e:
            print(f"  ❌ edge-tts失败: {e}")
            return False
    
    def generate_with_pyttsx3(self, text: str, output_path: Path) -> bool:
        """使用pyttsx3生成语音"""
        try:
            import pyttsx3
            import wave
            import pyaudio
            
            engine = pyttsx3.init()
            
            # 设置属性
            engine.setProperty('rate', 150)  # 语速
            engine.setProperty('volume', 0.9)  # 音量
            
            # 保存到临时文件
            temp_file = output_path.with_suffix('.tmp.wav')
            engine.save_to_file(text, str(temp_file))
            engine.runAndWait()
            
            # 等待文件生成
            time.sleep(1)
            
            if temp_file.exists():
                # 转换格式（如果需要）
                import subprocess
                try:
                    subprocess.run([
                        'ffmpeg', '-y', '-i', str(temp_file),
                        '-ar', '16000', '-ac', '1',
                        str(output_path)
                    ], check=True, capture_output=True)
                    temp_file.unlink()  # 删除临时文件
                    print(f"  ✅ pyttsx3: {text[:30]}...")
                    return True
                except:
                    # 如果ffmpeg失败，直接使用原文件
                    temp_file.rename(output_path)
                    print(f"  ⚠️ pyttsx3 (无转换): {text[:30]}...")
                    return True
            return False
        except Exception as e:
            print(f"  ❌ pyttsx3失败: {e}")
            return False
    
    def generate_with_gtts(self, text: str, output_path: Path) -> bool:
        """使用gTTS生成语音"""
        try:
            from gtts import gTTS
            
            # 生成语音
            tts = gTTS(text=text, lang='zh-cn')
            tts.save(str(output_path))
            
            if output_path.exists():
                # 转换为WAV格式（如果需要）
                if output_path.suffix != '.wav':
                    wav_path = output_path.with_suffix('.wav')
                    try:
                        subprocess.run([
                            'ffmpeg', '-y', '-i', str(output_path),
                            '-ar', '16000', '-ac', '1',
                            str(wav_path)
                        ], check=True, capture_output=True)
                        output_path.unlink()  # 删除原始文件
                        output_path = wav_path
                    except:
                        pass
                
                print(f"  ✅ gTTS: {text[:30]}...")
                return True
            return False
        except Exception as e:
            print(f"  ❌ gTTS失败: {e}")
            return False
    
    def generate_all_test_audio(self, output_dir: str = "test_audio_local"):
        """生成所有测试音频"""
        # 创建输出目录
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        # 选择TTS引擎
        engine_choice = None
        available = [k for k, v in self.available_engines.items() if v]
        
        if not available:
            print("❌ 没有可用的TTS引擎，请先安装一个TTS库")
            print("推荐: pip install edge-tts")
            return []
        
        print(f"\n可用的TTS引擎: {', '.join(available)}")
        if len(available) == 1:
            engine_choice = available[0]
        else:
            print("请选择TTS引擎:")
            for i, engine in enumerate(available, 1):
                print(f"{i}. {engine}")
            choice = input(f"选择 (1-{len(available)}): ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(available):
                engine_choice = available[int(choice) - 1]
        
        if not engine_choice:
            print("❌ 无效选择")
            return []
        
        print(f"\n使用 {engine_choice} 生成测试音频...")
        print(f"输出目录: {output_path.absolute()}")
        print("-" * 60)
        
        # 生成音频
        generated_files = []
        for i, phrase in enumerate(self.test_phrases, 1):
            print(f"生成音频 {i}/{len(self.test_phrases)}: {phrase[:40]}...")
            
            # 创建安全的文件名
            safe_name = f"test_{i:02d}_{phrase[:10]}.wav".replace(' ', '_')
            file_path = output_path / safe_name
            
            success = False
            if engine_choice == "edge-tts":
                success = self.generate_with_edge_tts(phrase, file_path)
            elif engine_choice == "pyttsx3":
                success = self.generate_with_pyttsx3(phrase, file_path)
            elif engine_choice == "gtts":
                success = self.generate_with_gtts(phrase, file_path)
            
            if success and file_path.exists():
                generated_files.append((phrase, file_path))
                # 显示文件大小
                size_kb = os.path.getsize(file_path) / 1024
                print(f"    大小: {size_kb:.1f} KB")
            else:
                print(f"    ❌ 生成失败")
            
            # 避免请求过快
            time.sleep(1)
        
        print("-" * 60)
        print(f"✅ 完成！共生成 {len(generated_files)} 个音频文件")
        return generated_files

def main():
    """主函数"""
    print("CRM语音助手 - 本地TTS测试音频生成器")
    print("=" * 60)
    
    generator = LocalTTSGenerator()
    
    if not any(generator.available_engines.values()):
        print("\n❌ 没有可用的TTS引擎")
        print("\n推荐安装以下库之一：")
        print("1. edge-tts (微软Edge TTS，免费，质量好)")
        print("   安装: pip install edge-tts")
        print("2. gTTS (Google TTS，需要网络)")
        print("   安装: pip install gtts")
        print("3. pyttsx3 (系统TTS，离线)")
        print("   安装: pip install pyttsx3")
        return
    
    generator.generate_all_test_audio()
    
    print("\n📁 测试音频已保存到 'test_audio_local' 目录")
    print("\n💡 使用建议:")
    print("1. 这些音频文件可用于语音识别测试")
    print("2. 在Postman测试中，选择对应的音频文件")
    print("3. 如果需要更多测试语句，可以修改代码中的 test_phrases 列表")

if __name__ == "__main__":
    main()