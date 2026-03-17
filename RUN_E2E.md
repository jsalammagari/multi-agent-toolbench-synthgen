# End-to-end run with real tools

Use the included `sample_tools/` (ToolBench-style JSON) to run the full pipeline: build → generate (Run A + Run B) → validate → metrics.

**Prerequisites:** From project root, with `.venv` activated and `pip install -e .` done:

```bash
# 1. Build registry and graph from sample tools
toolbench-synthgen build --toolbench-path sample_tools --artifacts-dir artifacts

# 2. Generate Run A (corpus memory disabled) – no OPENAI_API_KEY needed
toolbench-synthgen generate \
  --output-path data/run_a.jsonl \
  --num-conversations 20 \
  --seed 123 \
  --no-corpus-memory

# 3. Generate Run B (corpus memory enabled) – requires OPENAI_API_KEY
toolbench-synthgen generate \
  --output-path data/run_b.jsonl \
  --num-conversations 20 \
  --seed 123

# 4. Validate both datasets
toolbench-synthgen validate --input-path data/run_a.jsonl
toolbench-synthgen validate --input-path data/run_b.jsonl

# 5. Metrics (single or both)
toolbench-synthgen metrics --input-path-a data/run_a.jsonl --input-path-b data/run_b.jsonl
```

For **Run B** you must set `OPENAI_API_KEY` (mem0 uses it for embeddings). To test without it, run only steps 1, 2, 4, and 5 with just Run A:

```bash
toolbench-synthgen metrics --input-path-a data/run_a.jsonl
```

**Using real ToolBench tools:** The repo’s `data_example/toolenv/tools` only has category folders and `api.py` files—**no tool definition `.json` files**. You need the full dataset:

1. Download the dataset from [ToolBench Data Release](https://github.com/OpenBMB/ToolBench#data-release) (Google Drive or Tsinghua Cloud link in the README).
2. Unzip it so you have a `data/` directory (with `data/toolenv/tools/` inside).
3. Point build at the **tools** directory that actually contains `.json` files (one per tool, under category subdirs):

   ```bash
   toolbench-synthgen build --toolbench-path /path/to/ToolBench/data/toolenv/tools --artifacts-dir artifacts
   ```

Tool definition JSONs follow the format described in [ToolBench API Customization](https://github.com/OpenBMB/ToolBench#api-customization): `tool_description`, `tool_name`, `title`, `standardized_name`, `api_list` (with `name`, `description`, `required_parameters`, `optional_parameters`). Our loader accepts this and also `category` / `category_name` for tags.
