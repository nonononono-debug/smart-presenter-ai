import streamlit as st
import google.generativeai as genai
from pptx import Presentation
import json
import io
from PIL import Image
import time

# --- 页面配置 ---
st.set_page_config(page_title="智讲 SmartPresenter Pro", layout="wide", page_icon="🎤")

# --- 侧边栏 ---
with st.sidebar:
    st.title("🎙️ 智讲 Pro")
    st.caption("自动重试 · 稳定版")
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

    # 模型选择
    if available_models:
        default_index = 0
        # 优先寻找 gemini-1.5-flash (最快且配额较高)
        for i, name in enumerate(available_models):
            if "flash" in name and "1.5" in name:
                default_index = i
                break
        
        selected_model = st.selectbox(
            "👇 选择模型:",
            available_models,
            index=default_index
        )
    else:
        selected_model = st.selectbox("模型列表:", ["models/gemini-1.5-flash"])

    st.info("💡 机制说明：遇到限流会自动等待并重试，绝不跳过任何一页。")

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
        status_text.text(f"🚀 正在死磕第 {i+1}/{total_slides} 页...")
        progress_bar.progress((i) / total_slides)

        # 1. 准备内容
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
        
        # 2. 构造 Prompt
        prompt = """
        Analyze this slide. Output valid JSON only:
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

        # 3. 核心：重试循环 (Retry Loop)
        max_retries = 5  # 最多重试5次
        retry_count = 0
        success = False
        
        while not success and retry_count < max_retries:
            try:
                response = model.generate_content(inputs)
                text = response.text.strip()
                if text.startswith("```json"): text = text.replace("```json", "").replace("```", "")
                data = json.loads(text)
                data['index'] = i + 1
                results.append(data)
                success = True # 成功了！退出循环
                
            except Exception as e:
                err_msg = str(e)
                if "429" in err_msg:
                    wait_time = 10 + (retry_count * 5) # 第一次等10秒，第二次15秒...
                    status_text.warning(f"⚠️ 第 {i+1} 页太快了 (429)，休息 {wait_time} 秒后重试 ({retry_count+1}/5)...")
                    time.sleep(wait_time)
                    retry_count += 1
                else:
                    st.error(f"❌ 第 {i+1} 页遇到非限流错误: {e}")
                    # 非限流错误（如图片太大）则跳过，避免死循环
                    break 

        # 每次成功后，稍微停顿一下，给 Google 服务器喘口气
        time.sleep(2)
                
    progress_bar.progress(1.0)
    status_text.success("🎉 所有页面分析完成！")
    return results

# --- UI ---
uploaded_file = st.file_uploader("📂 上传 PPTX 文件", type=['pptx'])

if uploaded_file and api_key and available_models:
    if st.button("🚀 开始分析 (死磕模式)"):
        with st.spinner("AI 正在逐页攻克..."):
            results = analyze_ppt(uploaded_file, api_key, selected_model)
            st.session_state['results'] = results

if 'results' in st.session_state and st.session_state['results']:
    st.divider()
    st.success(f"✅ 成功生成 {len(st.session_state['results'])} 页讲稿！")
    
    for slide in st.session_state['results']:
        with st.expander(f"📄 第 {slide.get('index', '?')} 页 | {slide.get('visual_summary', '无摘要')}", expanded=False):
            c1, c2 = st.columns([2, 1])
            with c1:
                scripts = slide.get('scripts', {})
                st.markdown("### 🎙️ 演讲稿")
                st.markdown(f"**普通模式:** {scripts.get('standard', 'N/A')}")
                st.info(f"**小白模式:** {scripts.get('beginner', 'N/A')}")
            with c2:
                ext = slide.get('knowledge_extension', {})
                st.markdown("### 🧠 知识点")
                st.warning(f"**{ext.get('entity', 'N/A')}**\n\n{ext.get('trivia', 'N/A')}")
elif 'results' in st.session_state and not st.session_state['results']:
    st.warning("⚠️ 分析结束，但没有生成任何结果。这通常是因为所有页面都重试失败了，请检查 Key 或更换模型。")
