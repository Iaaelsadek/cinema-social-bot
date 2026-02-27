import gradio as gr 
import os 
import subprocess 
import sys 
import threading 

# Global state to manage the running process 
current_process = None 
LOG_FILE = "system_logs.txt" 

def cancel_process(): 
    """Kill switch to terminate the running bot.""" 
    global current_process 
    if current_process is not None and current_process.poll() is None: 
        current_process.terminate() 
        return "🛑 تم إرسال أمر الإيقاف بنجاح! جاري قتل العملية..." 
    return "ℹ️ لا توجد عملية قيد التشغيل حالياً." 

def clear_logs(): 
    """Clear the terminal screen and log file.""" 
    if os.path.exists(LOG_FILE): 
        open(LOG_FILE, 'w', encoding='utf-8').close() 
    return "", gr.update(value=None) 

def stream_logs(env_vars): 
    """Run the bot, stream logs line-by-line, and gather outputs.""" 
    global current_process 
    
    # 1. Install browser for Playwright (silent) 
    os.system("playwright install chromium") 
    
    # 2. Inject environment variables to CLEAN logs (disable TQDM progress bars) 
    env_vars["TQDM_DISABLE"] = "1" 
    env_vars["PYTHONUNBUFFERED"] = "1" 
    
    with open(LOG_FILE, "w", encoding="utf-8") as f: 
        f.write("🚀 بدء دورة التشغيل الجديدة...\n" + "="*50 + "\n") 
        
    process = subprocess.Popen( 
        [sys.executable, "main.py"], 
        env=env_vars, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.STDOUT, 
        text=True, 
        bufsize=1 
    ) 
    current_process = process 
    
    logs = "🚀 جاري تشغيل المكنة...\n" + "="*50 + "\n" 
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
        logs += "✅ تمت العملية بنجاح ساحق!\n" 
        
        # 3. Find generated assets for the UI 
        video_path = "output/final_reel.mp4" if os.path.exists("output/final_reel.mp4") else None 
        extracted_files = [] 
        if os.path.exists("temp"): 
            extracted_files = [os.path.join("temp", f) for f in os.listdir("temp") if f.endswith((".txt", ".mp3"))] 
        if video_path: extracted_files.append(video_path) 
        
        yield logs, gr.update(value=LOG_FILE), gr.update(value=video_path), gr.update(value=extracted_files if extracted_files else None) 
    else: 
        if return_code in (-15, 143): # Killed by user 
            logs += "🛑 تم إجهاض العملية بنجاح بواسطة المستخدم.\n" 
        else: 
            logs += f"❌ توقفت العملية بسبب خطأ (Code {return_code}). راجع السجل.\n" 
        yield logs, gr.update(value=LOG_FILE), gr.update(), gr.update() 

def run_auto_bot(tg, fb, insta, yt, tk, wa, voice): 
    env = os.environ.copy() 
    env.update({"FORCE_POST": "true", "VOICE_MODEL": voice}) 
    env.update({"POST_TELEGRAM": str(tg), "POST_FACEBOOK": str(fb), "POST_INSTAGRAM": str(insta), "POST_YOUTUBE": str(yt), "POST_TIKTOK": str(tk), "POST_WHATSAPP": str(wa)}) 
    yield from stream_logs(env) 

def run_manual_bot(movie_name, trailer_url, overview, tg, fb, insta, yt, tk, wa, voice): 
    env = os.environ.copy() 
    env.update({ 
        "FORCE_POST": "true", "MANUAL_MODE": "true", 
        "MANUAL_TITLE": movie_name, "MANUAL_TRAILER": trailer_url, "MANUAL_OVERVIEW": overview, "VOICE_MODEL": voice 
    }) 
    env.update({"POST_TELEGRAM": str(tg), "POST_FACEBOOK": str(fb), "POST_INSTAGRAM": str(insta), "POST_YOUTUBE": str(yt), "POST_TIKTOK": str(tk), "POST_WHATSAPP": str(wa)}) 
    yield from stream_logs(env) 

custom_css = """ 
#log_box textarea { background-color: #0d1117; color: #00ff00; font-family: 'Courier New', monospace; font-size: 14px; direction: ltr; text-align: left;} 
.gradio-container { font-family: 'Tajawal', sans-serif; } 
""" 

with gr.Blocks(title="Cinema Omni-Dashboard", css=custom_css, theme=gr.themes.Soft()) as demo: 
    gr.Markdown("<h1 style='text-align: center;'>🚀 غرفة عمليات Cinema Social Bot (V4.0 Pro)</h1>") 
    
    with gr.Row(): 
        with gr.Column(scale=2): 
            with gr.Tabs(): 
                with gr.TabItem("🤖 الإنتاج الآلي (Auto)"): 
                    gr.Markdown("يسحب أحدث فيلم من قاعدة البيانات وينتجه بالكامل.") 
                    auto_btn = gr.Button("بدء الإنتاج الآلي 🚀", variant="primary", size="lg") 
                    
                with gr.TabItem("🎯 الإنتاج اليدوي (Manual)"): 
                    m_title = gr.Textbox(label="اسم الفيلم") 
                    m_trailer = gr.Textbox(label="رابط إعلان يوتيوب (اختياري)") 
                    m_overview = gr.Textbox(label="ملخص القصة (اختياري)", lines=2) 
                    manual_btn = gr.Button("بدء الإنتاج اليدوي 🎯", variant="secondary", size="lg")
                    
    # Placeholder to satisfy the component logic if used elsewhere in full V4.0 UI
    # Note: The provided snippet ends abruptly. I will complete it to be functional.
    with gr.Row():
        with gr.Column():
            gr.Markdown("### 📡 منصات النشر")
            with gr.Row():
                tg = gr.Checkbox(label="Telegram", value=True)
                fb = gr.Checkbox(label="Facebook", value=True)
                insta = gr.Checkbox(label="Instagram", value=False)
            with gr.Row():
                yt = gr.Checkbox(label="YouTube", value=False)
                tk = gr.Checkbox(label="TikTok", value=False)
                wa = gr.Checkbox(label="WhatsApp", value=False)
            voice = gr.Dropdown(label="موديل الصوت", choices=["ar-EG-SalmaNeural", "ar-SA-ZariNeural", "ar-EG-ShakirNeural"], value="ar-EG-SalmaNeural")

    with gr.Row():
        with gr.Column(scale=3):
            log_box = gr.Textbox(label="سجل العملية (Live Logs)", lines=15, elem_id="log_box")
            with gr.Row():
                stop_btn = gr.Button("🛑 إيقاف فوري (Kill Switch)", variant="stop")
                clear_btn = gr.Button("🧹 تنظيف السجل")
                log_file_out = gr.File(label="تحميل السجل الكامل")

        with gr.Column(scale=2):
            video_out = gr.Video(label="معاينة الفيديو النهائي")
            files_out = gr.File(label="الأصول المستخرجة (Assets)", file_count="multiple")

    # Wire up buttons
    auto_btn.click(
        fn=run_auto_bot, 
        inputs=[tg, fb, insta, yt, tk, wa, voice], 
        outputs=[log_box, log_file_out, video_out, files_out]
    )
    manual_btn.click(
        fn=run_manual_bot, 
        inputs=[m_title, m_trailer, m_overview, tg, fb, insta, yt, tk, wa, voice], 
        outputs=[log_box, log_file_out, video_out, files_out]
    )
    stop_btn.click(fn=cancel_process, outputs=[log_box])
    clear_btn.click(fn=clear_logs, outputs=[log_box, log_file_out])

if __name__ == "__main__": 
    demo.launch(server_name="0.0.0.0", server_port=7860)
