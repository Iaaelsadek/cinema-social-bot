import gradio as gr 
import os 
import subprocess 
import sys 
import asyncio 
import edge_tts 
import psutil # For system monitoring 

# --- CONFIGURATION & VOICES --- 
ARABIC_VOICES = { 
    "شاكر (مصر)": "ar-EG-ShakirNeural", "سلمى (مصر)": "ar-EG-SalmaNeural", 
    "حامد (السعودية)": "ar-SA-HamedNeural", "زارينا (السعودية)": "ar-SA-ZariyahNeural", 
    "حمدان (الإمارات)": "ar-AE-HamdanNeural", "فاطمة (الإمارات)": "ar-AE-FatimaNeural", 
    "باسم (سوريا)": "ar-SY-BasselNeural", "بشرى (اليمن)": "ar-YE-MaryamNeural" 
} 

LOG_FILE = "system_logs.txt" 
current_process = None 

def get_sys_info(): 
    """Real-time system resource monitor.""" 
    cpu = psutil.cpu_percent() 
    ram = psutil.virtual_memory().percent 
    return f"🖥️ CPU: {cpu}% | 🧠 RAM: {ram}%" 

async def generate_sample(voice_key): 
    voice = ARABIC_VOICES[voice_key] 
    text = "جاري فحص جودة الصوت في مختبرات سينما بوت. النظام جاهز للإنتاج الآن." 
    path = f"sample_{voice}.mp3" 
    await edge_tts.Communicate(text, voice).save(path) 
    return path 

def preview_voice(voice_key): 
    return asyncio.run(generate_sample(voice_key)) 

def stream_logs(env_vars): 
    global current_process 
    os.system("playwright install chromium") 
    env_vars.update({"PYTHONUNBUFFERED": "1", "GRADIO_ANALYTICS_ENABLED": "False"}) 
    with open(LOG_FILE, "w", encoding="utf-8") as f: f.write("🚀 Starting Cinema Bot V6.0...\n") 
    process = subprocess.Popen([sys.executable, "main.py"], env=env_vars, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1) 
    current_process = process 
    logs = "" 
    for line in iter(process.stdout.readline, ''): 
        logs += line 
        yield logs, None 
    process.wait() 

def master_launch(mode, m_title, m_trailer, m_overview, tg, fb, insta, yt, tk, wa, voice_key, speed, quality, ai_temp, ai_style): 
    env = os.environ.copy() 
    env.update({ 
        "FORCE_POST": "true", "MANUAL_MODE": "true" if mode == "Manual" else "false", 
        "MANUAL_TITLE": m_title, "MANUAL_TRAILER": m_trailer, "MANUAL_OVERVIEW": m_overview, 
        "VOICE_MODEL": ARABIC_VOICES[voice_key], "VOICE_SPEED": str(speed), 
        "VIDEO_QUALITY": quality, "AI_TEMP": str(ai_temp), "SCRIPT_STYLE": ai_style, 
        "POST_TELEGRAM": str(tg), "POST_FACEBOOK": str(fb), "POST_INSTAGRAM": str(insta), 
        "POST_YOUTUBE": str(yt), "POST_TIKTOK": str(tk), "POST_WHATSAPP": str(wa) 
    }) 
    
    # Run production and yield logs + placeholders for video
    for logs, vid in stream_logs(env):
        yield logs, vid
    
    # After completion, try to find the generated video
    final_video = "final_video.mp4" 
    if os.path.exists(final_video):
        yield logs, final_video
    else:
        yield logs, None

# --- VISUAL THEME (CYBERPUNK) --- 
custom_css = """ 
body { background-color: #050505; color: #00ffcc; } 
.gradio-container { border: 2px solid #00ffcc !important; box-shadow: 0 0 20px #00ffcc44 !important; border-radius: 15px !important; } 
#log_box textarea { background: #000 !important; color: #0f0 !important; font-family: 'Courier New', monospace; border: 1px solid #0f0; } 
.stat-box { background: #111; border-radius: 10px; padding: 10px; border-left: 5px solid #ff3366; } 
h1 { text-shadow: 0 0 10px #ff3366; color: #ff3366 !important; } 
""" 

with gr.Blocks(title="Cinema Emperor V6") as demo: 
    gr.Markdown("# ☢️ CINEMA BOT COMMAND CENTER V6.0 ☢️") 
    
    with gr.Row(): 
        with gr.Column(): 
            gr.Markdown("### 🎙️ Settings") 
            voice_dd = gr.Dropdown(list(ARABIC_VOICES.keys()), label="Narrator", value="شاكر (مصر)") 
            speed_sl = gr.Slider(-50, 50, -10, step=5, label="Speed (%)") 
            quality = gr.Dropdown(["720p", "1080p", "4K"], label="Quality", value="1080p") 
            ai_temp = gr.Slider(0, 1, 0.7, label="AI Imagination") 
            ai_style = gr.Dropdown(["Dramatic", "Action", "Horror", "Documentary"], label="Tone", value="Dramatic") 
        
        with gr.Column(): 
            mode_rd = gr.Radio(["Auto", "Manual"], label="Mode", value="Auto") 
            m_title = gr.Textbox(label="Title") 
            m_trailer = gr.Textbox(label="Trailer URL") 
            m_overview = gr.Textbox(label="Overview", lines=3) 
            
            start_btn = gr.Button("🔥 INITIALIZE PRODUCTION 🔥", variant="primary") 
            log_out = gr.Textbox(label="Logs", lines=10) 
            vid_path_out = gr.Textbox(label="Video Path") 
            
    # --- WIRING (Test) --- 
    def test_fn(): return "System Initialized", "None"
    start_btn.click( 
        fn=test_fn, 
        inputs=[], 
        outputs=[log_out, vid_path_out] 
    ) 

if __name__ == "__main__": 
    demo.launch( 
        server_name="0.0.0.0", 
        server_port=7860, 
        show_api=False 
    ) 
