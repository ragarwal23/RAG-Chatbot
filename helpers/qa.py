# helpers/qa.py
# Minimal Gemini helpers for grounded QA + simple sample questions

from typing import List, Dict
import json
import re

from langchain_google_vertexai import ChatVertexAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

# ---------------- Configuration ----------------
PROJECT_ID = "stoked-courier-475320-g9"         # <-- change if needed
LOCATION   = "us-central1"
MODEL_NAME = "gemini-2.0-flash-001"

# Uses Application Default Credentials (ADC).
# In Cloud Run/Cloud Shell: ensure service account has aiplatform.user.
llm = ChatVertexAI(
    model_name=MODEL_NAME,
    project=PROJECT_ID,
    location=LOCATION,
    temperature=0.0,
)

# ---------------- Prompts ----------------
ANSWER_PROMPT = PromptTemplate(
    input_variables=["question", "context"],
    template=(
        "You are a helpful internal assistant. Use ONLY the context to answer.\n"
        "If the answer is not present in the context, say you don't know.\n\n"
        "Question:\n{question}\n\n"
        "Context (numbered snippets):\n{context}\n\n"
        "Instructions:\n"
        "- Be concise and accurate.\n"
        "- If helpful, cite snippets like [1], [2] based on the numbering below.\n\n"
        "Answer:"
    ),
)

SAMPLES_PROMPT = PromptTemplate(
    input_variables=["doc_text"],
    template=(
        "You help users explore an internal document. Based ONLY on the text below, "
        "suggest 5-7 concise, practical questions a user might ask about it. "
        "Do not invent topics outside this text. Respond ONLY with a JSON list of strings.\n\n"
        "Document snippet:\n{doc_text}\n"
    ),
)

# ---------------- Public API ----------------
def synthesize_answer(question: str, contexts: List[Dict]) -> str:
    """
    Make a grounded answer using Gemini and the retrieved contexts.
    Each context dict is expected to include: { 'filename': str, 'text': str, 'score': float? }
    """
    try:
        # Build a compact, numbered context block
        blocks = []
        total = 0
        budget = 12000  # simple character budget for prompt size
        for i, c in enumerate(contexts, start=1):
            fn = c.get("filename", "Unknown")
            tx = (c.get("text", "") or "").strip()
            # trim if needed to fit budget
            take = min(len(tx), max(0, budget - total))
            if take <= 0:
                break
            snippet = tx[:take]
            blocks.append(f"[{i}] {fn}\n{snippet}")
            total += take + len(fn) + 6

        context_block = "\n\n".join(blocks) if blocks else "(no context provided)"

        chain = LLMChain(llm=llm, prompt=ANSWER_PROMPT, verbose=False)
        raw = chain.run({"question": question, "context": context_block})
        # Light cleanup
        return re.sub(r"\n{3,}", "\n\n", raw).strip()
    except Exception as e:
        return f"Sorry, I couldn't generate an answer right now. ({e})"

def suggest_sample_questions(docs_text: str) -> List[str]:
    """
    Simple, doc-grounded sample Qs. Feeds a slice of the uploaded text to Gemini.
    Returns [] if anything goes wrong (UI will just skip showing samples).
    """
    try:
        # Keep it small & fast
        doc_text = (docs_text or "")[:8000]
        if not doc_text.strip():
            return []

        chain = LLMChain(llm=llm, prompt=SAMPLES_PROMPT, verbose=False)
        raw = chain.run({"doc_text": doc_text}).strip()

        # Expect a JSON list of strings
        items = json.loads(raw)
        out = []
        seen = set()
        for s in items:
            if isinstance(s, str):
                t = s.strip()
                if t and t not in seen:
                    out.append(t[:120])  # keep short
                    seen.add(t)
        return out[:7]
    except Exception:
        return []
