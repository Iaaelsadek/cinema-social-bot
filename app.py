import gradio as gr 
import os 
import subprocess 
import threading 
import sys 

def run_bot(): 
    try: 
        # Run main.py with FORCE_POST enabled 
        env = os.environ.copy() 
        env["FORCE_POST"] = "true" 
        result = subprocess.run([sys.executable, "main.py"], env=env, capture_output=True, text=True) 
        if result.returncode == 0: 
            return "✅ تم بنجاح!\n\n" + result.stdout 
        else: 
            return "❌ حدث خطأ:\n\n" + result.stderr 
    except Exception as e: 
        return str(e) 

with gr.Blocks(title="Cinema Social Bot Control") as demo: 
    gr.Markdown("# 🎬 لوحة تحكم Cinema Social Bot") 
    gr.Markdown("اضغط على الزر أدناه لتشغيل البوت، استخراج السكربت، والمونتاج فوراً.") 
    
    start_btn = gr.Button("🚀 تشغيل البوت وإنتاج فيديو الآن", variant="primary") 
    output_logs = gr.Textbox(label="سجل التشغيل (Logs)", lines=15) 
    
    start_btn.click(fn=run_bot, inputs=[], outputs=[output_logs]) 

if __name__ == "__main__": 
    demo.launch(server_name="0.0.0.0", server_port=7860)
