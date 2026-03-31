"""
Extração de embeddings com modelos BERT pré-treinados em português clínico.

Modelos suportados (em ordem de preferência para prontuários brasileiros):

  pucpr/biobertpt-clin   — BioBERTpt treinado exclusivamente em narrativas
                           clínicas de prontuários brasileiros (EHR).
                           Referência: Schneider et al., ACL Clinical NLP 2020.

  pucpr/biobertpt-all    — BioBERTpt treinado em narrativas clínicas +
                           literatura biomédica (PubMed / SciELO).

  neuralmind/bert-base-portuguese-cased  — BERTimbau Base: BERT geral para
                           português brasileiro, treinado no BrWaC (1B tokens).
                           Referência: Souza et al., STIL 2020.

  neuralmind/bert-large-portuguese-cased — BERTimbau Large: maior precisão,
                           mais custo computacional.

Estratégia de embedding:
  - Mean-pooling sobre tokens válidos (supera [CLS] isolado em classificação).
  - Janela deslizante (sliding window) para documentos > 512 tokens.
  - L2-normalização automática antes de uso em classificadores sklearn.
  - Processamento em lote (batch) com inferência sem gradiente.
  - Cache LRU opcional para acelerar análises repetidas.
"""

import logging
from functools import lru_cache
from typing import List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Importações opcionais — torch e transformers não são obrigatórios para o
# modo somente-regras do sistema.
# ---------------------------------------------------------------------------
try:
    import torch
    from transformers import AutoTokenizer, AutoModel

    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

#: Modelo padrão: BioBERTpt clínico. Melhor para prontuários brasileiros.
DEFAULT_MODEL = "pucpr/biobertpt-clin"

#: Fallback quando biobertpt não está disponível ou para uso geral em PT.
FALLBACK_MODEL = "neuralmind/bert-base-portuguese-cased"

#: Dimensão dos embeddings para os modelos BERT-Base (todas as variantes).
BERT_BASE_DIM = 768

#: Número máximo de tokens suportado pelo BERT (incluindo [CLS] e [SEP]).
MAX_BERT_TOKENS = 512

#: Sobreposição entre janelas deslizantes (em tokens).
WINDOW_STRIDE = 128


# ---------------------------------------------------------------------------
# Utilitários internos
# ---------------------------------------------------------------------------


def _mean_pool(last_hidden: "torch.Tensor", attention_mask: "torch.Tensor") -> np.ndarray:
    """
    Mean-pooling sobre tokens reais (exclui padding).

    Args:
        last_hidden:    (batch, seq_len, hidden_size)
        attention_mask: (batch, seq_len)

    Returns:
        numpy array de shape (batch, hidden_size)
    """
    mask = attention_mask.unsqueeze(-1).float()          # (B, S, 1)
    summed = (last_hidden * mask).sum(dim=1)             # (B, H)
    count = mask.sum(dim=1).clamp(min=1e-9)              # (B, 1)
    return (summed / count).detach().cpu().numpy()        # (B, H)


def _l2_normalize(matrix: np.ndarray) -> np.ndarray:
    """Normalização L2 linha a linha; evita divisão por zero."""
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return matrix / norms


# ---------------------------------------------------------------------------
# Classe principal
# ---------------------------------------------------------------------------


class BertEmbedder:
    """
    Extrai embeddings de texto usando modelos BERT para português clínico.

    Uso básico:
        embedder = BertEmbedder()                        # usa biobertpt-clin
        vec = embedder.embed("Paciente com lesão corporal.")
        # vec.shape → (768,)

    Uso com modelo alternativo:
        embedder = BertEmbedder("neuralmind/bert-base-portuguese-cased")

    Uso em lote:
        X = embedder.embed_batch(["texto1", "texto2", "texto3"])
        # X.shape → (3, 768)

    Integração com sklearn:
        from sklearn.linear_model import LogisticRegression
        clf = LogisticRegression()
        clf.fit(embedder.embed_batch(train_texts), train_labels)

    Raises:
        ImportError: se torch e transformers não estiverem instalados.
    """

    def __init__(
        self,
        model_id: str = DEFAULT_MODEL,
        device: Optional[str] = None,
        batch_size: int = 16,
        max_length: int = MAX_BERT_TOKENS,
        stride: int = WINDOW_STRIDE,
    ) -> None:
        """
        Args:
            model_id:   ID do modelo HuggingFace. Padrão: biobertpt-clin.
            device:     "cpu", "cuda" ou None (auto-detecta GPU se disponível).
            batch_size: número de textos processados por vez.
            max_length: janela máxima em tokens (≤ 512).
            stride:     sobreposição entre janelas para documentos longos.
        """
        if not HAS_TRANSFORMERS:
            raise ImportError(
                "torch e transformers são necessários para BertEmbedder.\n"
                "Execute: pip install torch transformers"
            )

        self.model_id = model_id
        self.batch_size = batch_size
        self.max_length = min(max_length, MAX_BERT_TOKENS)
        self.stride = stride

        # Seleciona dispositivo
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        logger.info("Carregando modelo '%s' em '%s'…", model_id, self.device)
        self._tokenizer = AutoTokenizer.from_pretrained(model_id)
        self._model = AutoModel.from_pretrained(model_id)
        self._model.eval()
        self._model.to(self.device)
        logger.info("Modelo carregado.")

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def embed(self, text: str) -> np.ndarray:
        """
        Retorna o embedding (shape 768,) para um único texto.

        Documentos com mais de `max_length` tokens são processados com
        janela deslizante e os embeddings das janelas são combinados por
        média ponderada pelo tamanho de cada janela.
        """
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: List[str]) -> np.ndarray:
        """
        Retorna matriz de embeddings (n_texts, hidden_size) L2-normalizados.

        Processa em lotes de `batch_size` textos para controle de memória.
        """
        all_embeddings: List[np.ndarray] = []

        for i in range(0, len(texts), self.batch_size):
            batch = texts[i: i + self.batch_size]
            embeddings = self._embed_batch_raw(batch)
            all_embeddings.append(embeddings)

        matrix = np.vstack(all_embeddings)        # (N, H)
        return _l2_normalize(matrix)

    @property
    def embedding_dim(self) -> int:
        """Dimensão dos vetores produzidos pelo modelo."""
        return self._model.config.hidden_size

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    def _embed_batch_raw(self, texts: List[str]) -> np.ndarray:
        """
        Processa um lote de textos; textos longos usam janela deslizante.
        Retorna array (len(texts), hidden_size) não-normalizado.
        """
        # Separar textos curtos (caben em uma janela) dos longos
        results = np.zeros((len(texts), self.embedding_dim), dtype=np.float32)
        short_indices, short_texts = [], []
        long_indices, long_texts = [], []

        for idx, text in enumerate(texts):
            n_tokens = len(self._tokenizer.tokenize(text))
            # -2 para [CLS] e [SEP]
            if n_tokens <= self.max_length - 2:
                short_indices.append(idx)
                short_texts.append(text)
            else:
                long_indices.append(idx)
                long_texts.append(text)

        # Textos curtos: processamento padrão em lote
        if short_texts:
            embs = self._encode_short(short_texts)
            for list_pos, orig_idx in enumerate(short_indices):
                results[orig_idx] = embs[list_pos]

        # Textos longos: janela deslizante individual
        for orig_idx, text in zip(long_indices, long_texts):
            results[orig_idx] = self._encode_long(text)

        return results

    def _encode_short(self, texts: List[str]) -> np.ndarray:
        """Codifica textos que cabem em uma única janela BERT."""
        encoded = self._tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=self.max_length,
            return_tensors="pt",
        ).to(self.device)

        with torch.no_grad():
            outputs = self._model(**encoded)

        return _mean_pool(outputs.last_hidden_state, encoded["attention_mask"])

    def _encode_long(self, text: str) -> np.ndarray:
        """
        Codifica documento longo com janela deslizante (sliding window).

        Cada janela sobrepõe a anterior em `stride` tokens. Os embeddings
        das janelas são combinados por média ponderada pelo número de
        tokens reais de cada janela.
        """
        encoded = self._tokenizer(
            text,
            truncation=True,
            max_length=self.max_length,
            stride=self.stride,
            return_overflowing_tokens=True,
            return_tensors="pt",
            padding="max_length",
        )

        # Remove a chave de mapeamento que o modelo não aceita
        encoded.pop("overflow_to_sample_mapping", None)

        chunk_embeddings: List[np.ndarray] = []
        chunk_token_counts: List[int] = []
        n_chunks = encoded["input_ids"].shape[0]

        for i in range(n_chunks):
            chunk = {k: v[i].unsqueeze(0).to(self.device) for k, v in encoded.items()}
            with torch.no_grad():
                out = self._model(**chunk)
            emb = _mean_pool(out.last_hidden_state, chunk["attention_mask"])
            # Número de tokens reais nesta janela (exclui padding)
            real_tokens = int(chunk["attention_mask"].sum().item())
            chunk_embeddings.append(emb[0])
            chunk_token_counts.append(real_tokens)

        # Média ponderada pelo número de tokens reais
        weights = np.array(chunk_token_counts, dtype=np.float32)
        weights /= weights.sum()
        stacked = np.stack(chunk_embeddings, axis=0)          # (C, H)
        return (stacked * weights[:, None]).sum(axis=0)        # (H,)


# ---------------------------------------------------------------------------
# Fábrica conveniente
# ---------------------------------------------------------------------------


def make_embedder(
    prefer_clinical: bool = True,
    device: Optional[str] = None,
    **kwargs,
) -> Optional["BertEmbedder"]:
    """
    Cria um BertEmbedder com fallback automático de modelo.

    Tenta carregar biobertpt-clin (clínico) e cai para BERTimbau Base
    se o primeiro falhar. Retorna None se transformers não estiver instalado.

    Args:
        prefer_clinical: se True, tenta biobertpt-clin antes de BERTimbau.
        device:          dispositivo ("cpu", "cuda" ou None para auto).
        **kwargs:        repassados ao BertEmbedder (batch_size, stride…).

    Returns:
        BertEmbedder pronto para uso, ou None.
    """
    if not HAS_TRANSFORMERS:
        logger.warning(
            "torch/transformers não instalados. "
            "Execute: pip install torch transformers"
        )
        return None

    candidates = (
        [DEFAULT_MODEL, FALLBACK_MODEL]
        if prefer_clinical
        else [FALLBACK_MODEL, DEFAULT_MODEL]
    )

    for model_id in candidates:
        try:
            return BertEmbedder(model_id=model_id, device=device, **kwargs)
        except Exception as exc:
            logger.warning("Falha ao carregar '%s': %s", model_id, exc)

    logger.error("Nenhum modelo BERT pôde ser carregado.")
    return None
