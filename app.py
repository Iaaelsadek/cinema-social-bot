import gradio as gr 
import os 
import subprocess 
import sys 
import asyncio 
import edge_tts 

# --- SYSTEM GLOBALS --- 
LOG_FILE = "system_logs.txt" 
current_process = None 

# All Arabic Voices in Edge-TTS 
ARABIC_VOICES = [ 
    "ar-EG-ShakirNeural", "ar-EG-SalmaNeural", 
    "ar-SA-HamedNeural", "ar-SA-ZariyahNeural", 
    "ar-AE-HamdanNeural", "ar-AE-FatimaNeural", 
    "ar-QA-AmalNeural", "ar-QA-MoazNeural", 
    "ar-KW-AliNeural", "ar-KW-ReemNeural", 
    "ar-SY-BasselNeural", "ar-SY-AmanyNeural",
    "ar-DZ-AminaNeural", "ar-DZ-IsmaelNeural",
    "ar-BH-AliNeural", "ar-BH-LailaNeural",
    "ar-IQ-BasselNeural", "ar-IQ-RanaNeural",
    "ar-JO-SanaNeural", "ar-JO-TaimNeural",
    "ar-LB-LaylaNeural", "ar-LB-RamiNeural",
    "ar-LY-ImanNeural", "ar-LY-OmarNeural",
    "ar-MA-MounaNeural", "ar-MA-JamalNeural",
    "ar-OM-AbdullahNeural", "ar-OM-AyshaNeural",
    "ar-PS-HaniNeural", "ar-PS-RayaNeural",
    "ar-TN-HediNeural", "ar-TN-ReemNeural",
    "ar-YE-MaryamNeural", "ar-YE-SalehNeural"
] 

# --- ASYNC VOICE PREVIEW GENERATOR --- 
async def generate_sample(voice): 
    text = "أهلاً بك يا سيدي في غرفة التحكم المركزية. أنا جاهز للعمل على إنتاج فيديوهاتك بأعلى جودة ممكنة." 
    output_file = f"sample_{voice}.mp3" 
    communicate = edge_tts.Communicate(text, voice) 
    await communicate.save(output_file) 
    return output_file 

def preview_voice(voice): 
    if not voice: return None 
    try: 
        # Run async synchronously safely using a more standard approach for Gradio
        # Using asyncio.run() directly is cleaner if not already in a loop
        import asyncio
        sample_path = asyncio.run(generate_sample(voice))
        return str(sample_path) # Force string return to avoid schema issues
    except Exception as e: 
        print(f"Error generating preview: {e}")
        return None 

# --- PROCESS MANAGEMENT --- 
def cancel_process(): 
    global current_process 
    if current_process is not None and current_process.poll() is None: 
        current_process.terminate() 
        return "🛑 تم إرسال أمر الإيقاف. المكنة تتوقف الآن!" 
    return "ℹ️ لا توجد عملية قيد التشغيل حالياً." 

def clear_logs(): 
    if os.path.exists(LOG_FILE): open(LOG_FILE, 'w', encoding='utf-8').close() 
    return "", gr.update(value=None) 

def stream_logs(env_vars): 
    global current_process 
    # Install playwright browser if not exists
    os.system("playwright install chromium") 
    env_vars.update({"TQDM_DISABLE": "1", "PYTHONUNBUFFERED": "1"}) 
    
    with open(LOG_FILE, "w", encoding="utf-8") as f: 
        f.write("🚀 جاري تهيئة نظام الإمبراطور V5.0...\n" + "="*50 + "\n") 
        
    process = subprocess.Popen([sys.executable, "main.py"], env=env_vars, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1) 
    current_process = process 
    
    logs = "🚀 الإقلاع بدأ...\n" 
    yield logs, gr.update(), gr.update(), gr.update() 
    
    for line in iter(process.stdout.readline, ''): 
        logs += line 
        with open(LOG_FILE, "a", encoding="utf-8") as f: f.write(line) 
        yield logs, gr.update(), gr.update(), gr.update() 
        
    process.stdout.close() 
    return_code = process.wait() 
    
    logs += "\n" + "="*50 + "\n" 
    if return_code == 0: 
        logs += "✅ تمت العملية بنجاح ساحق!\n" 
        video_path = "output/final_reel.mp4" if os.path.exists("output/final_reel.mp4") else None 
        files = []
        if os.path.exists("temp"):
            files = [os.path.join("temp", f) for f in os.listdir("temp") if f.endswith((".txt", ".mp3"))]
        if video_path: files.append(video_path) 
        yield logs, gr.update(value=LOG_FILE), gr.update(value=video_path), gr.update(value=files if files else None) 
    else: 
        logs += f"❌ توقف بسبب خطأ (Code {return_code}).\n" 
        yield logs, gr.update(value=LOG_FILE), gr.update(), gr.update() 

def master_launcher(mode, m_title, m_trailer, m_overview, tg, fb, insta, yt, tk, wa, voice, speed, quality, sub_color, temp): 
    env = os.environ.copy() 
    env.update({ 
        "FORCE_POST": "true", 
        "MANUAL_MODE": "true" if mode == "Manual" else "false", 
        "MANUAL_TITLE": m_title, 
        "MANUAL_TRAILER": m_trailer, 
        "MANUAL_OVERVIEW": m_overview, 
        "VOICE_MODEL": voice, 
        "VOICE_SPEED": str(speed), 
        "VIDEO_QUALITY": quality, 
        "SUB_COLOR": sub_color, 
        "AI_TEMP": str(temp), 
        "POST_TELEGRAM": str(tg), 
        "POST_FACEBOOK": str(fb), 
        "POST_INSTAGRAM": str(insta), 
        "POST_YOUTUBE": str(yt), 
        "POST_TIKTOK": str(tk), 
        "POST_WHATSAPP": str(wa) 
    }) 
    yield from stream_logs(env) 

# --- MIND-BLOWING CSS --- 
css = """ 
body { background-color: #0b0f19; color: #ffffff; } 
.gradio-container { font-family: 'Tajawal', sans-serif; max-width: 100% !important; } 
#log_box textarea { 
    background-color: #050505 !important; 
    color: #00ffcc !important; 
    font-family: 'Courier New', monospace; 
    font-size: 14px; 
    border: 2px solid #00ffcc; 
    box-shadow: 0 0 10px #00ffcc33;
} 
.sidebar { border-left: 1px solid #333; padding-left: 15px; } 
h1 { 
    text-align: center; 
    color: #ff3366; 
    text-shadow: 0 0 20px #ff336688; 
    margin-bottom: 30px; 
    font-size: 2.5em;
} 
.launch-btn { 
    background: linear-gradient(90deg, #ff3366, #ff9933) !important; 
    border: none !important; 
    color: white !important; 
    font-size: 20px !important; 
    font-weight: bold !important; 
    box-shadow: 0 0 15px #ff336688 !important;
    padding: 15px !important;
}
""" 

# --- THE UI ARCHITECTURE --- 
with gr.Blocks(title="Cinema Emperor Dashboard", css=css, theme=gr.themes.Monochrome()) as demo: 
    gr.Markdown("<h1>👑 غرفة عمليات Cinema Social Bot (إصدار الإمبراطور V5.0) 👑</h1>") 
    
    with gr.Row(): 
        # LEFT COLUMN: THE ENGINE & LOGS (Scale 3) 
        with gr.Column(scale=3): 
            with gr.Tabs(): 
                with gr.TabItem("🤖 وضع الإنتاج (Production Mode)"): 
                    mode_radio = gr.Radio(["Auto", "Manual"], label="اختر أسلوب عمل البوت", value="Auto", info="الآلي يسحب من قاعدة البيانات، اليدوي يسمح لك بتحديد الفيلم.") 
                    
                    with gr.Group(visible=False) as manual_group: 
                        gr.Markdown("### 🎯 إعدادات الإنتاج اليدوي") 
                        with gr.Row(): 
                            m_title = gr.Textbox(label="اسم الفيلم / المسلسل", placeholder="مثال: Interstellar") 
                            m_trailer = gr.Textbox(label="رابط إعلان يوتيوب", placeholder="لتحسين السكربت (اختياري)") 
                        m_overview = gr.Textbox(label="ملخص القصة", lines=2, placeholder="ضع ملخصاً أو اتركه لجيميناي (اختياري)") 
                    
                    mode_radio.change(fn=lambda m: gr.update(visible=m=="Manual"), inputs=mode_radio, outputs=manual_group) 
                    
                    start_btn = gr.Button("🚀 إطـــلاق الـمـكـنـــة الآن 🚀", elem_classes="launch-btn", size="lg") 

            gr.Markdown("### 🖥️ شاشة المراقبة المركزية (Live Cyber-Terminal)") 
            log_output = gr.Textbox(label="", lines=18, max_lines=25, interactive=False, elem_id="log_box") 
            
            with gr.Row(): 
                kill_btn = gr.Button("� تدمير العملية (Kill)", variant="stop") 
                clear_btn = gr.Button("🧹 تنظيف الشاشة") 
                download_log_btn = gr.DownloadButton("📥 تحميل السجل") 
                
            gr.Markdown("### 🎬 المخرجات (Studio Outputs)") 
            with gr.Row(): 
                video_preview = gr.Video(label="معاينة الفيديو النهائي", interactive=False) 
                assets_files = gr.File(label="📂 الملفات الخام (صوت ونص)", interactive=False) 

        # RIGHT COLUMN: THE STICKY SIDEBAR (Scale 1) 
        with gr.Column(scale=1, elem_classes="sidebar"): 
            gr.Markdown("## 🎛️ لوحة الإعدادات الشاملة") 
            
            with gr.Accordion("🎙️ استوديو الصوتيات (Edge-TTS)", open=True): 
                voice_dd = gr.Dropdown(ARABIC_VOICES, label="اختر المعلق الصوتي", value="ar-EG-ShakirNeural") 
                audio_preview = gr.Audio(label="🎧 عينة صوتية للمعلق", type="filepath", interactive=False, autoplay=True) 
                # Auto-generate voice sample when dropdown changes 
                voice_dd.change(fn=preview_voice, inputs=voice_dd, outputs=audio_preview) 
                speed_slider = gr.Slider(-50, 50, value=-10, step=5, label="سرعة النطق (%)") 
                
            with gr.Accordion("🌍 منصات النشر (Social Dispatcher)", open=True): 
                tg_cb = gr.Checkbox(label="✈️ Telegram", value=True) 
                fb_cb = gr.Checkbox(label="📘 Facebook Reels") 
                insta_cb = gr.Checkbox(label="📸 Instagram Reels") 
                yt_cb = gr.Checkbox(label="🟥 YouTube Shorts") 
                tk_cb = gr.Checkbox(label="🎵 TikTok") 
                wa_cb = gr.Checkbox(label="💬 WhatsApp") 
                
            with gr.Accordion("🎨 المونتاج والرؤية (Video Engine)", open=False): 
                quality_dd = gr.Dropdown(["720p", "1080p", "4K (بطيء)"], label="جودة الرندر", value="1080p", multiselect=False) 
                sub_color = gr.ColorPicker(label="لون الترجمة (Subtitles)", value="#FFFF00", interactive=True) 
                
            with gr.Accordion("� عقل الذكاء الاصطناعي (AI Settings)", open=False): 
                temp_slider = gr.Slider(0.0, 1.0, value=0.7, step=0.1, label="درجة الإبداع (Temperature)", info="0 يعني دقيق وصارم، 1 يعني خيالي ومبدع.") 

    # Wiring up the launch button to pass all 15 arguments 
    start_btn.click( 
        master_launcher, 
        inputs=[mode_radio, m_title, m_trailer, m_overview, tg_cb, fb_cb, insta_cb, yt_cb, tk_cb, wa_cb, voice_dd, speed_slider, quality_dd, sub_color, temp_slider], 
        outputs=[log_output, download_log_btn, video_preview, assets_files] 
    ) 
    kill_btn.click(cancel_process, outputs=[log_output]) 
    clear_btn.click(clear_logs, outputs=[log_output, download_log_btn]) 

if __name__ == "__main__": 
    demo.launch(server_name="0.0.0.0", server_port=7860)
