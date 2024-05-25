# Set up developmental environment

- Recommended IDE: PyCharm. Reason: Zhenya likes it.
- Recommended Python environment: conda. Reason: Zhenya likes it.
- Install the package in editable mode with `pip install -e .` in the repo root.

# After finishing changes

## Update repo after implementing a change

- Merge branch into `main` (or do nothing if the change is a single commit done directly on `main`).
- Edit version in `setup.py`.
- Add new block in `CHANGELOG.md`.
- Commit.
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

notes:
- You might need to `pip install` `twine` and `build` first.
- Use `__token__` as the login and an API token as the password. pypi.org login passwords and 2FA verification codes are in 1Password - in the blab-staff vault.
