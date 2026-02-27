import gradio as gr 
import os 
import subprocess 
import sys 
import asyncio 
import edge_tts 
import psutil 

# --- CONFIGURATION & VOICES --- 
ARABIC_VOICES = { 
    "شاكر (مصر)": "ar-EG-ShakirNeural", "سلمى (مصر)": "ar-EG-SalmaNeural", 
    "حامد (السعودية)": "ar-SA-HamedNeural", "زارينا (السعودية)": "ar-SA-ZariyahNeural", 
    "حمدان (الإمارات)": "ar-AE-HamdanNeural", "فاطمة (الإمارات)": "ar-AE-FatimaNeural", 
    "باسم (سوريا)": "ar-SY-BasselNeural", "بشرى (اليمن)": "ar-YE-MaryamNeural" 
} 

LOG_FILE = "system_logs.txt" 

def get_sys_info(): 
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
    os.system("playwright install chromium") 
    env_vars["PYTHONUNBUFFERED"] = "1" 
    
    with open(LOG_FILE, "w", encoding="utf-8") as f: 
        f.write("🚀 Starting Cinema Bot V6.0 (Gradio 5 Engine)...\n") 
        
    process = subprocess.Popen( 
        [sys.executable, "main.py"], 
        env=env_vars, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1 
    ) 
    
    logs = "" 
    for line in iter(process.stdout.readline, ''): 
        logs += line 
        yield logs, gr.update() 
    process.wait() 

def master_launch(mode, m_title, m_trailer, m_overview, tg, fb, insta, yt, tk, wa, voice_key, speed, quality, ai_temp, ai_style): 
    env = os.environ.copy() 
    env.update({ 
        "FORCE_POST": "true", 
        "MANUAL_MODE": "true" if mode == "Manual" else "false", 
        "MANUAL_TITLE": m_title, "MANUAL_TRAILER": m_trailer, "MANUAL_OVERVIEW": m_overview, 
        "VOICE_MODEL": ARABIC_VOICES[voice_key], "VOICE_SPEED": str(speed), 
        "VIDEO_QUALITY": quality, "AI_TEMP": str(ai_temp), "SCRIPT_STYLE": ai_style, 
        "POST_TELEGRAM": str(tg), "POST_FACEBOOK": str(fb), "POST_INSTAGRAM": str(insta), 
        "POST_YOUTUBE": str(yt), "POST_TIKTOK": str(tk), "POST_WHATSAPP": str(wa) 
    }) 
    yield from stream_logs(env) 

# --- VISUAL THEME (CYBERPUNK) --- 
custom_css = """ 
body { background-color: #050505; color: #00ffcc; } 
.gradio-container { border: 2px solid #00ffcc !important; box-shadow: 0 0 20px #00ffcc44 !important; border-radius: 15px !important; } 
#log_box textarea { background: #000 !important; color: #0f0 !important; font-family: 'Courier New', monospace; border: 1px solid #0f0; } 
h1 { text-align: center; text-shadow: 0 0 10px #ff3366; color: #ff3366 !important; } 
""" 

with gr.Blocks(title="Cinema Emperor V6", css=custom_css) as demo: 
    gr.Markdown("<h1>☢️ CINEMA BOT COMMAND CENTER V6.0 ☢️</h1>") 
    
    with gr.Row(): 
        with gr.Column(scale=1): 
            sys_mon = gr.Textbox(value=get_sys_info(), label="System Status", interactive=False) 
            
            with gr.Accordion("🌍 Social Dispatch", open=True): 
                tg_cb = gr.Checkbox(label="Telegram", value=True) 
                fb_cb = gr.Checkbox(label="Facebook Reels", value=False) 
                insta_cb = gr.Checkbox(label="Instagram Reels", value=False) 
                yt_cb = gr.Checkbox(label="YouTube Shorts", value=False) 
                tk_cb = gr.Checkbox(label="TikTok", value=False) 
                wa_cb = gr.Checkbox(label="WhatsApp", value=False) 
            
            with gr.Accordion("🎙️ Voice Lab", open=True): 
                voice_dd = gr.Dropdown(choices=list(ARABIC_VOICES.keys()), label="Select Narrator", value="شاكر (مصر)") 
                audio_prev = gr.Audio(label="Live Preview", interactive=False) 
                voice_dd.change(fn=preview_voice, inputs=voice_dd, outputs=audio_prev) 
                speed_sl = gr.Slider(minimum=-50.0, maximum=50.0, value=-10.0, step=5.0, label="Voice Speed (%)") 
        
        with gr.Column(scale=2): 
            mode_rd = gr.Radio(choices=["Auto", "Manual"], label="Production Mode", value="Auto") 
            with gr.Accordion("🎯 Manual Override Data", open=True): 
                m_title = gr.Textbox(label="Movie Title") 
                m_trailer = gr.Textbox(label="Trailer URL") 
                m_overview = gr.Textbox(label="Overview", lines=3) 
                    
            start_btn = gr.Button("🔥 INITIALIZE PRODUCTION 🔥", variant="primary", size="lg") 
            log_out = gr.Textbox(label="Cyber Terminal Logs", lines=15, elem_id="log_box") 
            
        with gr.Column(scale=1): 
            with gr.Accordion("⚙️ AI & Video Tweaks", open=True): 
                quality = gr.Dropdown(choices=["720p", "1080p", "4K"], label="Quality", value="1080p") 
                ai_temp = gr.Slider(minimum=0.0, maximum=1.0, value=0.7, step=0.1, label="AI Imagination") 
                ai_style = gr.Dropdown(choices=["Dramatic", "Action", "Horror", "Documentary"], label="Script Tone", value="Dramatic")
            
            gr.Markdown("### 🎬 Studio Preview") 
            vid_prev = gr.Video(label="Final Output")

    # --- WIRING --- 
    start_btn.click( 
        fn=master_launch, 
        inputs=[mode_rd, m_title, m_trailer, m_overview, tg_cb, fb_cb, insta_cb, yt_cb, tk_cb, wa_cb, voice_dd, speed_sl, quality, ai_temp, ai_style], 
        outputs=[log_out, vid_prev] 
    ) 

if __name__ == "__main__": 
    demo.launch( 
        server_name="0.0.0.0", 
        server_port=7860, 
        show_api=False 
    ) 
