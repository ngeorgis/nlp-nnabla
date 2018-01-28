# Deep learning implementation for NLP with NNabla
Tiny implementation of deep learning models for NLP with Sony's NNabla.

## Test environment
- NNabla v0.9.7
- Keras v2.1.2 (for preprocessing)
- Numpy v1.13.3
- tqdm v4.19.5

## New features (different from the master respository of the NNabla)
- RNN layer
- LSTM layer
- Highway layer
- Time distributed parametric functions

## Models

### Language models
- A vanilla recurrent neural network language model ([`rnnlm.py`](https://github.com/satopirka/nlp-nnabla/blob/master/language-models/rnnlm.py))
- LSTM language model ([`lstmlm.py`](https://github.com/satopirka/nlp-nnabla/blob/master/language-models/lstmlm.py))
- Character-level neural language model ([`char-cnn-lstmlm.py`](https://github.com/satopirka/nlp-nnabla/blob/master/language-models/char-cnn-lstm.py))
  
  - this is almost same implementation of the paper ["Character-Aware Neural Language Models"](https://arxiv.org/abs/1508.06615).

#### Usage

To start training of the model:

```bash
cd language-models
ipython
run char-cnn-lstm.py
```

After training, you can get the similar words to the query word:

```python
In [3]: get_top_k('looooook', k=5)
Out[3]: ['look', 'hook', 'book', 'volokh', 'looks']

In [4]: get_top_k('while', k=5)
Out[4]: ['chile', 'whole', 'white', 'meanwhile', 'mile']

In [5]: get_top_k('richard', k=5)
Out[5]: ['richer', 'steinhardt', 'chart', 'michael', 'charts']
```

which is similar to the paper ["Character-Aware Neural Language Models"](https://arxiv.org/abs/1508.06615).

> <img src="https://github.com/satopirka/nlp-nnabla/blob/master/img/char-cnn-lstm.png" style="width: 500px">

### Seq2Seq models
- Encoder-decoder (`encdec.py`)
- Encoder-decoder + global attention (`attention.py`)

#### Usage

To start training of the model: 

```bash
cd seq2seq
./download.sh
ipython
run attention.py
```

You can use pre-trained attention model:

```bash
cd seq2seq
./download.sh
ipython
run attention.py
Ctrl+C (interrupt)

!wget https://github.com/satopirka/nlp-nnabla/releases/download/v0.0.1-alpha/attention_en2ja.h5
nn.load_parameters('attention_en2ja.h5')
```

And you can try to translate Japanese sentence into English by the model like below:

```python
nn.load_parameters('attention_en2ja.h5')

In [00]: translate("i was unable to look her in the face .")
Out[00]: '彼女の顔をまともに見ることが出来なかった。'

In [00]: translate("how far is it to the station ?")
Out[00]: '駅までどのくらいありますか。'
```

## Future work
- Skip-gram model
- Continuous-BoW model
- Encoder-decoder + local attention
- Peephole LSTM
- GRU
- etc.
