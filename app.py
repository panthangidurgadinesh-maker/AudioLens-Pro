import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
import asyncio
import edge_tts
import time
import os
import glob

# --- 1. THE THEME (Animated Grid) ---
st.set_page_config(page_title="AudioLens Pro", layout="wide")
st.components.v1.html("""
<canvas id="canvas" style="position:fixed; top:0; left:0; width:100vw; height:100vh; z-index:-1; background:#08080a;"></canvas>
<script>
const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');
canvas.width = window.innerWidth; canvas.height = window.innerHeight;
let particles = [];
class Particle {
    constructor() {
        this.x = Math.random() * canvas.width;
        this.y = Math.random() * canvas.height;
        this.v = Math.random() * 0.4 + 0.1;
    }
    update() { this.y -= this.v; if (this.y < 0) this.y = canvas.height; }
    draw() { ctx.fillStyle = 'rgba(65, 149, 252, 0.4)'; ctx.beginPath(); ctx.arc(this.x, this.y, 1, 0, Math.PI * 2); ctx.fill(); }
}
for (let i = 0; i < 70; i++) particles.push(new Particle());
function anim() { ctx.clearRect(0, 0, canvas.width, canvas.height); particles.forEach(p => { p.update(); p.draw(); }); requestAnimationFrame(anim); }
anim();
</script>
""", height=0)

st.markdown("""
    <style>
    .stApp { background-color: transparent; background-image: linear-gradient(to right, rgba(255,255,255,0.03) 1px, transparent 1px), linear-gradient(to bottom, rgba(255,255,255,0.03) 1px, transparent 1px); background-size: 40px 40px; }
    div[data-testid="stExpander"], .stChatMessage, .stFileUploader { background-color: rgba(20, 20, 25, 0.8) !important; border: 1px solid rgba(255, 255, 255, 0.1) !important; backdrop-filter: blur(10px); }
    .stButton>button { background: linear-gradient(90deg, #4facfe, #00f2fe); color: black; font-weight: bold; border-radius: 20px; width: 100%; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. THE CORE ENGINE ---
API_KEY = st.secrets["AIzaSyAsX-7Kj_AdMfhkNOChe8x2T_Vv0JJGwB4"]
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-3-flash-preview')

def get_yt_transcript(url):
    try:
        import re
        from youtube_transcript_api import YouTubeTranscriptApi
        
        # 1. Extract Video ID
        vid_match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", url)
        if not vid_match:
            return None
        video_id = vid_match.group(1)

        # 2. Initialize the API
        ytt_api = YouTubeTranscriptApi()
        
        # 3. Fetch the data
        transcript_data = ytt_api.fetch(video_id, languages=['en', 'hi', 'te'])
        
        # ✅ THE FIX: Use t.text instead of t['text']
        return " ".join([t.text for t in transcript_data])
        
    except Exception as e:
        # Secondary backup for standard dictionary-style API returns
        try:
            from youtube_transcript_api import YouTubeTranscriptApi as YTA
            return " ".join([i['text'] for i in YTA.get_transcript(video_id)])
        except:
            st.error(f"URL Connection Failed: {e}")
            return None

# --- 3. UI ---
with st.sidebar:
    st.title("🛰️ AudioLens Settings")
    lang_choice = st.selectbox("🌐 Audio Language", ["English", "Hindi", "Telugu"])
    if st.button("🗑️ Clear Local Cache"):
        for f in glob.glob("podcast_*.mp3"): os.remove(f)
        st.success("Cleaned!")

st.title("🎙️ Intelligence Workspace")
tab1, tab2 = st.tabs(["🚀 Transform", "🧠 Chat"])

with tab1:
    source_type = st.radio("Source:", ["PDF", "YouTube"], horizontal=True)
    active_text = ""
    if source_type == "PDF":
        f = st.file_uploader("Upload PDF")
        if f: active_text = "\n".join([p.extract_text() for p in PdfReader(f).pages])
    else:
        url_in = st.text_input("Paste YouTube Link")
        if url_in: active_text = get_yt_transcript(url_in)

    if active_text and st.button("✨ Generate Podcast"):
        output_file = f"podcast_{int(time.time())}.mp3"
        with st.status("AI Processing...", expanded=True) as status:
            prompt = f"Create a natural dialogue between Alex and Sam in {lang_choice} about: {active_text[:12000]}"
            script = model.generate_content(prompt).text
            v_map = {"English": ["en-US-ChristopherNeural", "en-US-JennyNeural"],
                     "Hindi": ["hi-IN-MadhurNeural", "hi-IN-SwaraNeural"],
                     "Telugu": ["te-IN-MohanNeural", "te-IN-ShrutiNeural"]}

            async def synth():
                with open(output_file, "wb") as f_out:
                    for line in script.strip().split('\n'):
                        if ":" not in line: continue
                        v = v_map[lang_choice][0] if "Alex" in line else v_map[lang_choice][1]
                        comm = edge_tts.Communicate(line.split(":", 1)[1], v)
                        async for chunk in comm.stream():
                            if chunk["type"] == "audio": f_out.write(chunk["data"])
            asyncio.run(synth())
            time.sleep(2)
            status.update(label="✅ Ready!", state="complete")
        st.audio(output_file)
        # --- NEW DOWNLOAD FEATURE ---
        st.markdown("---")
        st.subheader("📝 Study Materials")
        
        # Prepare the text for the download file
        summary_content = f"TRANSCRIPT SUMMARY & PODCAST SCRIPT\n"
        summary_content += f"Source: {url_in if source_type == 'YouTube' else 'Uploaded PDF'}\n"
        summary_content += f"Language: {lang_choice}\n"
        summary_content += "="*40 + "\n\n"
        summary_content += script  # This uses the AI-generated dialogue [cite: 11]

        # Create the download button
        st.download_button(
            label="📥 Download Study Notes (TXT)",
            data=summary_content,
            file_name=f"study_notes_{int(time.time())}.txt",
            mime="text/plain",
            help="Click to save the AI summary to your device for offline reading."
        )

with tab2:
    if "msgs" not in st.session_state: st.session_state.msgs = []
    for m in st.session_state.msgs:
        with st.chat_message(m["role"]): st.write(m["content"])
    if q := st.chat_input("Ask about the content..."):
        st.session_state.msgs.append({"role": "user", "content": q})
        with st.chat_message("user"): st.write(q)
        res = model.generate_content(f"Data: {active_text[:5000]}. Q: {q}").text
        st.session_state.msgs.append({"role": "assistant", "content": res})
        with st.chat_message("assistant"): st.write(res)