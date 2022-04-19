# After version bump

## Update PyPI

```shell
python -m build
twine upload --skip-existing dist/*
```

## Update the version tag

```shell
git tag $(python setup.py --version) && git push --tags
```
