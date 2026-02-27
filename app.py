import gradio as gr 
import os 
import subprocess 
import threading 
import sys 
import json
from datetime import datetime
import pandas as pd

# Global state for logs
logs_storage = []

def run_bot(force_post=True): 
    try: 
        # Run main.py with FORCE_POST enabled 
        env = os.environ.copy() 
        if force_post:
            env["FORCE_POST"] = "true" 
        
        process = subprocess.Popen(
            [sys.executable, "main.py"], 
            env=env, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        output = ""
        for line in process.stdout:
            output += line
            yield output
            
        process.wait()
        if process.returncode == 0: 
            yield output + "\n\n✅ تم بنجاح!"
        else: 
            yield output + f"\n\n❌ حدث خطأ (Exit Code: {process.returncode})"
    except Exception as e: 
        yield str(e)

def get_env_vars():
    vars_to_show = [
        "TMDB_API_KEY", "GEMINI_API_KEY", "PEXELS_API_KEY", 
        "FB_PAGE_TOKEN", "FB_PAGE_ID", "SUPABASE_URL", "SUPABASE_KEY",
        "POST_TELEGRAM", "POST_FACEBOOK", "POST_INSTAGRAM", "POST_YOUTUBE", "POST_TIKTOK", "POST_WHATSAPP"
    ]
    return {v: os.environ.get(v, "") for v in vars_to_show}

def get_viral_queue():
    if os.path.exists("viral_queue.json"):
        try:
            with open("viral_queue.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return pd.DataFrame(data)
        except Exception as e:
            return pd.DataFrame([{"Error": str(e)}])
    return pd.DataFrame(columns=["title", "url", "status"])

def get_output_files():
    files = []
    if os.path.exists("output"):
        for f in os.listdir("output"):
            if f.endswith(".mp4"):
                path = os.path.join("output", f)
                stats = os.stat(path)
                files.append({
                    "Name": f,
                    "Size": f"{stats.st_size / (1024*1024):.2f} MB",
                    "Created": datetime.fromtimestamp(stats.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
                })
    if not files:
        return pd.DataFrame(columns=["Name", "Size", "Created"])
    return pd.DataFrame(files)

# Gradio UI
with gr.Blocks(title="Cinema Social Bot CMS v3.0", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🎬 Cinema Social Bot: The Nuclear Upgrade (CMS v3.0)")
    
    with gr.Tabs():
        # Tab 1: Dashboard
        with gr.Tab("🚀 Control Center"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### 🤖 Bot Controls")
                    force_post_cb = gr.Checkbox(label="Force Post (تجاوز الجدولة)", value=True)
                    start_btn = gr.Button("🚀 Run Bot Now", variant="primary")
                
                with gr.Column(scale=3):
                    gr.Markdown("### 📜 Real-time Logs")
                    output_logs = gr.Textbox(label="Terminal Output", lines=20, interactive=False)
            
            start_btn.click(fn=run_bot, inputs=[force_post_cb], outputs=[output_logs])

        # Tab 2: Dispatcher Settings
        with gr.Tab("🌍 Omni-Channel Dispatcher"):
            gr.Markdown("### 📡 Platform Publishing Settings")
            with gr.Row():
                post_tg = gr.Checkbox(label="Telegram", value=os.environ.get("POST_TELEGRAM") == "True")
                post_fb = gr.Checkbox(label="Facebook Reels", value=os.environ.get("POST_FACEBOOK") == "True")
                post_ig = gr.Checkbox(label="Instagram Reels", value=os.environ.get("POST_INSTAGRAM") == "True")
            with gr.Row():
                post_yt = gr.Checkbox(label="YouTube Shorts", value=os.environ.get("POST_YOUTUBE") == "True")
                post_tk = gr.Checkbox(label="TikTok", value=os.environ.get("POST_TIKTOK") == "True")
                post_wa = gr.Checkbox(label="WhatsApp", value=os.environ.get("POST_WHATSAPP") == "True")
            
            save_dispatcher_btn = gr.Button("💾 Save Dispatcher Settings")
            dispatcher_status = gr.Markdown("")

            def update_dispatcher(tg, fb, ig, yt, tk, wa):
                os.environ["POST_TELEGRAM"] = "True" if tg else "False"
                os.environ["POST_FACEBOOK"] = "True" if fb else "False"
                os.environ["POST_INSTAGRAM"] = "True" if ig else "False"
                os.environ["POST_YOUTUBE"] = "True" if yt else "False"
                os.environ["POST_TIKTOK"] = "True" if tk else "False"
                os.environ["POST_WHATSAPP"] = "True" if wa else "False"
                return "✅ Dispatcher settings updated for current session!"

            save_dispatcher_btn.click(
                fn=update_dispatcher, 
                inputs=[post_tg, post_fb, post_ig, post_yt, post_tk, post_wa], 
                outputs=[dispatcher_status]
            )

        # Tab 3: Content Manager
        with gr.Tab("📁 Content Explorer"):
            gr.Markdown("### 🎥 Generated Videos (output/)")
            output_df = gr.DataFrame(value=get_output_files(), interactive=False)
            refresh_btn = gr.Button("🔄 Refresh Explorer")
            refresh_btn.click(fn=get_output_files, outputs=[output_df])

        # Tab 4: Viral Queue
        with gr.Tab("🔥 Viral Queue"):
            gr.Markdown("### 📈 Pending Viral Content")
            queue_df = gr.DataFrame(value=get_viral_queue(), interactive=False)
            refresh_queue_btn = gr.Button("🔄 Refresh Queue")
            refresh_queue_btn.click(fn=get_viral_queue, outputs=[queue_df])

        # Tab 5: API Settings
        with gr.Tab("🔑 API Credentials"):
            gr.Markdown("### ⚙️ Environment Configuration")
            with gr.Row():
                tmdb_key = gr.Textbox(label="TMDB API Key", value=os.environ.get("TMDB_API_KEY", ""), type="password")
                gemini_key = gr.Textbox(label="Gemini API Key", value=os.environ.get("GEMINI_API_KEY", ""), type="password")
            with gr.Row():
                supabase_url = gr.Textbox(label="Supabase URL", value=os.environ.get("SUPABASE_URL", ""))
                supabase_key = gr.Textbox(label="Supabase Key", value=os.environ.get("SUPABASE_KEY", ""), type="password")
            
            save_api_btn = gr.Button("💾 Save API Settings")
            api_status = gr.Markdown("")

            def update_api_settings(tmdb, gemini, sub_url, sub_key):
                os.environ["TMDB_API_KEY"] = tmdb
                os.environ["GEMINI_API_KEY"] = gemini
                os.environ["SUPABASE_URL"] = sub_url
                os.environ["SUPABASE_KEY"] = sub_key
                return "✅ API Credentials updated for current session!"

            save_api_btn.click(
                fn=update_api_settings, 
                inputs=[tmdb_key, gemini_key, supabase_url, supabase_key], 
                outputs=[api_status]
            )

if __name__ == "__main__": 
    demo.launch(server_name="0.0.0.0", server_port=7860)
