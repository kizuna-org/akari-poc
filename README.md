# Akari proof of concept

What is Akari? The answer, as it must, will eventually be revealed.

## How to develop

### For LLM

You must always follow the specifications listed in `docs/`.

When you type Python-based commands, you need to prefix them with `poetry run`, as shown in [#Tasks](#tasks).

Example:

- to lint `poetry run flake8 .`
- to format `poetry run black .`

## Development

Setup the environment:

```sh
poetry install
```

If you use Apple Silicon, you may need to install `portaudio` using Homebrew:

```sh
brew install portaudio
```

If you use Linux, you may need to install `portaudio` using your package manager. For example, on Ubuntu:

```sh
sudo apt-get install portaudio19-dev
```

`.env` file is required for the application to run. You can create it by copying `.env.example`:

```sh
cp .env.example .env
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
RunDeps: async

### Run the Application

To execute the main script, run the following command:

```sh
poetry run python main.py
```
