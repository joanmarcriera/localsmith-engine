# Project - wordcount-cli-realtest

Build a tiny Python 3 standard-library command-line app for counting words in text.

## Goal

Create a minimal app that can be generated and verified quickly as a real workflow
test. It should be useful enough to prove the workflow can create source, docs, and
tests without relying on fixture outputs.

## Constraints

- Use Python 3 standard library only.
- No external dependencies.
- No `uv`, no `pyproject.toml`, no Dockerfile, and no package manager metadata for this
  test project. This project is intentionally smaller than the normal defaults.
- Keep implementation readable and small.
- Include a README, source file, and at least one test file.

## Required behavior

- Provide a CLI runnable as:

  ```bash
  python3 src/wordcount.py input.txt
  ```

- Output JSON with:
  - `lines`
  - `words`
  - `characters`
  - `top_words`

- `top_words` should be a list of `[word, count]` pairs, sorted by descending count
  then alphabetically for ties.
- Normalize words to lowercase.
- Treat alphabetic and numeric runs as words. Ignore punctuation.
- Support `--top N`, defaulting to `5`.
- Exit non-zero with a clear stderr message when the input file does not exist.

## Acceptance checks

- `python3 -m py_compile src/wordcount.py` passes.
- `python3 tests/test_wordcount.py` passes.
- The README documents usage and one example command.
