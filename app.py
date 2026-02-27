import gradio as gr 
import os 
import subprocess 
import sys 

LOG_FILE = "system_logs.txt" 

def stream_logs(env_vars): 
    os.system("playwright install chromium") 
    env_vars["PYTHONUNBUFFERED"] = "1" 
    
    with open(LOG_FILE, "w", encoding="utf-8") as f: 
        f.write("🚀 Starting Cinema Bot (Safe Mode)...\n") 
        
    process = subprocess.Popen( 
        [sys.executable, "main.py"], 
        env=env_vars, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1 
    ) 
    
    logs = "" 
    for line in iter(process.stdout.readline, ''): 
        logs += line 
        yield logs, gr.update() 
    process.wait() 

def safe_launch(movie_title, trailer_url, voice_speed): 
    env = os.environ.copy() 
    env.update({ 
        "FORCE_POST": "true", 
        "POST_TELEGRAM": "True", 
        "VOICE_MODEL": "ar-EG-ShakirNeural", 
        "VOICE_SPEED": str(voice_speed) 
    }) 
    
    if movie_title.strip() != "": 
        env["MANUAL_MODE"] = "true" 
        env["MANUAL_TITLE"] = movie_title 
        env["MANUAL_TRAILER"] = trailer_url 
    else: 
        env["MANUAL_MODE"] = "false" 
        
    yield from stream_logs(env) 

# ULTRA SIMPLE UI - NO TABS, NO ACCORDIONS, NO CHECKBOXES 
with gr.Blocks(title="Cinema Bot Safe Mode") as demo: 
    gr.Markdown("# 🎬 Cinema Social Bot (Safe Mode)") 
    gr.Markdown("⚠️ *Running in Safe Mode due to Gradio 5 schema bugs.* Leave 'Movie Title' blank for AUTO mode.") 
    
    m_title = gr.Textbox(label="Movie Title (Leave blank for Auto Mode)") 
    m_trailer = gr.Textbox(label="Trailer URL (Optional)") 
    v_speed = gr.Textbox(label="Voice Speed (e.g., -10, 0, 10)", value="-10") 
    
    start_btn = gr.Button("🚀 START PRODUCTION", variant="primary") 
    
    log_out = gr.Textbox(label="System Logs", lines=15) 
    vid_prev = gr.Video(label="Output") 

    start_btn.click( 
        fn=safe_launch, 
        inputs=[m_title, m_trailer, v_speed], 
        outputs=[log_out, vid_prev] 
    ) 

if __name__ == "__main__": 
    demo.launch(server_name="0.0.0.0", server_port=7860)
