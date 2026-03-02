import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
import yt_dlp
import asyncio
import edge_tts
import re
import os
import threading

# --- 1. SETTINGS & GLOBAL COMPACT CSS ---
st.set_page_config(page_title="Shruta", layout="wide", page_icon="🎧")

st.markdown("""
    <style>
    /* Global Font Shrink */
    html, body, [class*="css"], .stMarkdown, p, div {
        font-size: 13px !important;
        line-height: 1.2 !important;
    }
    /* Tighten Layout Padding */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 0rem !important;
        max-width: 98% !important;
    }
    /* Shrink Headers */
    h1 { font-size: 20px !important; font-weight: 700 !important; margin-bottom: 5px !important; }
    h2 { font-size: 16px !important; }
    h3 { font-size: 14px !important; }
    
    /* Minimize Input Box Heights */
    .stTextInput>div>div>input, .stFileUploader section {
        padding: 2px 10px !important;
        min-height: 30px !important;
    }
    /* Compact Sidebar */
    [data-testid="stSidebar"] { width: 220px !important; }
    
    /* Professional Clean Button */
    .stButton>button {
        width: 100%;
        height: 32px !important;
        background-color: transparent !important;
        border: 1px solid #444 !important;
        font-size: 13px !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. THE ENGINE ---
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=API_KEY)
    available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    target_model = next((m for m in available_models if "flash" in m), available_models[0])
    model = genai.GenerativeModel(target_model)
except Exception as e:
    st.error(f"Config Error: {e}"); st.stop()

def get_yt_text_pro(url):
    try:
        with yt_dlp.YoutubeDL({'skip_download': True, 'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            return f"Lecture: {info.get('title')}. [Metadata Processed]"
    except: return "BLOCKED"

def make_audio(text, lang):
    v_map = {"English": "en-US-AriaNeural", "Hindi": "hi-IN-SwaraNeural", "Telugu": "te-IN-ShrutiNeural"}
    async def amain():
        await edge_tts.Communicate(re.sub(r'[*_#`\-]', '', text), v_map.get(lang, "en-US-AriaNeural")).save("voice.mp3")
    new_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(new_loop)
    new_loop.run_until_complete(amain())
    new_loop.close()

# --- 3. UI LAYOUT (MINIMALIST) ---
st.markdown("### 🎧 Shruta | శ్రుత")

if "raw_data" not in st.session_state: st.session_state.raw_data = ""

tab1, tab2 = st.tabs(["🚀 Generator", "🧠 Chat"])

with tab1:
    col1, col2 = st.columns([1, 1])
    with col1:
        source = st.radio("Source:", ["PDF", "YouTube"], horizontal=True, label_visibility="collapsed")
    
    if source == "PDF":
        up = st.file_uploader("Upload PDF", type="pdf", label_visibility="collapsed")
        if up: st.session_state.raw_data = "\n".join([p.extract_text() for p in PdfReader(up).pages])
    else:
        url_in = st.text_input("YouTube URL", placeholder="Paste Link...", label_visibility="collapsed")
        if url_in: st.session_state.raw_data = get_yt_text_pro(url_in)

    lang = st.selectbox("Audio Language", ["English", "Hindi", "Telugu"], label_visibility="collapsed")

    if st.session_state.raw_data and st.button("🔊 Generate Audio"):
        with st.spinner("Processing..."):
            prompt = f"Detailed spoken script in {lang}. Cover all basic points. Context: {st.session_state.raw_data[:25000]}"
            script = model.generate_content(prompt).text
            t = threading.Thread(target=make_audio, args=(script, lang))
            t.start(); t.join()
            if os.path.exists("voice.mp3"): st.audio("voice.mp3")

with tab2:
    if q := st.chat_input("Ask a question..."):
        res = model.generate_content(f"Context: {st.session_state.raw_data[:15000]}. Q: {q}").text
        with st.chat_message("assistant"): st.write(res)
