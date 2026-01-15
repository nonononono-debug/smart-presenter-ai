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
    st.caption("自适应模型加载版")
    st.divider()
    
    # 1. 输入 API Key
    api_key = st.text_input("🔑 Google API Key", type="password")
    
    # 2. 自动获取可用模型 (核心修复)
    available_models = []
    if api_key:
        try:
            genai.configure(api_key=api_key)
            # 动态向 Google 询问有哪些模型可用
            all_models = genai.list_models()
            for m in all_models:
                # 只保留支持内容生成的模型
                if 'generateContent' in m.supported_generation_methods:
                    available_models.append(m.name)
            st.success(f"✅ 已加载 {len(available_models)} 个可用模型")
        except Exception as e:
            st.error(f"❌ Key 验证失败: {e}")

    # 3. 模型选择下拉菜单
    if available_models:
        # 智能预选：优先找 flash 或 pro
        default_index = 0
        for i, name in enumerate(available_models):
            if "flash" in name and "1.5" in name:
                default_index = i
                break
        
        selected_model = st.selectbox(
            "👇 请选择一个模型 (Google 官方列表):",
            available_models,
            index=default_index
        )
    else:
        # 兜底选项
        selected_model = st.selectbox(
            "模型列表 (请输入 Key 加载):",
            ["models/gemini-1.5-flash", "models/gemini-pro"]
        )

# --- 核心逻辑 ---
def analyze_ppt(uploaded_file, api_key, model_name):
    genai.configure(api_key=api_key)
    
    # 直接使用列表中选中的真实名字，不再猜测
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
        status_text.text(f"🚀 正在分析第 {i+1}/{total_slides} 页 | 使用引擎: {model_name}")
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
            # 如果选中的模型不支持 JSON，做个提示
            if "400" in str(e) and "JSON" in str(e):
                st.warning(f"第 {i+1} 页：当前模型 {model_name} 可能不支持 JSON 模式，建议换一个带 1.5 的模型。")
            else:
                st.error(f"第 {i+1} 页出错: {e}")
                
    progress_bar.empty()
    status_text.empty()
    return results

# --- UI ---
uploaded_file = st.file_uploader("📂 上传 PPTX 文件", type=['pptx'])

if uploaded_file and api_key and available_models:
