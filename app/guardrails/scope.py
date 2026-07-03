import re
import numpy as np
import openai
import faiss

# Keywords that indicate out-of-scope personal data requests
_BLOCKLIST_PATTERNS = [
    re.compile(r"customer\s+\d+", re.IGNORECASE),
    re.compile(r"account\s+balance", re.IGNORECASE),
    re.compile(r"transaction\s+history", re.IGNORECASE),
    re.compile(r"(check|show|get|view)\s+(my\s+)?(balance|statement|transactions?)", re.IGNORECASE),
    re.compile(r"transfer\s+(money|funds|baht|thb)", re.IGNORECASE),
    re.compile(r"stock\s+(price|market|tip)", re.IGNORECASE),
    re.compile(r"(bitcoin|crypto|forex|invest)", re.IGNORECASE),
    re.compile(r"(weather|sports|recipe|joke|movie)", re.IGNORECASE),
]

# In-scope anchor phrases — used for embedding similarity gate
_ANCHOR_TEXTS = [
    "What is the annual leave policy for bank employees?",
    "How should staff handle confidential customer data?",
    "What are the expense reimbursement rules?",
    "What is the password policy for IT systems?",
    "What is the KYC process for new customers?",
    "What are the rules for working from home?",
    "How should employees report a security incident?",
    "What is the code of conduct for conflicts of interest?",
    "What is the anti-bribery and corruption policy?",
    "How does the performance review process work?",
    "What are the data classification tiers and handling rules?",
    "What is the IT acceptable use policy for software and devices?",
    "What are the social media guidelines for bank employees?",
    "What is the travel policy for flights and hotel bookings?",
    "How do I report misconduct through the whistleblower channel?",
]


class ScopeChecker:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        embedding_model: str = "text-embedding-3-small",
        threshold: float = 0.30,
    ):
        self._client = openai.OpenAI(api_key=api_key, base_url=base_url, timeout=30.0)
        self._embedding_model = embedding_model
        self._threshold = threshold
        self._anchor_vectors: np.ndarray | None = None

    def load_anchors(self) -> None:
        """Pre-compute anchor embeddings (call once at startup)."""
        response = self._client.embeddings.create(input=_ANCHOR_TEXTS, model=self._embedding_model)
        vectors = np.array([item.embedding for item in response.data], dtype="float32")
        faiss.normalize_L2(vectors)
        self._anchor_vectors = vectors

    def check_scope(self, text: str) -> bool:
        """
        Return True if the text is in scope (i.e. about bank policies).
        Return False if it should be refused.
        """
        # Layer 1: keyword blocklist
        for pattern in _BLOCKLIST_PATTERNS:
            if pattern.search(text):
                return False

        # Layer 2: embedding similarity gate
        if self._anchor_vectors is not None:
            response = self._client.embeddings.create(input=[text], model=self._embedding_model)
            query_vec = np.array([response.data[0].embedding], dtype="float32")
            faiss.normalize_L2(query_vec)
            scores = (self._anchor_vectors @ query_vec.T).flatten()
            if float(scores.max()) < self._threshold:
                return False

        return True
