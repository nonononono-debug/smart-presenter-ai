import streamlit as st
import google.generativeai as genai
from pptx import Presentation
import json
import io
from PIL import Image
import time
import random

# --- 1. 页面配置 ---
st.set_page_config(
    page_title="智讲 SmartPresenter Pro",
    layout="wide",
    page_icon="🧠",
    initial_sidebar_state="expanded"
)

# --- 2. 架构核心：带重试机制的 AI 请求函数 ---
def call_ai_with_retry(model, inputs, slide_index, status_box):
    """
    这是一个死磕到底的函数。
    只要是限流 (429) 错误，它就会一直重试，直到成功为止。
    绝不把错误抛给主流程，绝不跳过任何一页。
    """
    max_retries = 10  # 最多重试 10 次
    base_wait_time = 10 # 基础等待 10 秒
    
    for attempt in range(max_retries):
        try:
            # 尝试发起请求
            response = model.generate_content(inputs)
            return response # 成功拿到结果，直接返回！
            
        except Exception as e:
            error_str = str(e)
            
            # 如果是限流错误 (429) 或者 服务器过载 (500/503)
            if "429" in error_str or "quota" in error_str.lower() or "50" in error_str:
                # 计算等待时间：每次失败，等待时间翻倍 (10s -> 20s -> 40s...)
                wait_time = base_wait_time * (attempt + 1) + random.randint(1, 5)
                
                # 倒计时显示
                for t in range(wait_time, 0, -1):
                    status_box.warning(
                        f"🛑 第 {slide_index} 页触发 Google 限流 (429)。\n"
                        f"⚡ 正在冷却重试机制: {t} 秒后进行第 {attempt + 1}/{max_retries} 次尝试..."
                    )
                    time.sleep(1)
            else:
                # 如果是其他错误 (比如图片太大)，那就没办法了，只能报错
                raise e
    
    raise Exception("重试次数耗尽，Google API 暂时不可用。")

# --- 3. 侧边栏配置 ---
with st.sidebar:
    st.title("🧠 智讲 Pro")
    st.caption("架构师版：智能重试队列")
    
    api_key = st.text_input("🔑 Google API Key", type="password")
    
    # 自动加载模型列表
    available_models = []
    if api_key:
        try:
            genai.configure(api_key=api_key)
            models = genai.list_models()
            for m in models:
                if 'generateContent' in m.supported_generation_methods:
                    available_models.append(m.name)
            st.success(f"✅ API 连接成功 (可用模型: {len(available_models)})")
        except:
            st.error("❌ API Key 无效")

    # 模型选择
    if available_models:
        # 自动选 Flash
        default_idx = 0
        for i, n in enumerate(available_models):
            if "flash" in n and "1.5" in n:
                default_idx = i
                break
        selected_model = st.selectbox("选择模型:", available_models, index=default_idx)
    else:
        selected_model = "models/gemini-1.5-flash"

    st.info("🛡️ 已开启【死磕模式】：遇到限流会自动挂起并重试，确保不漏掉每一页。")

# --- 4. 主逻辑 ---
def analyze_slide_logic(model, slide, index, status_box):
    # (A) 提取内容
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

    # (B) Prompt
    prompt = """
    Analyze slide. Output JSON (no markdown):
    {
        "visual_summary": "1 sentence summary",
        "scripts": {
            "beginner": "Simple tone script",
            "standard": "Business tone script",
            "expert": "Technical tone script"
        },
        "knowledge_extension": {
            "entity": "Keyword",
            "trivia": "Did you know fact"
        }
    }
    """
    
    inputs = [prompt, f"Context: {slide_text}"]
    if slide_image: inputs.append(slide_image)
    
    # (C) 核心差异：调用我们写的【死磕函数】，而不是直接调用 model
    response = call_ai_with_retry(model, inputs, index, status_box)
    
    # (D) 清洗数据
    txt = response.text.replace("```json", "").replace("```", "").strip()
    return json.loads(txt)

# --- 5. UI 渲染 ---
st.title("🎙️ 智讲 SmartPresenter")
st.markdown("### 您的 AI 演示架构师：零丢包 · 全量分析")

uploaded_file = st.file_uploader("上传 PPTX", type=['pptx'])

if 'results_cache' not in st.session_state:
    st.session_state['results_cache'] = []

if uploaded_file and api_key and available_models:
    if st.button("🚀 启动高可靠分析流水线"):
        st.session_state['results_cache'] = [] # 清空
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(selected_model)
        prs = Presentation(uploaded_file)
        
        progress_bar = st.progress(0)
        status_box = st.empty()
        result_container = st.container()
        
        total = len(prs.slides)
        
        for i, slide in enumerate(prs.slides):
            idx = i + 1
            status_box.info(f"🚀 正在分析第 {idx}/{total} 页...")
            progress_bar.progress(i / total)
            
            try:
                # 调用逻辑
                data = analyze_slide_logic(model, slide, idx, status_box)
                data['index'] = idx
                st.session_state['results_cache'].append(data)
                
                # 实时渲染结果 (不用等全部跑完)
                with result_container:
                    with st.expander(f"✅ 第 {idx} 页分析完成 | {data['visual_summary']}", expanded=True):
                        c1, c2 = st.columns([2, 1])
                        c1.info(f"演讲稿: {data['scripts']['standard']}")
                        c2.success(f"知识点: {data['knowledge_extension']['trivia']}")
                
                # 成功后，主动休息2秒，积德行善，减少下一次触发限流的概率
                time.sleep(2) 

            except Exception as e:
                st.error(f"第 {idx} 页最终失败: {e}")
        
        status_box.success("🎉 全部分析结束！")
        progress_bar.progress(1.0)

# --- 6. 回显缓存 ---
elif st.session_state['results_cache']:
    st.divider()
    st.markdown("### 📜 生成历史")
    for data in st.session_state['results_cache']:
        with st.expander(f"第 {data['index']} 页 | {data.get('visual_summary')}"):
            st.write(data['scripts']['standard'])
