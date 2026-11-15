# Recettes

Recettes turns Markdown files into a small, static recipe website. Recipes remain easy to edit in GitHub; the generated site is mobile-friendly and needs no application server.

## Recipe format

Put one Markdown file per recipe in a directory. Optional photos sit beside the Markdown file and use its filename with a numbered suffix:

```text
examples/
├── soupe-oignon.md
├── soupe-oignon-1.jpg
└── soupe-oignon-2.webp
```

Recipe properties go in YAML front matter. Tags can be a comma-separated string or a YAML list. All properties are optional:

```md
---
title: Soupe à l'oignon
portions: 4
preparation: 45
cuisson: 15
tags: hiver, soupe, facile, pas-cher
lang: fr
---

# Préparation

Pelez et émincez les {{ 4 oignons }}.

Faites-les revenir dans {{ 50g de beurre }} et {{ 1cas d'huile }}.
Ajoutez {{ 1L d'eau chaude }} et {{ 25cl de vin blanc }}.

Laissez cuire doucement.
```

Write ingredient amounts inside `{{ }}` in the recipe text. Recettes reads a number and an optional unit from the start of the expression, including decimals and fractions such as `0.5cac` and `1/2 cac`. A number without a unit is treated as a count; text without a leading number stays unchanged. The optional `portions` property enables serving controls. Front matter properties are shown as written, except `title`, `tags`, and `portions`, which are shown separately. Optional `lang` sets the HTML page language for browsers and assistive technology; it does not limit the recipe's language.

## Build and preview

Install with [uv](https://docs.astral.sh/uv/):

```sh
uv tool install .
```

Build the recipes in a directory and preview the generated site:

```sh
recettes build examples --destination site
python -m http.server --directory site 8000
```

Open <http://127.0.0.1:8000>. Cards include the first prose paragraph as a short excerpt, in the recipe's language. The index has search and tag filters. Recipe pages show title tags, front matter properties, Markdown, matching photos, and a consolidated ingredient list. Portion controls appear when `portions` is set.

The recipe source directory is never modified. Generated files go in `site/` by default or the directory passed to `--destination`.

## Contribute

Add or edit a Markdown file and its optional numbered photos, then open a pull request. The CI workflow runs Ruff, pytest, and Prettier checks. On pushes to `main`, the CD workflow builds `examples/` and publishes the generated site to the `gh-pages` branch. Configure GitHub Pages to deploy from that branch at its root.

## Development

```sh
uv sync --extra dev
uv run recettes --help
uv run ruff check .
uv run pytest
npm ci
npm run format:check
```

## License

CC0 1.0 Universal
