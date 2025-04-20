# Akari proof of concept

What is Akari? The answer, as it must, will eventually be revealed.

## Development

Setup the environment:

```sh
poetry install
```

### Tasks

> [!NOTE]
> You can use `xc`(<https://xcfile.dev/>) to run the commands
>
> See <https://xcfile.dev/getting-started/#installation> for installation instructions

#### format

```sh
poetry run black .
poetry run isort .
```

#### format:check

Check only

```sh
poetry run black --check .
poetry run isort --check-only .
```

#### lint

```sh
poetry run flake8 .
```

#### type

```sh
poetry run mypy .
```

#### test

```sh
poetry run python -m pytest
```

#### all

Requires: format, lint, type, test

### Run the Application

To execute the main script, run the following command:

```sh
poetry run python main.py
```
