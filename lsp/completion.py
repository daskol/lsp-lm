#   encoding: utf8
#   filename: completion.py

import re

import numpy as np
import tensorflow as tf

from typing import List, Optional

from tensorflow.keras.layers.experimental.preprocessing import TextVectorization  # noqa
from tensorflow.keras.models import load_model

from .corpus import Document


def locate(text: str, line: int, char: int) -> Optional[int]:
    """Function locate find position in text by line and character from the
    line beginning.
    """
    pos = 0

    # Find line first.
    cur_line = 0
    while pos < len(text) and cur_line != line:
        pos = text.index('\n', pos) + 1
        cur_line += 1

    # Find character in the line.
    for cur_char, c in enumerate(text[pos:pos + char]):
        pos += 1
        if c in '\r\n':
            return None
    if cur_char + 1 != char:
        return None

    return pos


class Completor:

    PATTERN_CLEAN = re.compile(r'[^A-Za-z \n\t]')

    def __init__(self, tv, model, context_size: int = 1, nosudgests: int = 5):
        self.tv = tv
        self.model = model
        self.context_size = context_size
        self.nosudgests = nosudgests

        self.vocab = tv.get_vocabulary()
        self.word_width = max(len(word) for word in self.vocab)
        self.word_dtype = f'U{self.word_width}'

    def complete(self, doc: Document, line: int, char: int) -> List[str]:
        # There is no such position in the text.
        if (pos := locate(doc.text, line, char)) is None:
            return []

        # Apply model to a phrase.
        phrase = self.get_phrase(doc.text, pos, self.context_size)
        tokens = self.tv.call([phrase])
        probas = self.model.call(tokens[:, :self.context_size])

        # Prepare sudgestion list.
        indexes = tf.argsort(probas)[:, -self.nosudgests:].numpy()
        sudgest = np.empty(self.nosudgests, self.word_dtype)
        for i, index in enumerate(indexes[0, ::-1]):
            sudgest[i] = self.vocab[index]

        return sudgest

    def get_phrase(self, text: str, end: int, length: int) -> str:
        # Estimate the beginning of a phrase with requiested number of words.
        pos = end
        nowords = 0
        while pos > 0:
            try:
                pos = text[:pos].rindex(' ')
            except ValueError:
                pos = 0
                nowords = nowords + 1
                break

            if (nowords := nowords + 1) == length:
                break
        begin = pos + 1 if pos else 0

        # Prepend phrase with [UNK] tokens if phrase is too short.
        beginning = '[UNK] ' * (length - nowords)
        ending = text[begin:end].lower()
        phrase = beginning + Completor.PATTERN_CLEAN.sub('', ending)

        # Again prepend phrase with [UNK] tokens after cleaning.
        words = [word for word in phrase.split() if word]
        nowords = len(words)
        prefix = '[UNK] ' * (length - nowords)
        return prefix + ' '.join(words)

    @staticmethod
    def load(vocab_path: str, model_path: str, **kwargs) -> 'Completor':
        vocab = np.load(vocab_path)
        tv = TextVectorization(vocabulary=vocab)
        model = load_model(model_path)
        return Completor(tv, model, **kwargs)


__all__ = (
    Completor,
)
