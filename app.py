import streamlit as st
import google.generativeai as genai
from pptx import Presentation
import json
import io
from PIL import Image
import time

# --- 页面配置 (Page Config) ---
st.set_page_config(
    page_title="智讲 SmartPresenter Pro",
    layout="wide",
    page_icon="🎙️",
    initial_sidebar_state="expanded"
)

# --- 辅助函数：清洗 JSON (防止 AI 输出 Markdown 标记) ---
def clean_json_text(text):
    text = text.strip()
    if text.startswith("```json"):
        text = text.replace("```json", "", 1)
    if text.startswith("```"):
        text = text.replace("```", "", 1)
    if text.endswith("```"):
        text = text.replace("```", "", 1)
    return text.strip()

# --- 侧边栏：全局设置 ---
with st.sidebar:
    st.title("🎙️ 智讲 Pro")
    st.caption("AI 驱动的演示认知重构系统")
    
    st.divider()
    
    # 1. API Key 配置
    api_key = st.text_input("🔑 Google API Key", type="password", help="在此输入您的 Gemini API Key")
    if not api_key:
        st.warning("⚠️ 请输入 API Key 以启动引擎")
        st.markdown("[👉 获取免费 Key](https://aistudio.google.com/app/apikey)")
    
    st.divider()

    # 2. 高级设置 (Prompt 实验室)
    st.subheader("🎛️ 风格微调")
    style_modifier = st.selectbox(
        "整体基调",
        ["默认 (均衡)", "幽默风趣 (脱口秀)", "极度专业 (学术汇报)", "史蒂夫·乔布斯风格 (极简)"],
        index=0
    )
    
    st.info(f"当前模型：Gemini 1.5 Flash (高速版)")

# --- 核心逻辑函数 ---
def analyze_ppt(uploaded_file, api_key, style_modifier):
    genai.configure(api_key=api_key)
    
    # 构建动态 System Prompt
    base_prompt = """
    You are an expert presentation architect. Analyze the slide image and text.
    Output pure, valid JSON. 
    """
    
    if "幽默" in style_modifier:
        base_prompt += " Add humor and wit to the scripts."
    elif "专业" in style_modifier:
        base_prompt += " Be extremely formal, data-driven, and academic."
    elif "乔布斯" in style_modifier:
        base_prompt += " Be minimalist, inspiring, and use powerful short sentences."

    model = genai.GenerativeModel(
        'gemini-1.5-flash',
        system_instruction=base_prompt,
        generation_config={"response_mime_type": "application/json"}
    )

    prs = Presentation(uploaded_file)
    results = []
    
    # 创建进度容器
    progress_bar = st.progress(0)
    status_text = st.empty()
    total_slides = len(prs.slides)

    for i, slide in enumerate(prs.slides):
        status_text.text(f"🚀 正在深度解析第 {i+1} / {total_slides} 页...")
        progress_bar.progress((i + 1) / total_slides)

        # 1. 提取文本
        text_runs = []
        for shape in slide.shapes:
            if hasattr(shape, "text"):
                text_runs.append(shape.text)
        slide_text = "\n".join(text_runs)

        # 2. 提取图片
        slide_image = None
        for shape in slide.shapes:
            if shape.shape_type == 13: 
                try:
                    image_stream = io.BytesIO(shape.image.blob)
                    slide_image = Image.open(image_stream)
                    break 
                except:
                    pass

        # 3. 具体指令
        prompt = """
        Analyze this slide. Return JSON with these exact keys:
        {
            "visual_summary": "1 sentence visual description",
            "scripts": {
                "beginner": "Script for laypeople (ELI5)",
                "standard": "Script for business setting",
                "expert": "Script for industry experts"
            },
            "knowledge_extension": {
                "entity": "Trigger keyword",
                "trivia": "A fascinating 'Did you know' fact related to the keyword"
            }
        }
        """
        
        inputs = [prompt, f"Slide Text Context: {slide_text}"]
        if slide_image:
            inputs.append(slide_image)
        else:
            inputs.append("(No image visual detected)")

        try:
            response = model.generate_content(inputs)
            cleaned_text = clean_json_text(response.text)
            data = json.loads(cleaned_text)
            data['index'] = i + 1
            results.append(data)
        except Exception as e:
            # 容错处理：如果出错，填入空数据，不中断程序
            st.error(f"第 {i+1} 页分析遇到小问题: {e}")
            results.append({
                "index": i+1,
                "visual_summary": "解析失败",
                "scripts": {"beginner": "N/A", "standard": "N/A", "expert": "N/A"},
                "knowledge_extension": {"entity": "None", "trivia": "N/A"}
            })
            
    progress_bar.empty()
    status_text.empty()
    return results

# --- 主界面 UI ---
st.title("🎤 智讲 SmartPresenter Pro")
st.markdown(f"#### 您的 AI 演示架构师 | 模式：{style_modifier}")

# 文件上传区
uploaded_file = st.file_uploader("📂 拖拽上传 PPTX 文件", type=['pptx'])

# 启动按钮
if uploaded_file and api_key:
    if st.button("🚀 启动认知重构引擎 (Start Analysis)", type="primary"):
        with st.spinner("🧠 正在连接 Gemini 视觉中枢..."):
            results = analyze_ppt(uploaded_file, api_key, style_modifier)
            st.session_state['results'] = results
            st.toast("✅ 分析完成！", icon="🎉")

# --- 结果展示区 (Pro版 UI) ---
if 'results' in st.session_state:
    results = st.session_state['results']
    
    # 1. 顶部：一键导出区域
    st.divider()
    col_exp1, col_exp2 = st.columns([4, 1])
    with col_exp1:
        st.caption(f"共分析了 {len(results)} 页幻灯片。您可以点击右侧按钮下载完整讲稿。")
    with col_exp2:
        # 生成下载文本
        export_text = ""
        for slide in results:
            export_text += f"=== 第 {slide['index']} 页 ===\n"
            export_text += f"视觉摘要: {slide['visual_summary']}\n\n"
            export_text += f"[小白模式]: {slide['scripts']['beginner']}\n"
            export_text += f"[普通模式]: {slide['scripts']['standard']}\n"
            export_text += f"[专业模式]: {slide['scripts']['expert']}\n"
            export_text += f"[知识彩蛋]: {slide['knowledge_extension']['trivia']}\n\n"
            export_text += "-"*30 + "\n"
            
        st.download_button(
            label="📥 导出完整讲稿 (.txt)",
            data=export_text,
            file_name="smart_presenter_script.txt",
            mime="text/plain"
        )
    
    st.divider()

    # 2. 逐页展示 (使用折叠面板，更整洁)
    for slide in results:
        with st.expander(f"📄 第 {slide['index']} 页 | 视觉摘要: {slide['visual_summary']}", expanded=(slide['index']==1)):
            
            # 布局：左侧脚本，右侧彩蛋
            c1, c2 = st.columns([7, 3])
            
            with c1:
                tab_b, tab_s, tab_e = st.tabs(["🟢 小白模式", "🔵 普通模式", "🔴 专业模式"])
                with tab_b:
                    st.markdown(f"*{slide['scripts']['beginner']}*")
                with tab_s:
                    st.markdown(f"{slide['scripts']['standard']}")
                with tab_e:
                    st.markdown(f"**{slide['scripts']['expert']}**")
            
            with c2:
                # 漂亮的卡片样式展示知识彩蛋
                st.success(f"💡 **知识延展：{slide['knowledge_extension']['entity']}**")
                st.caption(slide['knowledge_extension']['trivia'])

elif uploaded_file and not api_key:
    st.info("👈 请先在左侧侧边栏输入您的 Google API Key。")
