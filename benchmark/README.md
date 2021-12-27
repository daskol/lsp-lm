# LSP-LM: Benchmark

## CPU Graph Executors

In this benchmark we investigate performance in sence wall clock of the most
used executors (ONNX, PyTorch, and TensorFlow). The goal is to measure
inference time for a RoBERTa-like model on a single input sequence of medium
length (~100-200 tokens).

We imply that desired inference time is about 33 ms (approximately 30 Hz).
Also, inference should use as few CPU as possible. By now. model inference
takes more than 100ms on Intel Core i7 10th series what is quite
unsatisfactory.

![Execution time for different execution backends on CPU.][1]

### ONNX Executor

This code must be run after benchmarking PyTorch executor since the later
executor export model to ONNX format.

```python
%run codebert-bench.py --use-dnn onnx
%timeit apply(input, mask)
```

See ONNX documentation to enable optimization and quantization.

### PyTorch and ONNX Executors

This benchmark should be executed first. We can tune ONNX operator set for
exported ONNX model. This is only way to convert model to ONNX format
(conversion from TF to ONNX is broken for some reason now).

```python
%run codebert-bench.py --op-set 12 pt
%timeit apply(input, mask)
```

### TensorFlow Executor

In this benchmark the only option to choose is JITting model on inference. The
issue here that we have enough memory (at least 10 GiB) to export model to ONNX
format.

```python
%run codebert-bench.py --jitted tf
%timeit apply(input, mask)
```

[1]: ./codebert-report.png
