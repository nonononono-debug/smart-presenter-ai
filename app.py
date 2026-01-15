import streamlit as st
import google.generativeai as genai
from pptx import Presentation
import json
import io
from PIL import Image

# --- 页面配置 ---
st.set_page_config(page_title="智讲 SmartPresenter Pro", layout="wide", page_icon="🎤")

# --- 侧边栏 ---
with st.sidebar:
    st.title("🎙️ 智讲 Pro")
    st.caption("API 连接诊断版")
    
    st.divider()
    
    # 1. API Key 输入区
    api_key = st.text_input("🔑 Google API Key", type="password")
    
    # 2. 连接测试按钮 (新增功能)
    if api_key:
        if st.button("🔌 点击测试 Key 是否有效"):
            try:
                genai.configure(api_key=api_key)
                # 尝试列出模型，如果 Key 是坏的，这里会直接报错
                models = list(genai.list_models())
                st.success(f"✅ 连接成功！您的 Key 有效。")
                st.caption(f"可用模型数量: {len(models)}")
            except Exception as e:
                st.error(f"❌ 连接失败！Key 无效。")
                st.error(f"Google 返回报错: {e}")
                st.info("请务必去 aistudio.google.com 创建一个【新项目】的 Key。")

    st.divider()

    # 3. 模型选择
    st.markdown("### 🤖 模型选择")
    selected_model = st.selectbox(
        "选择模型：",
        ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"],
        index=0
    )

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
        status_text.text(f"🚀 [{model_name}] 正在分析第 {i+1}/{total_slides} 页...")
        progress_bar.progress((i + 1) / total_slides)

        # 提取文本
        text_runs = []
        for shape in slide.shapes:
            if hasattr(shape, "text"):
                text_runs.append(shape.text)
        slide_text = "\n".join(text_runs)

        # 提取图片
        slide_image = None
        for shape in slide.shapes:
            if shape.shape_type == 13: 
                try:
                    image_stream = io.BytesIO(shape.image.blob)
                    slide_image = Image.open(image_stream)
                    break 
                except:
                    pass

        # Prompt
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

        try:
            response = model.generate_content(inputs)
            text = response.text.strip()
            if text.startswith("```json"): text = text.replace("```json", "").replace("```", "")
            data = json.loads(text)
            data['index'] = i + 1
            results.append(data)
        except Exception as e:
            # 兼容旧模型不支持 JSON 的情况
            if "gemini-pro" == model_name and "400" in str(e):
                st.warning(f"第 {i+1} 页：旧版模型不支持 JSON 模式，请切换回 1.5-flash。")
            else:
                st.error(f"第 {i+1} 页分析出错: {e}")
                
    progress_bar.empty()
    status_text.empty()
    return results

# --- UI ---
uploaded_file = st.file_uploader("📂 上传 PPTX 文件", type=['pptx'])

if uploaded_file and api_key:
    if st.button("🚀 开始分析"):
        with st.spinner("AI 正在思考..."):
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
