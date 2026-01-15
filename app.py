import streamlit as st
import google.generativeai as genai
from pptx import Presentation
import json
import io
from PIL import Image

# --- 页面配置 ---
st.set_page_config(page_title="智讲 SmartPresenter", layout="wide", page_icon="🎤")

# --- 侧边栏：API Key 配置 ---
with st.sidebar:
    st.header("⚙️ 设置")
    api_key = st.text_input("请输入 Google API Key", type="password")
    st.markdown("[获取 API Key](https://aistudio.google.com/app/apikey)")
    st.divider()
    st.info("架构师提示：这是一个基于 Google Gemini 1.5 的 PPT 认知重构系统。")

# --- 核心逻辑函数 ---
def analyze_ppt(uploaded_file, api_key):
    genai.configure(api_key=api_key)
    
    # 使用支持 JSON Mode 的模型
model = genai.GenerativeModel(    # 第 24 行
        'gemini-1.5-pro',
        generation_config={"response_mime_type": "application/json"}
    )

    prs = Presentation(uploaded_file) # 第 29 行（这里要和上面的 model 对齐！）
    results = []                      # 第 30 行（也要对齐）

    progress_bar = st.progress(0)     # 第 32 行（也要对齐）
    total_slides = len(prs.slides)

    for i, slide in enumerate(prs.slides):
        # 更新进度条
        progress_bar.progress((i + 1) / total_slides, text=f"正在分析第 {i+1}/{total_slides} 页...")

        # 1. 提取文本
        text_runs = []
        for shape in slide.shapes:
            if hasattr(shape, "text"):
                text_runs.append(shape.text)
        slide_text = "\n".join(text_runs)

        # 2. 尝试提取图片 (简化版)
        slide_image = None
        for shape in slide.shapes:
            if shape.shape_type == 13: 
                try:
                    image_stream = io.BytesIO(shape.image.blob)
                    slide_image = Image.open(image_stream)
                    break 
                except:
                    pass

        # 3. Prompt 设计
        prompt = """
        Analyze this slide. Output valid JSON:
        {
            "visual_summary": "Brief visual description",
            "scripts": {
                "beginner": "ELI5 script, simple analogies, warm tone",
                "standard": "Professional script, business tone",
                "expert": "Technical script, jargon heavy, critical"
            },
            "knowledge_extension": {
                "entity": "Trigger entity",
                "trivia": "A short, surprising 'Did you know' fact related to the entity"
            }
        }
        """
        
        inputs = [prompt, f"Slide Text: {slide_text}"]
        if slide_image:
            inputs.append(slide_image)
        else:
            inputs.append("(No image detected)")

        try:
            response = model.generate_content(inputs)
            data = json.loads(response.text)
            data['index'] = i + 1
            results.append(data)
        except Exception as e:
            st.error(f"第 {i+1} 页分析出错: {e}")
            
    progress_bar.empty()
    return results

# --- 主界面 UI ---
st.title("🎤 智讲 SmartPresenter")
st.markdown("### 您的 AI 演示架构师：自适应认知 + 知识增强")

uploaded_file = st.file_uploader("上传 PPTX 文件", type=['pptx'])

if uploaded_file and api_key:
    if st.button("🚀 开始 AI 分析 (架构重组)"):
        with st.spinner("正在启动认知引擎..."):
            results = analyze_ppt(uploaded_file, api_key)
            st.session_state['results'] = results # 存入缓存
            st.success("分析完成！")

# --- 结果展示区 ---
if 'results' in st.session_state:
    results = st.session_state['results']
    
    for slide in results:
        with st.container():
            st.markdown(f"#### 📄 第 {slide['index']} 页")
            st.caption(f"视觉摘要: {slide['visual_summary']}")
            
            # 布局：左边是三轨脚本，右边是知识彩蛋
            col1, col2 = st.columns([3, 1])
            
            with col1:
                tab1, tab2, tab3 = st.tabs(["🟢 小白模式", "🔵 普通模式", "🔴 专业模式"])
                with tab1: st.write(slide['scripts']['beginner'])
                with tab2: st.write(slide['scripts']['standard'])
                with tab3: st.write(slide['scripts']['expert'])
            
            with col2:
                st.markdown("✨ **知识延展**")
                st.info(f"**触发词:** {slide['knowledge_extension']['entity']}\n\n💡 {slide['knowledge_extension']['trivia']}")
            
            st.divider()

elif uploaded_file and not api_key:

    st.warning("请在左侧侧边栏输入 API Key 以继续。")

