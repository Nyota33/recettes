import json
from pathlib import Path

from recettes.cli import aggregate_ingredients, build, parse_quantity


def test_parse_quantity_and_guessed_count_unit() -> None:
    assert parse_quantity("50g de beurre") == (50.0, "g", "de beurre")
    assert parse_quantity("1cas d'huile") == (1.0, "cas", "d'huile")
    assert parse_quantity("1/2 cac") == (0.5, "cac", "")
    assert parse_quantity("0.5cac") == (0.5, "cac", "")
    assert parse_quantity("4 oignons") == (4.0, "", "oignons")
    assert parse_quantity("comté râpé") == (None, "", "comté râpé")


def test_aggregate_repeated_ingredients_by_name_and_unit() -> None:
    ingredients = [
        {"amount": 50.0, "unit": "g", "name": "de beurre", "raw": "50g de beurre"},
        {"amount": 20.0, "unit": "g", "name": "de beurre", "raw": "20g de beurre"},
        {"amount": 0.5, "unit": "cac", "name": "de sel", "raw": "1/2 cac de sel"},
        {"amount": 0.5, "unit": "cac", "name": "de sel", "raw": "0.5cac de sel"},
    ]

    aggregated = aggregate_ingredients(ingredients)

    assert [(item["amount"], item["unit"], item["name"]) for item in aggregated] == [
        (70.0, "g", "de beurre"),
        (1.0, "cac", "de sel"),
    ]


def test_build_recipe_site_with_frontmatter_images_and_portion_controls(tmp_path: Path) -> None:
    source = tmp_path / "recipes"
    source.mkdir()
    (source / "soupe-oignon.md").write_text(
        "---\ntitle: Soupe à l'oignon\nportions: 4\npreparation: 45\n"
        "cuisson: 15\ntags: hiver, soupe\nlang: fr\nauteur: Test\n---\n\n"
        "# Préparation\n\nMélangez {{ 4 oignons }} et {{ 50g de beurre }}.\n\n"
        "Ajoutez {{ 20 g de beurre }} et {{ 1/2 cac de sel }}.\n"
        "Goûtez, puis ajoutez {{ 0.5cac de sel }} si besoin.\n",
        encoding="utf-8",
    )
    (source / "soupe-oignon-1.jpg").write_bytes(b"fake jpeg")
    output = tmp_path / "site"

    assert build(source, output) == 1

    index = (output / "index.html").read_text(encoding="utf-8")
    recipe = (output / "recipes" / "soupe-oignon.html").read_text(encoding="utf-8")
    data = json.loads((output / "data" / "soupe-oignon.json").read_text(encoding="utf-8"))
    assert '<template id="recipe-card-template">' in index
    assert '<p class="card-excerpt" data-recipe-excerpt></p>' in index
    assert '<template id="recipe-property-template">' in recipe
    assert '<h2 class="ingredients-title">Ingredients</h2>' in recipe
    assert '<div class="recipe-meta-row">' in recipe
    assert '<div class="ingredients-heading">' in recipe
    assert 'data-recipe="soupe-oignon"' in recipe
    assert data["title"] == "Soupe à l'oignon"
    assert data["lang"] == "fr"
    assert [item["name"] for item in data["properties"]] == [
        "preparation",
        "cuisson",
        "lang",
        "auteur",
    ]
    assert [item["value"] for item in data["properties"]] == [45, 15, "fr", "Test"]
    assert data["portions"] == 4
    assert [(item["amount"], item["unit"], item["name"]) for item in data["ingredient_list"]] == [
        (4.0, "", "oignons"),
        (70.0, "g", "de beurre"),
        (1.0, "cac", "de sel"),
    ]
    assert "RECIPEINGREDIENTTOKEN0END" in data["content"]
    index_data = json.loads((output / "recipes.json").read_text(encoding="utf-8"))
    assert "4 oignons" in index_data[0]["search"]
    assert "auteur Test" in index_data[0]["search"]
    assert index_data[0]["excerpt"] == "Mélangez 4 oignons et 50g de beurre."
    assert data["images"] == ["soupe-oignon-1.jpg"]
    assert (output / "assets" / "images" / "soupe-oignon-1.jpg").read_bytes() == b"fake jpeg"


def test_recipe_without_portions_has_no_toggle_and_properties_are_optional(
    tmp_path: Path,
) -> None:
    source = tmp_path / "recipes"
    source.mkdir()
    (source / "simple.md").write_text(
        "---\ntitle: Simple\ntags: quick\n---\n\nJust a recipe.\n", encoding="utf-8"
    )
    output = tmp_path / "site"

    build(source, output)

    data = json.loads((output / "data" / "simple.json").read_text(encoding="utf-8"))
    assert data["portions"] is None
    assert data["properties"] == []
    assert data["ingredient_list"] == []
    script = (output / "assets" / "recipe.js").read_text(encoding="utf-8")
    assert "if (recipe.portions == null)" in script
