# 
# Copyright (c) 2017-2018 Minato Sato
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.
#

from collections import OrderedDict
import pickle
import numpy as np

import nnabla as nn
import nnabla.functions as F
import nnabla.parametric_functions as PF
import nnabla.solvers as S
from nnabla.utils.data_iterator import data_iterator_simple

from tqdm import tqdm

from parametric_functions import lstm
from parametric_functions import lstm_cell

from functions import time_distributed
from functions import time_distributed_softmax_cross_entropy

"""cuda setting"""
from nnabla.contrib.context import extension_context
ctx = extension_context('cuda.cudnn', device_id=0)
nn.set_default_context(ctx)
""""""
# nn.load_parameters('encdec_best.h5')

from utils import load_data
from utils import with_padding

train_source, dev_source, test_source, w2i_source, i2w_source = load_data('./data', 'en')
train_source = with_padding(train_source, padding_type='post')[:,::-1].astype(np.int32)
dev_source = with_padding(dev_source, padding_type='post')[:,::-1].astype(np.int32)
test_source = with_padding(test_source, padding_type='post')[:,::-1].astype(np.int32)

train_target, dev_target, test_target, w2i_target, i2w_target = load_data('./data', 'ja')
train_target = with_padding(train_target, padding_type='post').astype(np.int32)
dev_target = with_padding(dev_target, padding_type='post').astype(np.int32)
test_target = with_padding(test_target, padding_type='post').astype(np.int32)

vocab_size_source = len(w2i_source)
vocab_size_target = len(w2i_target)
sentence_length_source = train_source.shape[1]
sentence_length_target = train_target.shape[1]
embedding_size = 1024
hidden = 1024
batch_size = 256
max_epoch = 500

num_train_batch = len(train_source)//batch_size
num_dev_batch = len(dev_source)//batch_size

def load_train_func(index):
    return train_source[index], train_target[index]

def load_dev_func(index):
    return dev_source[index], dev_target[index]

train_data_iter = data_iterator_simple(load_train_func, len(train_source), batch_size, shuffle=True, with_file_cache=False)
dev_data_iter = data_iterator_simple(load_dev_func, len(dev_source), batch_size, shuffle=True, with_file_cache=False)

# def where(enable, c, c_prev):
#     batch_size, units = c.shape
#     ret = []
#     for e, _c, _c_prev in zip(F.split(enable, axis=0), F.split(c, axis=0), F.split(c_prev, axis=0)):
#         if e.d == 1:
#             ret.append(F.reshape(_c, (1, units)))
#         else:
#             ret.append(F.reshape(_c_prev, (1, units)))
#     return F.concatenate(*ret, axis=0)

# def Maxout(x, units, pool_size=128, name='maxout'):
#     batch_size = x.shape[0]
#     h = PF.affine(x, units*pool_size, name='maxout')
#     h = F.reshape(h, (batch_size, units, pool_size))
#     h = F.max(h, axis=2)
#     return h

def GlobalAttention(hs, attention_units):
    # hs -> (batch_size, sentence_legnth_source, embedding_size)
    hs = time_distributed(PF.affine)(hs, attention_units, with_bias=False, name='Wahs')
    # -> (batch_size, sentence_legnth_source, attention_units)

    def compute_context(prev_state):
        batch_size = prev_state.shape[0]
        ht = PF.affine(prev_state, attention_units, with_bias=False, name='Waht')
        # -> (batch_size, attention_units)
        ht = F.reshape(ht, (batch_size, 1, attention_units))
        # -> (batch_size, 1, attention_units)
        ht = F.broadcast(ht, (batch_size, sentence_length_source, attention_units))
        # -> (batch_size, sentence_length_source, attention_units)

        attention = F.tanh(hs + ht)
        # -> (batch_size, sentence_length_source, attention_units)
        attention = time_distributed(PF.affine)(attention, 1, with_bias=False, name='attention')
        # -> (batch_size, sentence_length_source, 1)
        attention = F.softmax(attention, axis=1)
        # -> (batch_size, sentence_length_source, 1)

        context = F.batch_matmul(hs, attention, transpose_a=True)
        context = F.reshape(context, (batch_size, attention_units))

        return context

    return compute_context

LSTMEncoder = lstm

def LSTMAttentionDecoder(inputs=None, encoder_output=None, initial_state=None, return_sequences=False, return_state=False, inference_params=None, name='lstm'):

    if inputs is None:
        assert inference_params is not None, 'if inputs is None, inference_params must not be None.'
    else:
        sentence_length = inputs.shape[1]

    assert type(initial_state) is tuple or type(initial_state) is list, \
           'initial_state must be a typle or a list.'
    assert len(initial_state) == 2, \
           'initial_state must have only two states.'

    c0, h0 = initial_state

    assert c0.shape == h0.shape, 'shapes of initial_state must be same.'
    batch_size, units = c0.shape

    cell = c0
    hidden = h0

    hs = []

    if inference_params is None:
        xs = F.split(F.slice(inputs, stop=(batch_size, sentence_length-1, units)), axis=1)
        pad = nn.Variable.from_numpy_array(np.array([w2i_source['pad']]*batch_size))
        xs = [PF.embed(pad, vocab_size_source, embedding_size, name='enc_embeddings')] + list(xs)

        compute_context = GlobalAttention(encoder_output, 1024)

        for x in xs:
            with nn.parameter_scope(name):
                cell, hidden = lstm_cell(x, cell, hidden)
                context = compute_context(hidden)
                h_t = F.tanh(PF.affine(F.concatenate(context, hidden, axis=1), 1024, with_bias=False, name='Wc'))
            hs.append(h_t)
    else:
        assert batch_size == 1, 'batch size of inference mode must be 1.'
        embed_weight, output_weight, output_bias = inference_params
        pad = nn.Variable.from_numpy_array(np.array([w2i_source['pad']]*batch_size))
        x = PF.embed(pad, vocab_size_source, embedding_size, name='enc_embeddings')

        compute_context = GlobalAttention(encoder_output, 1024)

        word_index = 0
        ret = []
        i = 0
        while i2w_target[word_index] != '。' and i < 20:
            with nn.parameter_scope(name):
                cell, hidden = lstm_cell(x, cell, hidden)
                context = compute_context(hidden)
                h_t = F.tanh(PF.affine(F.concatenate(context, hidden, axis=1), 1024, with_bias=False, name='Wc'))
            output = F.affine(h_t, output_weight, bias=output_bias)
            word_index = np.argmax(output.d[0])
            ret.append(word_index)
            x = nn.Variable.from_numpy_array(np.array([word_index], dtype=np.int32))
            x = F.embed(x, embed_weight)

            i+=1
        return ret


    if return_sequences:
        ret = F.stack(*hs, axis=1)
    else:
        ret = hs[-1]

    if return_state:
        return ret, cell, hidden
    else:
        return ret



def predict(x):
    with nn.auto_forward():
        x = x.reshape((1, sentence_length_source))
        enc_input = nn.Variable.from_numpy_array(x)
        enc_input = time_distributed(PF.embed)(enc_input, vocab_size_source, embedding_size, name='enc_embeddings')

        # encoder
        with nn.parameter_scope('encoder'):
            output, c, h = LSTMEncoder(enc_input, hidden, return_sequences=True, return_state=True)

        # decoder
        params = [nn.get_parameters()['dec_embeddings/embed/W'],
                  nn.get_parameters()['output/affine/W'],
                  nn.get_parameters()['output/affine/b']]
        ret = LSTMAttentionDecoder(encoder_output=output, initial_state=(c, h), inference_params=params, name='decoder')

        return ret

def translate_test(index):
    print('source:')
    print(' '.join([i2w_source[i] for i in test_source[index]][::-1]).strip(' pad'))
    print('target:')
    print(''.join([i2w_target[i] for i in test_target[index]]).strip('pad'))
    print('encoder-decoder output:')
    print(''.join([i2w_target[i] for i in predict(test_source[index])]).strip('pad'))

def translate(sentence):
    sentence = list(map(lambda x: w2i_source[x], sentence.split()))
    sentence += [0]*(sentence_length_source - len(sentence))
    sentence.reverse()
    return ''.join([i2w_target[i] for i in predict(np.array([sentence]))])

def build_model():
    x = nn.Variable((batch_size, sentence_length_source))
    input_mask = F.sign(F.reshape(F.slice(x), (batch_size, sentence_length_source, 1)))
    y = nn.Variable((batch_size, sentence_length_target))
    
    enc_input = time_distributed(PF.embed)(x, vocab_size_source, embedding_size, name='enc_embeddings')#*input_mask
    # -> (batch_size, sentence_length_source, embedding_size)
    dec_input = time_distributed(PF.embed)(y, vocab_size_target, embedding_size, name='dec_embeddings')
    # -> (batch_size, sentence_length_target, embedding_size)

    # encoder
    with nn.parameter_scope('encoder'):
        output, c, h = LSTMEncoder(enc_input, hidden, return_sequences=True, return_state=True)
        # -> (batch_size, sentence_length_source, hidden), (batch_size, hidden), (batch_size, hidden)

    # decoder
    output = LSTMAttentionDecoder(dec_input, output, initial_state=(c, h), return_sequences=True, name='decoder')
    # -> (batch_size, sentence_length_target, hidden)
    output = time_distributed(PF.affine)(output, vocab_size_target, name='output')
    # -> (batch_size, sentence_length_target, vocab_size_target)

    t = F.reshape(F.slice(y), (batch_size, sentence_length_target, 1))

    entropy = time_distributed_softmax_cross_entropy(output, t)

    mask = F.sum(F.sign(t), axis=2) # do not predict 'pad'.
    count = F.sum(mask, axis=1)

    entropy *= mask
    loss = F.mean(F.sum(entropy, axis=1)/count)
    return x, y, loss

x, y, loss = build_model()

# Create solver.
solver = S.Momentum(1e-2, momentum=0.9)
solver.set_parameters(nn.get_parameters())

# Create monitor.
from nnabla.monitor import Monitor, MonitorSeries, MonitorTimeElapsed
monitor = Monitor('./tmp-encdec')
monitor_perplexity = MonitorSeries('perplexity', monitor, interval=1)
monitor_perplexity_dev = MonitorSeries('perplexity_dev', monitor, interval=1)

best_dev_loss = 9999

for epoch in range(max_epoch):
    train_loss_set = []
    for i in tqdm(range(num_train_batch)):
        x.d, y.d = train_data_iter.next()
        loss.forward()
        solver.zero_grad()
        loss.backward(clear_buffer=True)
        solver.update()
        train_loss_set.append(loss.d.copy())

    dev_loss_set = []
    for i in range(num_dev_batch):
        x.d, y.d = train_data_iter.next()
        loss.forward()
        dev_loss_set.append(loss.d.copy())

    monitor_perplexity.add(epoch+1, np.e**np.mean(train_loss_set))
    monitor_perplexity_dev.add(epoch+1, np.e**np.mean(dev_loss_set))

    # dev_loss = np.e**np.mean(dev_loss_set)
    # if best_dev_loss > dev_loss:
    #     best_dev_loss = dev_loss
    #     print('best dev loss updated! {}'.format(dev_loss))
    #     nn.save_parameters('encdec_best.h5')



