import streamlit as st
import google.generativeai as genai
from pptx import Presentation
import json
import io
from PIL import Image
import time

# --- 页面全局配置 ---
st.set_page_config(
    page_title="智讲 SmartPresenter Pro",
    layout="wide",
    page_icon="👨‍💻",
    initial_sidebar_state="expanded"
)

# --- 架构师工具箱：智能配速逻辑 ---
def get_model_delay(model_name):
    """
    根据模型类型决定'冷却时间'，避免触发 429 报错。
    Flash: ~15 RPM -> 安全间隔 4秒
    Pro: ~2 RPM -> 安全间隔 32秒
    """
    if "flash" in model_name.lower():
        return 4  # Flash 模型：快
    else:
        return 32 # Pro 模型：慢 (贵族模型)

# --- 侧边栏配置 ---
with st.sidebar:
    st.title("👨‍💻 智讲 Pro")
    st.caption("架构师版：流式渲染 + 智能配速")
    st.divider()
    
    api_key = st.text_input("🔑 Google API Key", type="password")
    
    # 1. 动态加载模型
    available_models = []
    if api_key:
        try:
            genai.configure(api_key=api_key)
            all_models = genai.list_models()
            for m in all_models:
                if 'generateContent' in m.supported_generation_methods:
                    available_models.append(m.name)
            st.success(f"✅ 已连接 Google 大脑 (可用模型: {len(available_models)})")
        except Exception as e:
            st.error(f"❌ Key 无效")

    # 2. 模型选择器
    selected_model = "models/gemini-1.5-flash" # 默认值
    if available_models:
        # 优先推荐 Flash，因为 Pro 实在是太慢了
        default_index = 0
        for i, name in enumerate(available_models):
            if "flash" in name and "1.5" in name:
                default_index = i
                break
        
        selected_model = st.selectbox(
            "👇 选择思考引擎 (推荐 Flash):",
            available_models,
            index=default_index
        )
        
        # 显示配速提示
        delay_time = get_model_delay(selected_model)
        if delay_time > 10:
            st.warning(f"⚠️ 您选择了高精度模型 (Pro)。\n受限于 Google 免费配额，每页分析需冷却 {delay_time} 秒。建议切换回 Flash 以获得 10 倍速度。")
        else:
            st.info(f"⚡ 已激活高速模式 (Flash)。每页冷却 {delay_time} 秒。")

# --- 核心处理逻辑 ---
def analyze_slide(model, slide, index):
    """单独处理一页 Slide 的原子函数"""
    
    # 1. 提取文字
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

    # 3. 构造 Prompt
    prompt = """
    Analyze this presentation slide. Output strictly valid JSON.
    Do not use Markdown formatting (no ```json).
    JSON Structure:
    {
        "visual_summary": "1 sentence describing the visual layout",
        "scripts": {
            "beginner": "Speech script for non-experts (warm tone)",
            "standard": "Speech script for business (professional tone)",
            "expert": "Speech script for tech experts (deep tone)"
        },
        "knowledge_extension": {
            "entity": "Key technical term from slide",
            "trivia": "A surprising fact about this entity"
        }
    }
    """
    
    inputs = [prompt, f"Slide Content: {slide_text}"]
    if slide_image:
        inputs.append(slide_image)
    
    # 4. 调用 AI
    response = model.generate_content(inputs)
    
    # 5. 清洗数据
    clean_text = response.text.replace("```json", "").replace("```", "").strip()
    data = json.loads(clean_text)
    data['index'] = index
    return data

# --- 主界面 ---
st.title("🎙️ 智讲 SmartPresenter")
st.markdown("### 您的 AI 演示架构师：实时流式生成")

uploaded_file = st.file_uploader("📂 上传 PPTX 文件", type=['pptx'])

# 初始化 Session State (用于存储已生成的结果)
if 'generated_slides' not in st.session_state:
    st.session_state['generated_slides'] = []

if uploaded_file and api_key and available_models:
    if st.button("🚀 启动流水线 (Start Pipeline)", type="primary"):
        st.session_state['generated_slides'] = [] # 清空旧记录
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(selected_model)
        prs = Presentation(uploaded_file)
        total_slides = len(prs.slides)
        
        # 进度容器
        progress_bar = st.progress(0)
        status_box = st.empty()
        result_area = st.container() # 创建一个容器专门放结果
        
        delay_time = get_model_delay(selected_model)

        for i, slide in enumerate(prs.slides):
            current_idx = i + 1
            
            # --- 1. 状态更新 ---
            status_box.info(f"🧠 正在深度解析第 {current_idx} / {total_slides} 页...")
            progress_bar.progress(i / total_slides)
            
            try:
                # --- 2. 执行分析 ---
                slide_data = analyze_slide(model, slide, current_idx)
                
                # --- 3. 存入状态并立即渲染 ---
                st.session_state['generated_slides'].append(slide_data)
                
                with result_area:
                    # 动态渲染刚刚生成的那一页
                    with st.expander(f"📄 第 {current_idx} 页 | {slide_data.get('visual_summary')}", expanded=True):
                        c1, c2 = st.columns([2, 1])
                        with c1:
                            st.markdown("#### 🎙️ 演讲脚本")
                            tabs = st.tabs(["🟢 小白", "🔵 标准", "🔴 专家"])
                            tabs[0].write(slide_data['scripts']['beginner'])
                            tabs[1].write(slide_data['scripts']['standard'])
                            tabs[2].write(slide_data['scripts']['expert'])
                        with c2:
                            st.markdown("#### 🧠 知识点")
                            ext = slide_data['knowledge_extension']
                            st.info(f"**{ext['entity']}**\n\n{ext['trivia']}")

                # --- 4. 智能配速 (Smart Throttling) ---
                # 如果不是最后一页，就需要休息
                if i < total_slides - 1:
                    for t in range(delay_time, 0, -1):
                        status_box.warning(f"⏳ 正在遵守 API 限速规则，冷却中... {t}秒 (为了不被 Google 封锁)")
                        time.sleep(1)
                        
            except Exception as e:
                st.error(f"第 {current_idx} 页解析失败: {e}")
                time.sleep(5) # 出错也休息一下

        status_box.success("🎉 全部分析完成！")
        progress_bar.progress(1.0)

# --- 历史结果回显 (防止刷新丢失) ---
elif st.session_state['generated_slides']:
    st.divider()
    st.caption("📜 历史生成记录")
    for slide in st.session_state['generated_slides']:
        with st.expander(f"📄 第 {slide['index']} 页 | {slide.get('visual_summary')}", expanded=False):
             # 简化的回显 UI
             st.write(f"**标准话术:** {slide['scripts']['standard']}")
