# home.py
# Streamlit App UI/Layout ONLY (no heavy logic here).
# Purpose: Internal Docs Q&A assistant for employees.

import pandas as pd
import streamlit as st

# ------------------------ IMPORT HOOKS -------------------
# If you prefer flat files (no package), you can also do: import docs as docs_mod, etc.
import helpers.docs as docs_mod
import helpers.index as index_mod
import helpers.qa as qa_mod

process_uploads = getattr(docs_mod, "process_uploads", None)
build_index     = getattr(index_mod, "build_index", None)
retrieve        = getattr(index_mod, "retrieve", None)
synthesize_answer       = getattr(qa_mod, "synthesize_answer", None)
suggest_sample_questions = getattr(qa_mod, "suggest_sample_questions", None)

# ------------------------ CONFIG ------------------------
st.set_page_config(page_title="Internal Docs Q&A", page_icon="📘", layout="wide")

# -------------------- SESSION STATE ---------------------
ss = st.session_state
ss.setdefault("chat_history", [])   # [{"user": str, "assistant": str, "sources": List[dict]}]
ss.setdefault("docs", [])           # [{"filename": str, "text": str, "page": int?}]
ss.setdefault("chunks", [])         # [{"id": str, "filename": str, "text": str}]
ss.setdefault("index", None)        # retriever/index
ss.setdefault("sample_qs", [])      # cached sample questions
ss.setdefault("samples_fp", None)   # fingerprint of chunks for re-gen control
ss.setdefault("last_upload_fp", None)

# ------------------------ STYLES -------------------------
st.markdown(
    """
    <style>
    .block-container { padding-top: 1.5rem; }
    .stChatFloatingInputContainer { border-top: 1px solid #eee; }
    .small-muted { color: #6c757d; font-size: 0.9rem; }
    .user-msg {
        background-color: #e6f3ff;
        padding: 0.8rem 1rem;
        border-radius: 0.5rem;
        margin-bottom: 0.5rem;
    }
    .assistant-msg {
        background-color: #f0f2f6;
        padding: 0.8rem 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------------- HEADER ------------------------
st.markdown("<h1 style='text-align:center;margin-bottom:.25rem;'>What do you need to know?</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center;color:gray;margin-top:0;'>Upload internal docs (handbooks, SOPs, FAQs). Ask questions. Get grounded answers.</p>", unsafe_allow_html=True)

# Center controls (e.g., toggles)
_, mid, _ = st.columns([2.2, 1, 0.9])
with mid:
    show_sources = st.checkbox("Show Source Snippets", value=True)

# --------------------- SIDEBAR: LIBRARY ------------------
with st.sidebar:
    st.header("📂 Document Library")

    uploaded_files = st.file_uploader(
        "Upload internal documentation",
        type=["pdf", "docx", "txt", "md"],
        accept_multiple_files=True,
        help="Drag & drop multiple files. The app will parse, chunk, and index them.",
        key="uploader"
    )

    def _files_fp(files):
        # lightweight fingerprint to avoid re-processing on every rerun
        return tuple((getattr(f, "name", f"f{i}"), getattr(f, "size", 0)) for i, f in enumerate(files or []))

    if uploaded_files:
        if process_uploads is None:
            st.warning("Upload handler not available. Implement `helpers/docs.process_uploads`.")
        else:
            fp = _files_fp(uploaded_files)
            if fp != ss.last_upload_fp:
                with st.spinner("Processing documents..."):
                    try:
                        result = process_uploads(uploaded_files)  # {"docs": [...], "chunks": [...]}
                        new_docs   = result.get("docs", []) or []
                        new_chunks = result.get("chunks", []) or []

                        if not new_docs or not new_chunks:
                            st.info("No readable text detected in uploaded files.")
                        else:
                            # Replace (not extend): this selection is the active library
                            ss.docs   = new_docs
                            ss.chunks = new_chunks

                            # Build/refresh index (optional but recommended)
                            if build_index is not None:
                                try:
                                    ss.index = build_index(ss.chunks)
                                except Exception as e:
                                    ss.index = None
                                    st.error(f"Index building failed: {e}")

                            st.success(f"Loaded {len(ss.docs)} document(s) • {len(ss.chunks)} chunk(s).")

                        ss.last_upload_fp = fp
                    except Exception as e:
                        st.error(f"Document processing failed: {e}")

    # Library stats
    st.caption(f"Documents: **{len(ss.docs)}** | Chunks: **{len(ss.chunks)}**")

    # Preview table
    if ss.docs:
        df = pd.DataFrame([{"File": d["filename"], "Characters": len(d.get("text", ""))} for d in ss.docs])
        st.dataframe(df, use_container_width=True, height=200)

    st.markdown("---")
    colA, colB = st.columns(2)
    with colA:
        if st.button("🧹 Clear Library", use_container_width=True):
            ss.docs = []
            ss.chunks = []
            ss.index = None
            ss.sample_qs = []
            ss.samples_fp = None
            ss.last_upload_fp = None
            st.success("Cleared uploaded docs & index.")
    with colB:
        if st.button("🗑️ Clear Chat", use_container_width=True):
            ss.chat_history = []
            st.success("Cleared chat history.")

# ------------------- SAMPLE QUESTIONS -------------------
SAMPLE_Q_COUNT = 6  # set how many you want

def _chunks_fp(chunks):
    # fingerprint to detect when chunks change (id + length)
    return tuple((c.get("id"), len(c.get("text", ""))) for c in chunks)

if ss.chunks and suggest_sample_questions is not None:
    fp = _chunks_fp(ss.chunks)
    if fp != ss.samples_fp:
        merged = "\n\n".join(c.get("text", "") for c in ss.chunks)
        try:
            qs = suggest_sample_questions(merged) or []
        except Exception:
            qs = []
        # keep first X unique, trimmed
        seen, out = set(), []
        for q in qs:
            t = (q or "").strip()
            if t and t not in seen:
                out.append(t[:120])
                seen.add(t)
            if len(out) >= SAMPLE_Q_COUNT:
                break
        ss.sample_qs = out
        ss.samples_fp = fp

if ss.sample_qs:
    with st.expander("💡 Try a sample question"):
        cols = st.columns(3)
        for i, q in enumerate(ss.sample_qs):
            with cols[i % 3]:
                if st.button(q, use_container_width=True, key=f"sample_q_{i}"):
                    ss["_prefill"] = q

# ------------------- INITIAL WELCOME --------------------
if not ss.chat_history and not ss.docs:
    st.info("Welcome! Upload documents in the sidebar and ask a question to get started.")

# ------------------- CHAT HISTORY VIEW ------------------
for message in ss.chat_history:
    st.markdown(f'<div class="user-msg"><b>You:</b> {message["user"]}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="assistant-msg"><b>Assistant:</b><br>{message["assistant"]}</div>', unsafe_allow_html=True)
    sources = message.get("sources")
    # Source expander is not inside the colored box
    if show_sources and sources:
        with st.expander("View Top Source"):
            src = sources[0]  # Show only the most relevant source
            fn = src.get("filename", "Unknown")
            pg = src.get("page")
            pg_str = f" (p. {pg})" if pg else ""
            st.markdown(f"**Source**: `{fn}{pg_str}`")
            txt = src.get("text", "") or ""
            st.markdown(txt[:1000] + ("..." if len(txt) > 1000 else ""))

# ------------------- CHAT INPUT WORKFLOW ----------------
placeholder = "Ask about your uploaded document"
user_input = st.chat_input(placeholder)

if not user_input and ss.get("_prefill"):
    user_input = ss.pop("_prefill")

if user_input:
    if not ss.chunks:
        assistant_msg = ("I don’t have any internal documents yet. "
                         "Please upload your handbook, policies, or SOPs in the sidebar.")
        ss.chat_history.append({"user": user_input, "assistant": assistant_msg, "sources": []})
        st.experimental_rerun()

    elif retrieve is None or synthesize_answer is None:
        assistant_msg = (
            "The app layout is ready, but retrieval/answering helpers are not configured.\n\n"
            "Please implement:\n"
            "- `helpers/index.retrieve(index, query, top_k)`\n"
            "- `helpers/qa.synthesize_answer(question, contexts)`\n"
        )
        ss.chat_history.append({"user": user_input, "assistant": assistant_msg, "sources": []})
        st.experimental_rerun()

    else:
        # Define a score threshold for what's considered a "strong" match.
        # This will depend on your indexing/scoring method. For the simple TF-IDF
        # here, scores are often low. A value around 0.1 is a reasonable starting point.
        # You can tune this value to be more or less strict.
        SCORE_THRESHOLD = 0.1

        with st.spinner("Searching your internal docs..."):
            try:
                contexts = retrieve(ss.index, user_input, top_k=6) or []
            except Exception as e:
                contexts = []
                st.error(f"Retrieval failed: {e}")
        
        # Check if the top result meets the relevance threshold
        if not contexts or contexts[0].get("score", 0.0) < SCORE_THRESHOLD:
            answer = "No strong matches found—try narrower terms."
            contexts = [] # Clear contexts so no sources are shown
        else:
            with st.spinner("Drafting an answer..."):
                try:
                    answer = synthesize_answer(user_input, contexts)
                except Exception as e:
                    answer = f"Sorry, I couldn't synthesize an answer. ({e})"
        
        ss.chat_history.append({"user": user_input, "assistant": answer, "sources": contexts})

        # Render this turn immediately
        st.markdown(f'<div class="user-msg"><b>You:</b> {user_input}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="assistant-msg"><b>Assistant:</b><br>{answer}</div>', unsafe_allow_html=True)
        if show_sources and contexts:
            with st.expander("View Top Source"):
                src = contexts[0]
                fn = src.get("filename", "Unknown")
                pg = src.get("page")
                pg_str = f" (p. {pg})" if pg else ""
                st.markdown(f"**Source**: `{fn}{pg_str}`")
                txt = src.get("text", "") or ""
                st.markdown(txt[:1000] + ("..." if len(txt) > 1000 else ""))
