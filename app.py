import streamlit as st
import google.generativeai as genai
from pptx import Presentation
import time
import ai_engine  # 引用刚才那个文件

st.set_page_config(page_title="智讲 SmartPresenter", layout="wide", page_icon="🧠")

# --- 侧边栏 ---
with st.sidebar:
    st.title("🧠 智讲 Pro")
    st.caption("双核架构版")
    api_key = st.text_input("🔑 Google API Key", type="password")
    
    available_models = []
    if api_key:
        # 调用 ai_engine 里的函数
        success, result = ai_engine.configure_genai(api_key)
        if success:
            available_models = result
            st.success(f"✅ 连接成功")
        else:
            st.error(f"❌ 连接失败: {result}")
    
    if available_models:
        default_index = 0
        for i, name in enumerate(available_models):
            if "flash" in name and "1.5" in name:
                default_index = i
                break
        selected_model = st.selectbox("👇 选择模型:", available_models, index=default_index)
    else:
        selected_model = st.selectbox("模型:", ["models/gemini-1.5-flash"])

# --- 回调函数 ---
def update_status_ui(slide_index, wait_seconds, attempt, max_retries):
    with st.empty():
        for t in range(wait_seconds, 0, -1):
            st.warning(f"⏳ 第 {slide_index} 页触发限流，冷却中... {t}s (重试 {attempt}/{max_retries})")
            time.sleep(1)

# --- 主界面 ---
st.title("🎙️ 智讲 SmartPresenter")
uploaded_file = st.file_uploader("上传 PPTX", type=['pptx'])

if 'results' not in st.session_state:
    st.session_state['results'] = []

if uploaded_file and api_key and available_models:
    if st.button("🚀 启动分析"):
        st.session_state['results'] = [] 
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(selected_model)
        prs = Presentation(uploaded_file)
        
        progress_bar = st.progress(0)
        status_box = st.empty()
        result_area = st.container()
        total = len(prs.slides)
        
        for i, slide in enumerate(prs.slides):
            idx = i + 1
            status_box.info(f"🚀 正在分析第 {idx}/{total} 页...")
            progress_bar.progress(i / total)
            
            try:
                # 调用 ai_engine
                data = ai_engine.analyze_slide_content(model, slide, idx, status_callback=update_status_ui)
                data['index'] = idx
                st.session_state['results'].append(data)
                
                with result_area:
                    with st.expander(f"✅ 第 {idx} 页 | {data.get('visual_summary')}", expanded=True):
                        st.write(data['scripts']['standard'])
                
                time.sleep(2)

            except Exception as e:
                st.error(f"第 {idx} 页失败: {e}")
        
        status_box.success("🎉 完成！")
        progress_bar.progress(1.0)

# ... (前面的代码保持不变)

elif st.session_state['results']:
    st.divider()
    
    # --- 新增功能：生成下载内容 ---
    def generate_report(results):
        report = "# 🎙️ 智讲 SmartPresenter 分析报告\n\n"
        for slide in results:
            report += f"## 第 {slide['index']} 页\n"
            report += f"**视觉摘要**: {slide.get('visual_summary', 'N/A')}\n\n"
            report += "### 🗣️ 演讲稿 (标准版)\n"
            report += f"{slide['scripts']['standard']}\n\n"
            report += "### 💡 知识扩展\n"
            report += f"**{slide['knowledge_extension']['entity']}**: {slide['knowledge_extension']['trivia']}\n"
            report += "---\n\n"
        return report

    # 准备下载数据
    report_text = generate_report(st.session_state['results'])
    
    # 下载按钮布局
    col1, col2 = st.columns([3, 1])
    with col1:
        st.success(f"🎉 分析完成！共生成 {len(st.session_state['results'])} 页讲稿。")
    with col2:
        st.download_button(
            label="📥 下载完整报告 (.md)",
            data=report_text,
            file_name="smart_presenter_report.md",
            mime="text/markdown"
        )

    # 结果回显
    for data in st.session_state['results']:
        with st.expander(f"✅ 第 {data['index']} 页 | {data.get('visual_summary')}"):
            st.markdown(f"**演讲稿**: {data['scripts']['standard']}")
            st.info(f"💡 {data['knowledge_extension']['trivia']}")
