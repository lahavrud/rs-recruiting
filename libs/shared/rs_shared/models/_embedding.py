"""Embedding vector width for the resume-matching engine.

Fixed at the DB-column level by the migration — keep in lockstep with
``settings.embedding_dim`` and the embedding model's output dimension (see
core/services/embeddings.py). Defined once here and shared by the ``Job`` and
``CandidateProfile`` ``Vector`` columns so the width can't drift between them.
"""

from rs_shared.core.infrastructure.config import settings

EMBEDDING_DIM = settings.embedding_dim
