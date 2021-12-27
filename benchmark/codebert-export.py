import onnxruntime as ort
import tensorflow as tf
import torch as T
import torch.onnx

from argparse import ArgumentParser, Namespace

from transformers import (RobertaConfig, RobertaForMaskedLM, RobertaTokenizer,
                          TFRobertaForMaskedLM)


def bench_onnx(input, mask, default_executor: bool):
    providers = ('DnnlExecutionProvider', 'CPUExecutionProvider')
    if default_executor:
        providers = providers[1:]

    global sess
    sess = ort.InferenceSession('codebert.pt.onnx', providers=providers)
    sess.run(['output'], {'input': input, 'mask': mask})

    def apply(input, mask):
        return sess.run(['output'], {'input': input, 'mask': mask})

    return apply


def bench_pt(config: RobertaConfig, input, mask, opset: int):
    global model
    model_path = 'microsoft/codebert-base-mlm'
    model = RobertaForMaskedLM.from_pretrained(model_path, config=config)

    dynamic_axes = {
        'input': {
            0: 'batch_size',
            1: 'sequence_length'
        },
        'mask': {
            0: 'batch_size',
            1: 'sequence_length'
        },
    }

    T.onnx.export(model=model,
                  args=(input, mask),
                  f='codebert.pt.onnx',
                  export_params=True,
                  verbose=False,
                  input_names=['input', 'mask'],
                  output_names=['output'],
                  do_constant_folding=True,
                  opset_version=opset,
                  dynamic_axes=dynamic_axes)

    return model


def bench_tf(config: RobertaConfig, input, mask, jitted: bool):
    global model
    model_path = 'microsoft/codebert-base-mlm'
    model = TFRobertaForMaskedLM.from_pretrained(model_path, config=config)

    @tf.function(input_signature=[
        tf.TensorSpec((None, None), tf.int32),
        tf.TensorSpec((None, None), tf.int32),
    ])
    def func(input, mask):
        return model.call(input, mask)

    if jitted:
        return func.get_concrete_function(input, mask)
    else:
        return model


def main(args: Namespace):
    with open('codebert-sample.py') as fin:
        code = fin.read()

    fmt = args.fw
    if args.fw == 'onnx':
        fmt = 'np'

    tokenizer = RobertaTokenizer.from_pretrained('microsoft/codebert-base-mlm')
    tokenized = tokenizer(text=[code],
                          max_length=512,
                          padding=True,
                          truncation=True,
                          return_tensors=fmt)

    global input, mask
    input = tokenized['input_ids']
    mask = tokenized['attention_mask']

    config_path = 'microsoft/codebert-base-mlm'
    config = RobertaConfig.from_pretrained(config_path)

    if args.fw == 'onnx':
        return bench_onnx(input, mask, not args.use_dnn)
    elif args.fw == 'pt':
        return bench_pt(config, input, mask, args.op_set)
    elif args.fw == 'tf':
        return bench_tf(config, input, mask, args.jitted)


parser = ArgumentParser()
parser.add_argument('fw', type=str, choices=('onnx', 'pt', 'tf'))
parser.add_argument('--op-set', type=int)
parser.add_argument('--jitted', default=False, action='store_true')
parser.add_argument('--use-dnn', default=False, action='store_true')

if __name__ == '__main__':
    apply = main(parser.parse_args())
