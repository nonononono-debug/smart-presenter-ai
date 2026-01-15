import streamlit as st
import google.generativeai as genai
from pptx import Presentation
import json
import io
from PIL import Image
import time  # <--- 引入时间库，用于限速

# --- 页面配置 ---
st.set_page_config(page_title="智讲 SmartPresenter Pro", layout="wide", page_icon="🎤")

# --- 侧边栏 ---
with st.sidebar:
    st.title("🎙️ 智讲 Pro")
    st.caption("防限流稳定版")
    st.divider()
    
    api_key = st.text_input("🔑 Google API Key", type="password")
    
    # 自动获取可用模型
    available_models = []
    if api_key:
        try:
            genai.configure(api_key=api_key)
            all_models = genai.list_models()
            for m in all_models:
                if 'generateContent' in m.supported_generation_methods:
                    available_models.append(m.name)
            st.success(f"✅ 已加载 {len(available_models)} 个可用模型")
        except Exception as e:
            st.error(f"❌ Key 验证失败: {e}")

    if available_models:
        # 智能预选
        default_index = 0
        for i, name in enumerate(available_models):
            if "flash" in name and "1.5" in name:
                default_index = i
                break
        
        selected_model = st.selectbox(
            "👇 选择模型 (推荐 Flash):",
            available_models,
            index=default_index
        )
    else:
        selected_model = st.selectbox("模型列表:", ["models/gemini-1.5-flash"])

    st.info("💡 提示：为防止 429 限流报错，每页分析将自动间隔 5 秒。")

# --- 核心逻辑 ---
def analyze_ppt(uploaded_file, api_key, model_name):
    genai.configure(api_key=api_key)
    
    model = genai.GenerativeModel(
        model_name,
        generation_config={"response_mime_type": "application/json"}
    )

    prs = Presentation(uploaded_file)
    results = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    total_slides = len(prs.slides)

    for i, slide in enumerate(prs.slides):
        status_text.text(f"🚀 正在分析第 {i+1}/{total_slides} 页 (模型: {model_name})")
        progress_bar.progress((i + 1) / total_slides)

        # --- 1. 提取内容 ---
        text_runs = []
        for shape in slide.shapes:
            if hasattr(shape, "text"):
                text_runs.append(shape.text)
        slide_text = "\n".join(text_runs)

        slide_image = None
        for shape in slide.shapes:
            if shape.shape_type == 13: 
                try:
                    image_stream = io.BytesIO(shape.image.blob)
                    slide_image = Image.open(image_stream)
                    break 
                except:
                    pass

        # --- 2. 构造 Prompt ---
        prompt = """
        Analyze this slide. Output valid JSON:
        {
            "visual_summary": "1 sentence description",
            "scripts": {
                "beginner": "Script for beginner",
                "standard": "Script for business",
                "expert": "Script for expert"
            },
            "knowledge_extension": {
                "entity": "Keyword",
                "trivia": "Did you know fact"
            }
        }
        """
        
        inputs = [prompt, f"Text: {slide_text}"]
        if slide_image:
            inputs.append(slide_image)
        else:
            inputs.append("(No image)")

        # --- 3. 调用 AI (带重试机制) ---
        try:
            response = model.generate_content(inputs)
            text = response.text.strip()
            if text.startswith("```json"): text = text.replace("```json", "").replace("```", "")
            data = json.loads(text)
            data['index'] = i + 1
            results.append(data)
            
        except Exception as e:
            err_msg = str(e)
            if "429" in err_msg:
                st.warning(f"第 {i+1} 页触发限流，正在冷却...")
                time.sleep(10) # 遇到限流多睡一会
            else:
                st.error(f"第 {i+1} 页出错: {e}")
        
        # --- 4. 关键：主动限速 (防止 429) ---
        # 免费版每分钟限制 15 次请求，所以每次请求后休息 4-5 秒是安全的
        time.sleep(4) 
                
    progress_bar.empty()
    status_text.empty()
    return results

# --- UI ---
uploaded_file = st.file_uploader("📂 上传 PPTX 文件", type=['pptx'])

if uploaded_file and api_key and available_models:
    if st.button("🚀 开始分析 (慢速稳定版)"):
        with st.spinner("AI 正在思考 (已开启防限流模式)..."):
            results = analyze_ppt(uploaded_file, api_key, selected_model)
            st.session_state['results'] = results

if 'results' in st.session_state:
    st.success("✅ 分析完成！")
    for slide in st.session_state['results']:
        with st.expander(f"📄 第 {slide.get('index', '?')} 页 | {slide.get('visual_summary', '')}", expanded=(slide.get('index')==1)):
            c1, c2 = st.columns([2, 1])
            with c1:
                scripts = slide.get('scripts', {})
                st.markdown(f"**普通模式：**\n{scripts.get('standard', 'N/A')}")
            with c2:
                ext = slide.get('knowledge_extension', {})
                st.info(f"💡 **{ext.get('entity', 'N/A')}**: {ext.get('trivia', 'N/A')}")
