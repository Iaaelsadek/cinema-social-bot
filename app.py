import gradio as gr 
import os 
import subprocess 
import sys 

LOG_FILE = "system_logs.txt" 
current_process = None 

def cancel_process(): 
    global current_process 
    if current_process is not None and current_process.poll() is None: 
        current_process.terminate() 
        return "🛑 تم تفعيل زر التدمير.. جاري إيقاف المكنة!" 
    return "ℹ️ لا توجد عملية حالية." 

def clear_logs(): 
    if os.path.exists(LOG_FILE): 
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            f.close() 
    return "", gr.update(value=None) 

def stream_logs(env_vars): 
    global current_process 
    # 1. Install browser for Playwright (silent)
    os.system("playwright install chromium") 
    
    # 2. Inject environment variables to CLEAN logs
    env_vars.update({"TQDM_DISABLE": "1", "PYTHONUNBUFFERED": "1"}) 
     
    with open(LOG_FILE, "w", encoding="utf-8") as f: 
        f.write("🚀 بدء نظام GOD-MODE...\n" + "="*50 + "\n") 
         
    process = subprocess.Popen(
        [sys.executable, "main.py"], 
        env=env_vars, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.STDOUT, 
        text=True, 
        bufsize=1
    ) 
    current_process = process 
     
    logs = "🚀 جاري الإقلاع...\n" 
    yield logs, gr.update(), gr.update(), gr.update() 
     
    for line in iter(process.stdout.readline, ''): 
        logs += line 
        with open(LOG_FILE, "a", encoding="utf-8") as f: 
            f.write(line) 
        yield logs, gr.update(), gr.update(), gr.update() 
         
    process.stdout.close() 
    return_code = process.wait() 
     
    logs += "\n" + "="*50 + "\n" 
    if return_code == 0: 
        logs += "✅ تمت العملية بنجاح أسطوري!\n" 
        video_path = "output/final_reel.mp4" if os.path.exists("output/final_reel.mp4") else None 
        files = []
        if os.path.exists("temp"):
            files = [os.path.join("temp", f) for f in os.listdir("temp") if f.endswith((".txt", ".mp3"))]
        if video_path: 
            files.append(video_path) 
        yield logs, gr.update(value=LOG_FILE), gr.update(value=video_path), gr.update(value=files if files else None) 
    else: 
        if return_code in (-15, 143): # Killed by user
            logs += "🛑 تم إجهاض العملية بنجاح بواسطة المستخدم.\n"
        else:
            logs += f"❌ توقف بسبب خطأ (Code {return_code}). راجع السجل.\n" 
        yield logs, gr.update(value=LOG_FILE), gr.update(), gr.update() 

def trigger_bot(mode, m_title, m_trailer, m_overview, lang, custom_prompt, voice, speed, bg_video, watermark, *socials): 
    env = os.environ.copy() 
    env.update({ 
        "FORCE_POST": "true", 
        "MANUAL_MODE": "true" if mode == "Manual" else "false", 
        "MANUAL_TITLE": m_title, 
        "MANUAL_TRAILER": m_trailer, 
        "MANUAL_OVERVIEW": m_overview, 
        "TARGET_LANG": lang, 
        "CUSTOM_PROMPT": custom_prompt, 
        "VOICE_MODEL": voice, 
        "VOICE_SPEED": str(speed), 
        "CUSTOM_BG_VIDEO": bg_video, 
        "CUSTOM_WATERMARK": watermark.name if watermark else "" 
    }) 
    social_keys = ["POST_TELEGRAM", "POST_FACEBOOK", "POST_INSTAGRAM", "POST_YOUTUBE", "POST_TIKTOK", "POST_WHATSAPP"] 
    for i, key in enumerate(social_keys): 
        env[key] = str(socials[i]) 
     
    yield from stream_logs(env) 

css = """
#log_box textarea { 
    background-color: #050505; 
    color: #00ffcc; 
    font-family: 'Courier New', monospace; 
    font-size: 13px; 
    direction: ltr; 
    text-align: left; 
    border: 1px solid #00ffcc;
}
.gradio-container { font-family: 'Tajawal', sans-serif; }
""" 

with gr.Blocks(title="Cinema God-Mode", css=css, theme=gr.themes.Dark()) as demo: 
    gr.Markdown("<h1 style='text-align: center; color: #ff5555;'>☢️ محطة فضاء Cinema Social Bot (GOD-MODE) ☢️</h1>") 
     
    with gr.Row(): 
        with gr.Column(scale=2): 
            with gr.Tabs(): 
                with gr.TabItem("🚀 الإنتاج (Production)"): 
                    mode_radio = gr.Radio(["Auto", "Manual"], label="وضع التشغيل", value="Auto") 
                    with gr.Group(visible=False) as manual_group: 
                        m_title = gr.Textbox(label="اسم الفيلم") 
                        m_trailer = gr.Textbox(label="رابط إعلان يوتيوب (اختياري)") 
                        m_overview = gr.Textbox(label="ملخص القصة (اختياري)", lines=2) 
                     
                    # Make manual inputs visible only when Manual is selected 
                    mode_radio.change(fn=lambda m: gr.update(visible=m=="Manual"), inputs=mode_radio, outputs=manual_group) 
                     
                    start_btn = gr.Button("🔥 إطلاق دورة الإنتاج الشاملة 🔥", variant="primary", size="lg") 
 
                with gr.TabItem("🧠 الذكاء الاصطناعي (AI & Lang)"): 
                    lang_dd = gr.Dropdown(["العربية", "English", "Español", "Français"], label="لغة الفيديو", value="العربية") 
                    custom_prompt = gr.Textbox(label="تعديل الموجه الأساسي (Boss Prompt Override)", lines=5, placeholder="اترك هذا فارغاً لاستخدام الموجه الافتراضي...") 
                 
                with gr.TabItem("🎬 المونتاج والهوية (Video & Audio)"): 
                    with gr.Row(): 
                        voice_dd = gr.Dropdown(["ar-EG-ShakirNeural", "ar-AE-HamdanNeural", "ar-SA-HamedNeural", "ar-EG-SalmaNeural", "ar-SA-ZariNeural"], label="المعلق الصوتي", value="ar-EG-ShakirNeural") 
                        speed_slider = gr.Slider(-50, 50, value=0, step=5, label="سرعة الصوت (%)") 
                    bg_video = gr.Textbox(label="رابط فيديو خلفية مخصص (اختياري)", placeholder=" `https://youtube.com/watch?v=` ...") 
                    watermark = gr.File(label="رفع لوجو / علامة مائية (PNG)")

                with gr.TabItem("🌍 التوزيع (Distribution)"): 
                    gr.Markdown("حدد المنصات التي سيتم النشر عليها فور انتهاء الرندر:") 
                    with gr.Row(): 
                        tg_cb = gr.Checkbox(label="Telegram", value=True) 
                        fb_cb = gr.Checkbox(label="Facebook") 
                        insta_cb = gr.Checkbox(label="Instagram") 
                    with gr.Row(): 
                        yt_cb = gr.Checkbox(label="YouTube Shorts") 
                        tk_cb = gr.Checkbox(label="TikTok") 
                        wa_cb = gr.Checkbox(label="WhatsApp") 
 
            gr.Markdown("### 🖥️ شاشة المراقبة النووية (Live Terminal)") 
            log_output = gr.Textbox(label="", lines=18, max_lines=25, interactive=False, elem_id="log_box", show_copy_button=True) 
             
            with gr.Row(): 
                kill_btn = gr.Button("🛑 تدمير العملية (Kill)", variant="stop") 
                clear_btn = gr.Button("🧹 مسح الشاشة") 
                download_log_btn = gr.DownloadButton("📥 تحميل اللوج") 
 
        with gr.Column(scale=1): 
            gr.Markdown("### 🍿 صالة العرض (Studio)") 
            video_preview = gr.Video(label="الفيديو النهائي", interactive=False) 
            assets_files = gr.File(label="📂 الملفات الخام (صوت/نص)", interactive=False) 

    # Wire up buttons
    start_btn.click( 
        trigger_bot, 
        inputs=[
            mode_radio, m_title, m_trailer, m_overview, 
            lang_dd, custom_prompt, 
            voice_dd, speed_slider, bg_video, watermark, 
            tg_cb, fb_cb, insta_cb, yt_cb, tk_cb, wa_cb
        ], 
        outputs=[log_output, download_log_btn, video_preview, assets_files] 
    ) 
    kill_btn.click(cancel_process, outputs=[log_output]) 
    clear_btn.click(clear_logs, outputs=[log_output, download_log_btn]) 
 
if __name__ == "__main__": 
    demo.launch(server_name="0.0.0.0", server_port=7860)
