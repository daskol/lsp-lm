#   encoding: utf8
#   filename: completion.py

import logging

import transformers

from transformers import AutoConfig, AutoModel, AutoTokenizer, pipeline

from abc import ABC, abstractmethod
from functools import partial
from typing import List

from .corpus import Document


__all__ = ('AbstractCompletor', 'make_completor_loader')


def make_completor_loader(lm_opts):
    """Function make_completor_loader implements factory patter for constuction
    a suitable completor builder (or loader) type.
    """
    if (model_type := lm_opts.get('model_type')) is None:
        logging.info('no model type is specified: assume `vocab` by default')
        model_type = 'vocab'

    # TODO: Use `match-case` syntax from Python 3.10.
    if model_type in ('hf', 'huggingface'):
        return HuggingFaceCompletorLoader(lm_opts['model_path'],
                                          lm_opts['num_results'])
    elif model_type == 'vocab':
        return VocabCompletorLoader(lm_opts['vocab_path'])
    else:
        raise ValueError(f'Unknown language model type: {model_type}')


class AbstractCompletor(ABC):
    """Class AbstractCompletor defines interface for any comletion model used
    in LSP implementation.
    """

    @abstractmethod
    def complete(self, doc: Document, line: int, char: int) -> List[str]:
        pass


class DummyCompletor(AbstractCompletor):
    """Class DummyCompletor implements a completor model used for testing and
    as a fallback interally.
    """

    def complete(self, doc: Document, line: int, char: int) -> List[str]:
        return []


class HuggingFaceCompletor(AbstractCompletor):

    def __init__(self, model_path: str, num_results: int):
        config = AutoConfig.from_pretrained(model_path)
        model_class_name = config.architectures[0]
        model_class = getattr(transformers, model_class_name, None)
        if model_class is None:
            logging.warning('failed to find model architecture %s: fallback',
                            model_class_name)
            model_class = AutoModel
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = model_class.from_pretrained(model_path)
        self.pipeline = pipeline('fill-mask',
                                 model=self.model,
                                 tokenizer=self.tokenizer)
        self.apply = partial(self.pipeline, top_k=num_results)

    def complete(self, doc: Document, line: int, char: int) -> List[str]:
        prefix, suffix = doc.window(line, char)
        text = ''.join([prefix, '<mask>', suffix])
        suggest = [el['token_str'] for el in self.apply(text)]
        return suggest


class HuggingFaceCompletorLoader:

    def __init__(self, model_path: str, num_results: int):
        self.completor: HuggingFaceCompletor
        self.model_path = model_path
        self.num_results = num_results

    def load(self) -> HuggingFaceCompletor:
        if not hasattr(self, 'completor'):
            self.completor = HuggingFaceCompletor(self.model_path,
                                                  self.num_results)
        return self.completor


class VocabCompletor(AbstractCompletor):
    """Class VocabCompletor implements completion logic based on predefined
    vocabulary.

    :param vocab: List of words.
    """

    def __init__(self, vocab: List[str]):
        self.vocab = vocab

    def complete(self, doc: Document, line: int, char: int) -> List[str]:
        return self.vocab


class VocabCompletorLoader:
    """Class VocabCompletorLoader is an loader object which loads from
    filesystem and initialises completor. This loader class is a caching one.

    :param vocab_path: Path to vocabulary file.
    """

    def __init__(self, vocab_path):
        self.completor: AbstractCompletor
        self.vocab_path = vocab_path

    def load(self) -> AbstractCompletor:
        if not hasattr(self, 'completor'):
            with open(self.vocab_path) as fin:
                vocab = fin.read().splitlines()
            self.completor = VocabCompletor(vocab)
        return self.completor
