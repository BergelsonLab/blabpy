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

## Build the package:

```shell
python -m build
```

## Upload to blabpy

```shell
twine upload --skip-existing dist/*
```

## Update the version tag

```shell
git tag $(python setup.py --version) && git push --tags
```
