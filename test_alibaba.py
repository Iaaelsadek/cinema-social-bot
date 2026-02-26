import os
import dashscope
from dashscope.audio.tts_v2 import SpeechSynthesizer
from dotenv import load_dotenv

load_dotenv()

dashscope.api_key = os.getenv("ALIBABA_API_KEY")
dashscope.base_http_api_url = 'https://dashscope-intl.aliyuncs.com/api/v1'
dashscope.base_websocket_api_url = 'wss://dashscope-intl.aliyuncs.com/api-ws/v1/inference'

print(f"API Key: {dashscope.api_key[:5]}...")
print(f"HTTP URL: {dashscope.base_http_api_url}")
print(f"WS URL: {dashscope.base_websocket_api_url}")

synthesizer = SpeechSynthesizer(model="cosyvoice-v3-plus", voice="longxiaomiao_v2")

try:
    audio_data = synthesizer.call("مرحبا بك في تجربة علي بابا")
    if audio_data:
        print("Success! Audio data received.")
        with open("test_alibaba.mp3", "wb") as f:
            f.write(audio_data)
    else:
        print("Failed: No audio data.")
except Exception as e:
    print(f"Error: {e}")
