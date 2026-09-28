import streamlit as st
import json
import difflib
import re

def get_diff_html(text1, text2):
    if not text1: text1 = ""
    if not text2: text2 = ""
    matcher = difflib.SequenceMatcher(None, text1, text2)
    result = []
    for opcode, a0, a1, b0, b1 in matcher.get_opcodes():
        if opcode == 'equal':
            result.append(text1[a0:a1])
        elif opcode == 'insert':
            result.append(f"<span style='background-color: #d4edda; color: #155724; font-weight: bold;'>{text2[b0:b1]}</span>")
        elif opcode == 'delete':
            result.append(f"<span style='background-color: #f8d7da; color: #721c24; text-decoration: line-through;'>{text1[a0:a1]}</span>")
        elif opcode == 'replace':
            result.append(f"<span style='background-color: #f8d7da; color: #721c24; text-decoration: line-through;'>{text1[a0:a1]}</span>")
            result.append(f"<span style='background-color: #d4edda; color: #155724; font-weight: bold;'>{text2[b0:b1]}</span>")
    return "".join(result).replace('\n', '<br>')

st.set_page_config(layout="wide", page_title="Textbook Review Helper")
st.title("Textbook Revision Review")

if 'review_status' not in st.session_state:
    st.session_state.review_status = {}

# --- FILE UPLOADERS ---
st.markdown("### Load Data")
col1, col2 = st.columns(2)
with col1:
    results_file = st.file_uploader("1. Upload LLM Results JSON", type=['json'])
with col2:
    progress_file_upload = st.file_uploader("2. Upload Existing Progress (Optional)", type=['json'])

if results_file is None:
    st.warning("Please upload an LLM results JSON file to begin.")
    st.stop()

# Load LLM results
try:
    results = json.load(results_file)
except json.JSONDecodeError:
    st.error("Invalid JSON file uploaded.")
    st.stop()

# Load Progress if uploaded
if progress_file_upload is not None:
    # Use file_id to prevent re-loading on every interaction
    if st.session_state.get('loaded_progress_id') != progress_file_upload.file_id:
        try:
            data = json.load(progress_file_upload)
            for item in data:
                uid = f"{item['chapter']}_{item['segment_id']}"
                st.session_state.review_status[uid] = item.get('status', 'approved')
                st.session_state[f"edit_{uid}"] = item.get('revised_text', '')
            st.session_state.loaded_progress_id = progress_file_upload.file_id
            st.success("Progress loaded successfully!")
        except json.JSONDecodeError:
            st.error("Invalid progress JSON file.")

# --- SIDEBAR & DOWNLOAD ---
export_data = []
reviewer_name = st.sidebar.text_input("👤 Reviewer Name (Required to save)", value=st.session_state.get('reviewer_name', ''), key='reviewer_name_input')

if reviewer_name:
    st.session_state.reviewer_name = reviewer_name

for r in results:
    uid = f"{r['chapter']}_{r['segment_id']}"
    if uid in st.session_state.review_status:
        item = r.copy()
        item['status'] = st.session_state.review_status[uid]
        if f"edit_{uid}" in st.session_state:
            item['revised_text'] = st.session_state[f"edit_{uid}"]
        item['reviewed_by'] = reviewer_name if reviewer_name else "Unknown"
        export_data.append(item)

st.sidebar.markdown("### Save Your Progress")
if not reviewer_name.strip():
    st.sidebar.warning("⚠️ Please enter your name above to download your progress.")
else:
    st.sidebar.download_button(
        label="💾 Download reviewed_segments.json",
        data=json.dumps(export_data, indent=2),
        file_name=f"reviewed_segments_{reviewer_name.strip().replace(' ', '_')}.json",
        mime="application/json"
    )
st.sidebar.markdown("---")

chapters = sorted(list(set(r.get('chapter', 'Unknown') for r in results)))
if not chapters:
    st.warning("No chapters found in the uploaded file.")
    st.stop()

selected_chapter = st.sidebar.selectbox("Select Chapter", chapters)
chapter_results = [r for r in results if r.get('chapter') == selected_chapter]

st.sidebar.subheader("Segments")

if 'current_idx' not in st.session_state:
    st.session_state.current_idx = 0

if st.session_state.current_idx >= len(chapter_results):
    st.session_state.current_idx = 0

for i, r in enumerate(chapter_results):
    uid = f"{r['chapter']}_{r['segment_id']}"
    status = st.session_state.review_status.get(uid, "pending")
    icon = "✅" if status == "approved" else "⏳"
    
    if st.sidebar.button(f"{icon} Segment {r['segment_id']}", key=f"nav_{uid}", type="primary" if i == st.session_state.current_idx else "secondary"):
        st.session_state.current_idx = i
        st.rerun()

# --- MAIN VIEW ---
current = chapter_results[st.session_state.current_idx]
uid = f"{current['chapter']}_{current['segment_id']}"

st.subheader(f"Chapter: {current['chapter']} - Segment {current['segment_id']}")

col_prev, col_next = st.columns(2)
with col_prev:
    if st.button("⬅️ Previous", disabled=st.session_state.current_idx == 0):
        st.session_state.current_idx -= 1
        st.rerun()
with col_next:
    if st.button("Next ➡️", disabled=st.session_state.current_idx == len(chapter_results) - 1):
        st.session_state.current_idx += 1
        st.rerun()

is_approved = st.session_state.review_status.get(uid) == "approved"
if st.button("✅ Approve Changes", type="primary" if is_approved else "secondary"):
    st.session_state.review_status[uid] = "approved"
    st.rerun()

# Format the rationale to have newlines for numbered lists like (1), (2) or 1., 2.
rationale_text = current.get('rationale', 'None')
rationale_text = re.sub(r'(\(\d+\))', r'\n\n\1', rationale_text)
rationale_text = re.sub(r'(?<!\d)(\d+\.) ', r'\n\n\1 ', rationale_text)
rationale_text = re.sub(r'(\([a-z]\))', r'\n  \1', rationale_text)

st.info(f"**LLM Rationale:**\n{rationale_text}")

c1, c2, c3 = st.columns(3)

orig_text = current.get('original_text', '')
rev_text = current.get('revised_text', '')

with c1:
    st.markdown("### Original")
    st.text_area("Original raw", value=orig_text, height=600, disabled=True)

with c2:
    st.markdown("### Revised (Editable)")
    edited_text = st.text_area("Edit text", value=st.session_state.get(f"edit_{uid}", rev_text), height=600, key=f"edit_{uid}")

with c3:
    st.markdown("### Diff")
    st.markdown(get_diff_html(orig_text, edited_text), unsafe_allow_html=True)
