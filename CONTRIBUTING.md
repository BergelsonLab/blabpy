# Set up developmental environment

- Recommended IDE: PyCharm. Reason: Zhenya likes it.
- Recommended Python environment: conda. Reason: Zhenya likes it.
- Install the package in editable mode with `pip install -e .` in the repo root.

# After finishing changes

## Update repo after implementing a change

- Edit version in `setup.py`.
- Add new block in `CHANGELOG.md`.
- Commit.
- Merge branch into `main` (or do nothing if the change is a single commit done directly on `main`).
- Push.
- Tag and push:
    
    ```shell
    git tag $(python setup.py --version) && git push --tags
    ```

## Build the package and upload to blabpy:

```shell
python -m build
```

```shell
twine upload --skip-existing dist/*
```
