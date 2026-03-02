import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
import yt_dlp
import asyncio
import edge_tts
import re
import os
import threading

# --- 1. SETUP ---
st.set_page_config(page_title="SHRUTA", layout="wide")

try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=API_KEY)
    available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    target_model = next((m for m in available_models if "flash" in m), available_models[0])
    model = genai.GenerativeModel(target_model)
except Exception as e:
    st.error(f"API Key Error: {e}")
    st.stop()

# --- 2. EXTRACTION ---
def get_yt_text_pro(url):
    ydl_opts = {'skip_download': True, 'quiet': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return f"Title: {info.get('title')}. Extracting transcript metadata..."
    except: return "BLOCKED"

def make_audio(text, lang):
    v_map = {"English": "en-US-AriaNeural", "Hindi": "hi-IN-SwaraNeural", "Telugu": "te-IN-ShrutiNeural"}
    clean_text = re.sub(r'[*_#`\-]', '', text)
    async def amain():
        await edge_tts.Communicate(clean_text, v_map.get(lang, "en-US-AriaNeural")).save("lecture_voice.mp3")
    new_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(new_loop)
    new_loop.run_until_complete(amain())
    new_loop.close()

# --- 3. INTERFACE ---
st.title("🎙️ shruta: Direct Voicen generater")

if "raw_data" not in st.session_state: st.session_state.raw_data = ""

with st.sidebar:
    lang_choice = st.selectbox("🌐 Audio Language", ["English", "Hindi", "Telugu"])

tab1, tab2 = st.tabs(["🚀 Audio Generator", "🧠 Deep Chat"])

with tab1:
    source = st.radio("Input:", ["PDF File", "YouTube URL"], horizontal=True)
    
    if source == "PDF File":
        up = st.file_uploader("Upload 1-Hour PDF")
        if up: st.session_state.raw_data = "\n".join([p.extract_text() for p in PdfReader(up).pages])
    else:
        url_input = st.text_input("YouTube URL:")
        if url_input: st.session_state.raw_data = get_yt_text_pro(url_input)

    if st.session_state.raw_data and st.button("🔊 Generate Full Audio Now"):
        with st.status("🏗️ Building Audio Script...", expanded=True) as status:
            # We generate a long hidden script (approx 800-1000 words) for long audio
            st.write("🧠 Extracting all key points for a long-form audio...")
            hidden_prompt = (
                f"Convert this lecture into a comprehensive, spoken-word script in {lang_choice}. "
                f"Ensure it is very detailed, covers every basic point, and lasts for a long duration. "
                f"Do not summarize briefly; explain the concepts as if teaching. Context: {st.session_state.raw_data[:30000]}"
            )
            
            script_response = model.generate_content(hidden_prompt)
            hidden_script = script_response.text
            
            st.write("🎙️ Synthesizing long-form voice...")
            t = threading.Thread(target=make_audio, args=(hidden_script, lang_choice))
            t.start()
            t.join()
            
            if os.path.exists("lecture_voice.mp3"):
                status.update(label="✅ Audio Generated!", state="complete")
                st.audio("lecture_voice.mp3")
                st.info("💡 No text shown as requested. Use the 'Deep Chat' tab for questions.")

with tab2:
    if "msgs" not in st.session_state: st.session_state.msgs = []
    for m in st.session_state.msgs:
        with st.chat_message(m["role"]): st.write(m["content"])
    
    if q := st.chat_input("Ask a question about the lecture..."):
        st.session_state.msgs.append({"role": "user", "content": q})
        with st.chat_message("user"): st.write(q)
        
        ai_res = model.generate_content(f"Context: {st.session_state.raw_data[:15000]}. Q: {q}").text
        st.session_state.msgs.append({"role": "assistant", "content": ai_res})
        with st.chat_message("assistant"): st.write(ai_res)
