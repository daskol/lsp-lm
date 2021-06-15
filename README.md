# LSP: Language Model

*Language Model as a Language Server*

## Tasks Queue

1. Find suitable corpus in Russian (English).
    a. Download Wikipedia dumps.
    b. Read Wikipedia dumps according to XML schema.
    c. Write parsed Wikipedia dumps to Parquet files.
2. Develop preprocessing pipeline.
3. Use TensorFlow to describe and fit a model.
4. Freeze models weights and export.
5. Write service which implements LSP.
6. Load model graph and weights in LSP service.

## Assembly

There are multiple required dependencies.

1. Multi-threading support (e.g. POSIX Threads).
2. XML parsing library [Expat][2].
3. Data compression library [bzip2][3].
4. [Apache Arrow][1] library with support of compression codecs and Parquet.

We use CMake as a main building system. So, assembly is relatively simple.
```shell
cmake -B build/release
cmake --build build/release
```

[1]: https://github.com/apache/arrow
[2]: https://github.com/libexpat/libexpat
[3]: https://gitlab.com/federicomenaquintero/bzip2
