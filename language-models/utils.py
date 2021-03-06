# 
# Copyright (c) 2017-2018 Minato Sato
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.
#

import numpy as np
import os

w2i = {}
i2w = {}

c2i = {}
i2c = {}

w2i['pad'] = 0
i2w[0] = 'pad'

c2i[' '] = 0
i2c[0] = ' '

word_length = 20


def load_data(filename):
    global w2i, i2w
    global c2i, i2c
    with open(filename) as f:
        lines = f.read().replace('\n', '<eos>')
        for char in set(lines):
            if char not in c2i:
                c2i[char] = len(c2i)
            if c2i[char] not in i2c:
                i2c[c2i[char]] = char

        words = lines.strip().split()
    dataset = np.ndarray((len(words), ), dtype=np.int32)

    for i, word in enumerate(words):
        if word not in w2i:
            w2i[word] = len(w2i)
        if w2i[word] not in i2w:
            i2w[w2i[word]] = word
        dataset[i] = w2i[word]

    sentences = []
    sentence = []
    for index in dataset:
        if i2w[index] != '<eos>':
            sentence.append(index)
        else:
            sentence.append(index)
            sentences.append(sentence)
            sentence = []
    return sentences

def wordseq2charseq(data):
    global word_length
    data = np.repeat(np.expand_dims(data, axis=2), word_length, axis=2)
    data[:, :, 1:] = 0
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            word = data[i][j][0]
            for k, char in enumerate(i2w[word]):
                data[i][j][k] = c2i[char]
    return data

def with_padding(sequences, padding_type='post', max_sequence_length=None):
    if max_sequence_length is None:
        max_sequence_length = max(map(lambda x: len(x), sequences))
    else:
        assert type(max_sequence_length) == int, 'max_sequence_length must be an integer.'
        assert max_sequence_length > 0, 'max_sequence_length must be a positive integer.'

    def _with_padding(sequence):
        sequence = sequence[:max_sequence_length]
        sequence_length = len(sequence)
        pad_length = max_sequence_length - sequence_length
        if padding_type == 'post':
            return sequence + [0] * pad_length
        elif padding_type == 'pre':
            return [0] * pad_length + sequence
        else:
            raise Exception('padding type error. padding type must be "post" or "pre"')

    return np.array(list(map(_with_padding, sequences)), dtype=np.int32)

ptb_url = 'https://raw.githubusercontent.com/wojzaremba/lstm/master/data/ptb.{0}.txt'
types = ['train', 'valid', 'test']
ptb_urls = map(lambda x: ptb_url.format(x), types)
os.makedirs('./ptb/', exist_ok=True)
for _url, _type in zip(ptb_urls, types):
    if not os.path.exists('./ptb/' + _type + '.txt'):
        os.system('wget -O ' + './ptb/' + _type + '.txt ' + _url)

