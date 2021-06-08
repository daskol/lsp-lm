# LSP: Language Model

*Language Model as a Language Server*

# Tasks Queue

1. Find suitable corpus in Russian (English).
    a. Download Wikipedia dumps.
    b. Read Wikipedia dumps according to XML schema.
    c. Write parsed Wikipedia dumps to Parquet files.
2. Develop preprocessing pipeline.
3. Use TensorFlow to describe and fit a model.
4. Freeze models weights and export.
5. Write service which implements LSP.
6. Load model graph and weights in LSP service.
