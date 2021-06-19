# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.11.3
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# # Language Model: MLP + BoW \[EN\]

import numpy as np
import tensorflow as tf

from operator import itemgetter
from os.path import join
from typing import Optional

from tensorflow.keras.models import Model, Sequential
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.layers import Dense, Embedding, Flatten, InputLayer
from tensorflow.keras.layers.experimental.preprocessing import TextVectorization

# +
DATA_DIR = '../data'

CONTEXT_SIZE = 11

MODEL_PATH = join(DATA_DIR, 'model/mlp-bow-en')

VOCAB_PATH = join(DATA_DIR, 'vocab.npy')

DATASET = [
    join(DATA_DIR, f'phr{CONTEXT_SIZE}'),
]


# -

# ## Input Pipeline

# +
def fst(*args):
    return args[0]

def snd(*args):
    return args[1]


# -

def parse_line(line: tf.Tensor):
    splits = tf.strings.split(line, ',', 1)
    id = tf.strings.to_number(splits[0], tf.int32)
    phrase = splits[1]
    return id, phrase


ds = tf.data.TextLineDataset(DATASET) \
    .map(parse_line) \
    .map(snd)

# ## Model

# ### Vocabulary Building

# Initially, we want to build vocabulary from scratch. So, we can do this as the following.

# %%time
tv = TextVectorization(1000, output_sequence_length=CONTEXT_SIZE + 1)
tv.adapt(ds.batch(128))

# As well as we obtain a vocabulary we should save it to file system in order to reuse it later.

vocab = tv.get_vocabulary()
np.save(VOCAB_PATH, vocab)

# Finally, we can instantiate text vectorizer with dictionary without adaptation to corpus.

vocab = np.load(VOCAB_PATH)

tv = TextVectorization(vocabulary=vocab,
                       output_sequence_length=CONTEXT_SIZE + 1)


# ### Modeling

# As a baseline model we define a simple MLP (a single layer neural network) which operates on context of fixed length.

class LanguageModel(Model):

    def __init__(self, context_size: int, embedding_size: int, vocab_size: int):
        super().__init__()

        self.model = tf.keras.Sequential()
        self.model.add(InputLayer(context_size))
        self.model.add(Embedding(input_dim=vocab_size,
                                 output_dim=embedding_size,
                                 input_length=context_size))
        self.model.add(Flatten())
        self.model.add(Dense(vocab_size))

    def call(self, context):
        return self.model(context)

    def predict(self, context):
        logits = self.model(context)
        labels = tf.argmax(logits, 1)
        return labels

    def predict_proba(self, context):
        logits = self.model(context)
        probas = tf.nn.softmax(logits)
        return probas


# ## Training Pipeline

def fit(model: LanguageModel, tv: TextVectorization, ds: tf.data.Dataset, noiters: Optional[int] = None):
    def objective(contexts, targets):
        targets_prob = model.call(contexts)
        ce = tf.nn.sparse_softmax_cross_entropy_with_logits(targets, targets_prob)
        loss = tf.reduce_mean(ce)
        return loss

    for i, phrases in enumerate(ds.batch(32)):
        tokens = tv.call(phrases)
        contexts = tokens[:, :-1]
        targets = tokens[:, -1]

        with tf.GradientTape() as tape:
            loss = objective(contexts, targets)

        opt_vars = model.weights
        opt_grads = tape.gradient(loss, opt_vars)
        opt.apply_gradients(zip(opt_grads, opt_vars))\

        if i % 128 == 0:
            print(f'[{i:05d}] loss={loss.numpy():.3e}')

        if noiters and noiters == i:
            break

    print(f'[{i:05d}] loss={loss.numpy():.3e}')
    return i, loss


opt = tf.keras.optimizers.Adam()

model = LanguageModel(context_size=CONTEXT_SIZE,
                      embedding_size=64,
                      vocab_size=tv.vocabulary_size())

loss = fit(model, tv, ds, 1024)

# As soon as we fit the model we want to save it.

model.model.save(MODEL_PATH)


# ## Evaluation

def evaluate(model, tv, phrases, nosudgests=5):
    tokens = tv.call(phrases)
    contexts = tokens[:, :-1]
    targets = tokens[:, -1]
    vocab = tv.get_vocabulary()

    probas = model.predict_proba(contexts)
    top = tf.argsort(probas)[:, -nosudgests:][:, ::-1].numpy()

    for i, phrase in enumerate(phrases):
        context, target = phrase.numpy().decode('utf-8').rsplit(' ', 1)
        print(f'[{i:02d}] context="{context}"')

        for j, idx in enumerate(top[i, :]):
            sudgest = vocab[idx]
            mark = 'x' if target == sudgest else ' '
            proba = probas[i, idx]
            print(f'     [{mark}] #{j + 1:02d} proba={proba:.3e} "{sudgest}"')

        print(f'                             "{target}"')


for phrases in ds.batch(4).take(1):
    evaluate(model, tv, phrases)
