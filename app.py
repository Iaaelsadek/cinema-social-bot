import gradio as gr 
import os 
import subprocess 
import sys 

LOG_FILE = "system_logs.txt" 
current_process = None 

def get_logs(): 
    if os.path.exists(LOG_FILE): 
        with open(LOG_FILE, "r", encoding="utf-8") as f: 
            return f.read() 
    return "لا توجد سجلات بعد..." 

def run_bot(m_title, m_trailer, m_overview): 
    global current_process 
    
    # 1. تجهيز بيئة العمل الأساسية 
    env = os.environ.copy() 
    env["FORCE_POST"] = "true" 
    env["PYTHONUNBUFFERED"] = "1" 
    
    # 2. تحديد نوع التشغيل (آلي أو يدوي) 
    if m_title and m_title.strip() != "": 
        env["MANUAL_MODE"] = "true" 
        env["MANUAL_TITLE"] = m_title 
        env["MANUAL_TRAILER"] = m_trailer 
        env["MANUAL_OVERVIEW"] = m_overview 
    else: 
        env["MANUAL_MODE"] = "false" 

    # 3. إعدادات ثابتة (عشان نتجنب أي إيرور من الواجهة) 
    env["VOICE_MODEL"] = "ar-EG-ShakirNeural" 
    env["VOICE_SPEED"] = "-10" 
    env["POST_TELEGRAM"] = "True" 

    # 4. تشغيل المكنة 
    os.system("playwright install chromium") 
    
    with open(LOG_FILE, "w", encoding="utf-8") as f: 
        f.write("🚀 جاري بدء تشغيل البوت...\n") 
        
    current_process = subprocess.Popen( 
        [sys.executable, "main.py"], 
        env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1 
    ) 
    
    # قراءة السجلات سطر بسطر 
    logs = "" 
    for line in iter(current_process.stdout.readline, ''): 
        logs += line 
        yield logs, gr.update() 
        
    current_process.wait() 
    
    # جلب الفيديو لو خلص 
    vid_path = "output/final_reel.mp4" 
    if os.path.exists(vid_path): 
        yield logs + "\n✅ تمت العملية بنجاح!", gr.update(value=vid_path) 
    else: 
        yield logs + "\n❌ انتهت العملية ولكن لم يتم العثور على فيديو.", gr.update() 


# ===================================================================== 
# THE SAFEST UI POSSIBLE FOR GRADIO 5 (NO ACCORDIONS, NO SLIDERS, NO CHECKBOXES) 
# ===================================================================== 
with gr.Blocks(title="Cinema Social Bot") as demo: 
    gr.Markdown("# 🎬 Cinema Social Bot") 
    gr.Markdown("اكتب اسم الفيلم للإنتاج اليدوي، أو اترك الخانة فارغة للإنتاج الآلي.") 
    
    # مدخلات بسيطة جداً (Textboxes فقط لتجنب أي Schema Errors) 
    movie_title = gr.Textbox(label="اسم الفيلم (اختياري)") 
    movie_trailer = gr.Textbox(label="رابط إعلان يوتيوب (اختياري)") 
    movie_overview = gr.Textbox(label="ملخص القصة (اختياري)", lines=2) 
    
    # زر التشغيل 
    run_btn = gr.Button("🚀 تشغيل البوت الآن", variant="primary") 
    
    # المخرجات 
    log_output = gr.Textbox(label="سجل العمليات (Logs)", lines=15) 
    video_output = gr.Video(label="الفيديو النهائي") 

    # ربط الزر بالدالة 
    run_btn.click( 
        fn=run_bot, 
        inputs=[movie_title, movie_trailer, movie_overview], 
        outputs=[log_output, video_output], 
        api_name=False # إغلاق الـ API لمنع الـ Schema builder من فحص الكود 
    ) 

if __name__ == "__main__": 
    demo.launch(server_name="0.0.0.0", server_port=7860, show_api=False)
