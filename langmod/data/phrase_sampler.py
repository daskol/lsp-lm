#!/usr/bin/env python

import numpy as np
import numpy.random

from typing import Optional

from numpy.typing import ArrayLike


def mark_spans(content: str, nowords: int):
    begins = np.empty(nowords, np.uint32)
    begins[0] = 0
    begin = 1
    index = 1
    while begin < len(content):
        try:
            begin = content.index(' ', begin) + 1
        except ValueError:
            break
        begins[index] = begin
        index += 1

    ends = np.empty_like(begins)
    ends[:-1] = begins[1:] - 1
    ends[-1] = len(content)

    return begins, ends


class PhraseSampler:

    def __init__(self, content: str,
                 rng: Optional[np.random.RandomState] = None):
        self.content = content
        self.rng = rng or np.random.RandomState()
        self.initialized = False

        self.nowords: int
        self.begins: ArrayLike
        self.ends: ArrayLike

    def initialize(self):
        self.nowords = self.content.count(' ') + 1
        self.begins, self.ends = mark_spans(self.content, self.nowords)
        self.word_width = (self.ends - self.begins).max()
        self.word_dtype = f'U{self.word_width}'

    def phrase(self, index: int, length: int) -> str:
        begin = self.begins[index]
        end = self.ends[index + length]
        return self.content[begin:end]

    def sample(self, length: int, size: int = 1):
        if not self.initialized:
            self.initialize()

        phrase_width = (self.word_width + 1) * length
        phrase_dtype = f'U{phrase_width}'

        words = self.sample_words(length, size)
        phrases = np.empty(size, phrase_dtype)
        for i in range(size):
            phrases[i] = self.phrase(words[i, 0], length)

        ids = np.array(words[:, 0])
        return ids, phrases

    def sample_words(self, length: int = 2, size: int = 1):
        """Function sample_words returns word indexes of contingues subsequence
        of orignal sequence [0, nowords).
        """
        begins = self.rng.randint(0, self.nowords - length, size)
        indexes = np.repeat(begins[:, None], length, axis=1)
        indexes += np.arange(length)
        return indexes

    def word(self, index: int) -> str:
        begin = self.begins[index]
        end = self.ends[index]
        return self.content[begin:end]


def sample_phrases(src: str, dst: str, length: int, size: int,
                   size_batch: int = 1024, seed: Optional[int] = None):
    rng = np.random.RandomState(seed)

    with open(src) as fin:
        content = fin.read().strip()
        content = content[:10000]

    sampler = PhraseSampler(content, rng)

    with open(dst, 'w') as fout:
        while size > 0:
            ids, phrases = sampler.sample(length, size_batch)
            size -= size_batch
            for id, phrase in zip(ids, phrases):
                fout.write(f'{id},{phrase}\n')


__all__ = (
    PhraseSampler,
    sample_phrases,
)
