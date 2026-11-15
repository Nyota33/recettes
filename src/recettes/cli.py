from __future__ import annotations

import html
import json
import re
import shutil
from fractions import Fraction
from pathlib import Path
from typing import Annotated

import frontmatter
import typer
from markdown_it import MarkdownIt

app = typer.Typer(no_args_is_help=True, help="Build a static recipe website from Markdown.")
INGREDIENT_RE = re.compile(r"\{\{\s*(.*?)\s*\}\}")
QUANTITY_RE = re.compile(
    r"^(?P<amount>\d+(?:[.,]\d+)?(?:\s*/\s*\d+(?:[.,]\d+)?)?)"
    r"\s*(?P<unit>c\.?\s*à\.?\s*[sc]\.?|cas|cac|kg|mg|g|ml|cl|l)?\s*(?P<name>.*)$",
    re.IGNORECASE,
)
IMAGE_RE = re.compile(r"^(?P<stem>.+)-(?P<number>\d+)\.(?P<ext>jpe?g|png|webp|avif)$", re.I)
MARKDOWN = MarkdownIt("default", {"html": False, "typographer": True})


@app.callback()
def main() -> None:
    """Build and maintain a static recipe website."""


def fail(message: str) -> None:
    raise typer.BadParameter(message)


def parse_quantity(value: str) -> tuple[float | None, str, str]:
    match = QUANTITY_RE.fullmatch(value.strip())
    if not match:
        return None, "", value.strip()
    amount_text = match.group("amount").replace(" ", "").replace(",", ".")
    try:
        amount = float(Fraction(amount_text))
    except (ValueError, ZeroDivisionError):
        return None, "", value.strip()
    raw_unit = (match.group("unit") or "").lower().replace(" ", "").replace(".", "")
    unit = {"càs": "cas", "càc": "cac"}.get(raw_unit, raw_unit)
    return amount, unit, match.group("name").strip()


def parse_tags(value: object) -> list[str]:
    if isinstance(value, str):
        tags = value.split(",")
    elif isinstance(value, list):
        tags = [str(tag) for tag in value]
    else:
        return []
    return [tag.strip() for tag in tags if tag.strip()]


def aggregate_ingredients(ingredients: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], dict[str, object]] = {}
    for ingredient in ingredients:
        amount = ingredient["amount"]
        unit = str(ingredient["unit"])
        name = str(ingredient["name"])
        normalized_name = " ".join(name.casefold().split())
        if amount is None:
            key = ("plain", normalized_name)
        elif normalized_name:
            key = (unit, normalized_name)
        else:
            key = (unit, "")
        if key not in grouped:
            grouped[key] = dict(ingredient)
        elif amount is not None:
            grouped[key]["amount"] = float(grouped[key]["amount"]) + float(amount)
    return list(grouped.values())


def markdown_with_ingredients(markdown: str) -> tuple[str, list[dict[str, object]]]:
    ingredients: list[dict[str, object]] = []

    def replace(match: re.Match[str]) -> str:
        raw = match.group(1).strip()
        amount, unit, name = parse_quantity(raw)
        ingredients.append({"amount": amount, "unit": unit, "name": name, "raw": raw})
        return f"RECIPEINGREDIENTTOKEN{len(ingredients) - 1}END"

    rendered = MARKDOWN.render(INGREDIENT_RE.sub(replace, markdown))
    return rendered, ingredients


def first_paragraph(markdown: str, limit: int = 180) -> str:
    tokens = MARKDOWN.parse(markdown)
    for index, token in enumerate(tokens):
        if token.type != "paragraph_open":
            continue
        inline = tokens[index + 1]
        if inline.type != "inline":
            continue
        parts = []
        for child in inline.children or []:
            if child.type in {"text", "code_inline", "image"}:
                parts.append(child.content)
            elif child.type in {"softbreak", "hardbreak"}:
                parts.append(" ")
        text = "".join(parts)
        text = INGREDIENT_RE.sub(lambda match: match.group(1), text)
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            return text[:limit].rstrip()
    return ""


def recipe_images(markdown_path: Path) -> list[Path]:
    images = []
    for path in markdown_path.parent.iterdir():
        match = IMAGE_RE.fullmatch(path.name)
        if path.is_file() and match and match.group("stem") == markdown_path.stem:
            images.append(path)
    return sorted(images, key=lambda path: int(IMAGE_RE.fullmatch(path.name).group("number")))


def recipe_slug(path: Path) -> str:
    return path.stem


def recipe_page(path: Path, image_dir: Path) -> dict[str, object]:
    try:
        document = frontmatter.load(path)
    except (OSError, ValueError) as exc:
        fail(f"Could not read recipe '{path.name}': {exc}")
    metadata = document.metadata
    portions_value = metadata.get("portions")
    portions = None
    if portions_value not in (None, ""):
        try:
            portions = int(portions_value)
        except (TypeError, ValueError):
            fail(f"Recipe '{path.name}' has invalid portions; use a positive integer")
        if isinstance(portions_value, bool) or (
            isinstance(portions_value, float) and not portions_value.is_integer()
        ):
            fail(f"Recipe '{path.name}' has invalid portions; use a positive integer")
        if portions < 1:
            fail(f"Recipe '{path.name}' has invalid portions; use a positive integer")

    title = str(metadata.get("title") or path.stem.replace("-", " ").title())
    slug = recipe_slug(path)
    content, ingredients = markdown_with_ingredients(document.content)
    images = recipe_images(path)
    for image in images:
        image_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(image, image_dir / image.name)

    excluded = {"title", "tags", "portions"}
    properties = [
        {"name": str(key), "value": value}
        for key, value in metadata.items()
        if key not in excluded
    ]
    return {
        "slug": slug,
        "title": title,
        "lang": str(metadata.get("lang", "")),
        "tags": parse_tags(metadata.get("tags")),
        "properties": properties,
        "excerpt": first_paragraph(document.content),
        "portions": portions,
        "ingredients": ingredients,
        "ingredient_list": aggregate_ingredients(ingredients),
        "content": content,
        "images": [image.name for image in images],
    }


def recipe_index_data(recipes: list[dict[str, object]]) -> str:
    entries = []
    for recipe in recipes:
        search_terms = [
            str(recipe["title"]),
            *recipe["tags"],
            str(recipe["content"]),
            *(str(ingredient["raw"]) for ingredient in recipe["ingredients"]),
            *(
                f'{property_["name"]} {property_["value"]}'
                for property_ in recipe["properties"]
            ),
        ]
        entries.append({
            "slug": recipe["slug"],
            "title": recipe["title"],
            "tags": recipe["tags"],
            "excerpt": recipe["excerpt"],
            "search": " ".join([*search_terms, str(recipe["excerpt"])]),
            "lang": recipe["lang"],
        })
    return json.dumps(entries, ensure_ascii=False)


def render_template(path: Path, **values: str) -> str:
    template = path.read_text(encoding="utf-8")
    for name, value in values.items():
        template = template.replace("{{ " + name + " }}", value)
    return template


def build(source: Path, destination: Path) -> int:
    source = source.resolve()
    destination = destination.resolve()
    if not source.is_dir():
        fail(f"Recipe directory does not exist: {source}")
    if source == destination or source in destination.parents:
        fail("Output directory must be outside the recipe source directory")
    paths = sorted(path for path in source.glob("*.md") if path.is_file())
    if not paths:
        fail(f"No Markdown recipes found in {source}")

    package_dir = Path(__file__).parent
    static = package_dir / "static"
    templates = package_dir / "templates"
    assets = destination / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    for filename in ("style.css", "app.js", "recipe.js"):
        shutil.copyfile(static / filename, assets / filename)
    image_dir = assets / "images"
    data_dir = destination / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    recipes_dir = destination / "recipes"
    recipes_dir.mkdir(parents=True, exist_ok=True)
    recipes = []
    seen = set()
    for path in paths:
        slug = recipe_slug(path)
        if slug in seen:
            fail(f"Recipe filenames must be unique: {path.name}")
        seen.add(slug)
        recipe = recipe_page(path, image_dir)
        recipes.append(recipe)
        (data_dir / f"{slug}.json").write_text(
            json.dumps(recipe, ensure_ascii=False, default=str), encoding="utf-8"
        )
        page = render_template(
            templates / "recipe.html",
            slug=html.escape(slug, quote=True),
            title=html.escape(str(recipe["title"])),
        )
        (recipes_dir / f"{slug}.html").write_text(page, encoding="utf-8")
    (destination / "index.html").write_text(
        (templates / "index.html").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (destination / "recipes.json").write_text(recipe_index_data(recipes), encoding="utf-8")
    return len(recipes)


@app.command("build")
def build_command(
    source: Annotated[Path, typer.Argument(help="Directory containing recipe Markdown files")],
    destination: Annotated[
        Path, typer.Option("--destination", "-d", help="Generated website directory")
    ] = Path("site"),
) -> None:
    """Build the static recipe website."""
    count = build(source, destination)
    typer.echo(f"Built {count} recipes into {destination}")


if __name__ == "__main__":
    app()
