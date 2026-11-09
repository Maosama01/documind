"""
The embedding model loads on first use, not at import.

These tests never download the real model: a fake SentenceTransformer is put
in sys.modules in its place.
"""
import os
import subprocess
import sys
import threading
import time
import types
from pathlib import Path

import numpy as np

import app.services.embedding_service as embedding_service

BACKEND_DIR = Path(__file__).resolve().parent.parent


class FakeTokenizer:
    """
    One token per space-separated word, plus one more per hyphen (so "e-mail"
    costs 2), plus [CLS] and [SEP] unless add_special_tokens=False, like a
    real BERT tokenizer.
    """

    def __call__(self, texts, add_special_tokens=True, verbose=True):
        special = 2 if add_special_tokens else 0
        return {"input_ids": [[0] * (len(text.split()) + text.count("-") + special) for text in texts]}


class FakeSentenceTransformer:
    instances = 0
    load_seconds = 0.0
    max_seq_length = 256

    def __init__(self, name):
        time.sleep(self.load_seconds)
        type(self).instances += 1
        self.name = name
        self.tokenizer = FakeTokenizer()

    def encode(self, texts, **kwargs):
        if isinstance(texts, list):
            return [np.zeros(384) for _ in texts]
        return np.zeros(384)


def use_fake_model(monkeypatch, load_seconds=0.0):
    fake_module = types.ModuleType("sentence_transformers")
    fake_module.SentenceTransformer = FakeSentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)
    monkeypatch.setattr(embedding_service, "_model", None)
    monkeypatch.setattr(FakeSentenceTransformer, "instances", 0)
    monkeypatch.setattr(FakeSentenceTransformer, "load_seconds", load_seconds)


def test_importing_the_app_does_not_load_the_model(tmp_path):
    env = dict(os.environ, PYTHONPATH=str(BACKEND_DIR))
    check = (
        "import sys, app.main, app.services.embedding_service as e; "
        "assert e._model is None; "
        "assert 'sentence_transformers' not in sys.modules; "
        "assert 'torch' not in sys.modules"
    )
    result = subprocess.run(
        [sys.executable, "-c", check], cwd=tmp_path, env=env, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_model_loads_once_and_is_reused(monkeypatch):
    use_fake_model(monkeypatch)

    single = embedding_service.create_embedding("hello")
    batch = embedding_service.create_embeddings_batch(["a", "b"])

    assert FakeSentenceTransformer.instances == 1
    assert embedding_service.get_model().name == embedding_service.MODEL_NAME
    assert len(single) == 384
    assert [len(vector) for vector in batch] == [384, 384]


def test_count_over_token_limit_counts_texts_longer_than_max_seq_length(monkeypatch):
    use_fake_model(monkeypatch)
    fits = " ".join(["word"] * 254)      # 254 + [CLS] + [SEP] = 256 tokens: fits exactly
    too_long = " ".join(["word"] * 255)  # 257 tokens: one past the limit

    assert embedding_service.count_over_token_limit([fits, too_long, fits, too_long]) == 2
    assert embedding_service.count_over_token_limit([fits]) == 0


def test_count_word_tokens_counts_each_word_without_the_special_tokens(monkeypatch):
    use_fake_model(monkeypatch)

    assert embedding_service.count_word_tokens(["send", "an", "e-mail"]) == [1, 1, 2]


def test_count_word_tokens_of_no_words_does_not_load_the_model(monkeypatch):
    use_fake_model(monkeypatch)

    assert embedding_service.count_word_tokens([]) == []
    assert FakeSentenceTransformer.instances == 0


def test_count_over_token_limit_does_not_load_the_model_for_no_texts(monkeypatch):
    use_fake_model(monkeypatch)

    assert embedding_service.count_over_token_limit([]) == 0
    assert FakeSentenceTransformer.instances == 0


def test_concurrent_first_calls_load_the_model_once(monkeypatch):
    use_fake_model(monkeypatch, load_seconds=0.05)

    threads = [threading.Thread(target=embedding_service.get_model) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert FakeSentenceTransformer.instances == 1
