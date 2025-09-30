# helpers/index.py
# Tiny inverted index with length-normalized term scoring (still no heavy deps)

import re
from collections import defaultdict
from math import log

TOKEN_RE = re.compile(r"[a-z0-9]+")

def _tokenize(text: str):
    return TOKEN_RE.findall((text or "").lower())

def build_index(chunks):
    """
    Builds a lightweight inverted index:
      inv[token] -> list of (chunk_idx, term_freq_in_chunk)
    Also stores doc length (in tokens) for basic normalization.
    """
    inv = defaultdict(list)
    lens = []
    for i, c in enumerate(chunks):
        toks = _tokenize(c.get("text", ""))
        lens.append(max(1, len(toks)))
        if not toks:
            continue
        # term frequencies per chunk
        tf = defaultdict(int)
        for t in toks:
            tf[t] += 1
        for t, cnt in tf.items():
            inv[t].append((i, cnt))
    N = max(1, len(chunks))
    # doc frequency for idf
    df = {t: len(posts) for t, posts in inv.items()}
    idf = {t: log((N + 1) / (df_t + 0.5)) + 1.0 for t, df_t in df.items()}  # smoothed
    return {"chunks": chunks, "inv": inv, "lens": lens, "idf": idf, "N": N}

def retrieve(index, query, top_k=6):
    if not index or not query:
        return []
    inv = index["inv"]; lens = index["lens"]; idf = index["idf"]
    q_tokens = _tokenize(query)
    if not q_tokens:
        return []

    scores = defaultdict(float)
    for qt in q_tokens:
        postings = inv.get(qt)
        if not postings:
            continue
        w_idf = idf.get(qt, 1.0)
        for i, tf in postings:
            # simple TF * IDF with doc length normalization
            scores[i] += (tf / lens[i]) * w_idf

    if not scores:
        return []

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:max(1, top_k)]
    # enrich with score, return in the same dict shape your UI expects
    out = []
    chunks = index["chunks"]
    for i, s in ranked:
        d = dict(chunks[i])  # shallow copy
        d["score"] = float(s)
        out.append(d)
    return out
