# After version bump

## Update repo after implementing a change

- Edit version in `setup.py`.
- Commit.
- Merge branch into master (or do nothing if the change is a single commit done directly on master).
- Push.

## Update PyPI

```shell
python -m build
twine upload --skip-existing dist/*
```

## Update the version tag

```shell
git tag $(python setup.py --version) && git push --tags
```
