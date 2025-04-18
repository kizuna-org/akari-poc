# Akari proof of concept

What is Akari? The answer, as it must, will eventually be revealed.

## Development

Setup the environment:

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

### Tasks

> [!NOTE]
> You can use `xc`(<https://xcfile.dev/>) to run the commands
>
> See <https://xcfile.dev/getting-started/#installation> for installation instructions


#### format

```sh
black .
isort .
```

#### format:check

Check only

```sh
black --check .
isort --check-only .
```

#### lint

```sh
flake8 .
```

#### type

```sh
mypy .
```

#### test

```sh
python -m pytest
```

#### all

Requires: format, lint, type, test
