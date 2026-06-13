import os
import re
import zipfile
import shutil
from pathlib import Path
from astroquery.simbad import Simbad




INPUT_PATH = r"C:\Users\kater\Desktop\лаби\galaxy_images"
OUTPUT_DIR = r"C:\Users\kater\Desktop\лаби\classified_galaxies"


def extract_archive_if_needed(path):
    path = Path(path)

    if path.is_dir():
        return path

    if path.suffix.lower() == ".zip":
        extract_dir = path.with_suffix("")
        extract_dir.mkdir(exist_ok=True)

        with zipfile.ZipFile(path, "r") as zip_ref:
            zip_ref.extractall(extract_dir)

        return extract_dir

    raise ValueError("Потрібно вказати шлях до папки або .zip архіву")


def get_galaxy_name(filename):
    name = Path(filename).stem.upper()

    # прибираємо номер на початку: 01_NGC_4254 -> NGC_4254
    name = re.sub(r"^\d+[_\-\s]*", "", name)

    # шукаємо NGC, IC або M
    match = re.search(r"\b(NGC|IC|M)[_\-\s]*(\d+)\b", name)

    if not match:
        return None

    catalog = match.group(1)
    number = match.group(2)

    return f"{catalog} {number}"


def safe_folder_name(text):
    text = str(text).strip()
    text = text.replace("/", "-")
    text = text.replace("\\", "-")
    text = text.replace(":", "-")
    text = text.replace("*", "")
    text = text.replace("?", "")
    text = text.replace('"', "")
    text = text.replace("<", "")
    text = text.replace(">", "")
    text = text.replace("|", "")
    return text


def explain_type(morph_type):
    if morph_type is None:
        return "Невідомий тип"

    t = str(morph_type).strip()

    if t in ["", "--", "None"]:
        return "Невідомий тип"

    tu = t.upper()

    if tu.startswith("E"):
        return "Еліптична галактика"

    if "S0" in tu:
        return "Лінзоподібна галактика"

    if tu.startswith("SB"):
        return "Спіральна галактика з баром"

    if tu.startswith("SAB"):
        return "Перехідна спіральна галактика, слабкий бар"

    if tu.startswith("SA"):
        return "Спіральна галактика без бара"

    if "IRR" in tu or "IM" in tu:
        return "Неправильна галактика"

    if tu.startswith("S"):
        return "Спіральна галактика"

    return "Інший або змішаний морфологічний тип"


def query_morphology(name):
    customSimbad = Simbad()
    customSimbad.add_votable_fields("otype", "morphtype")

    try:
        result = customSimbad.query_object(name)

        if result is None:
            return None

        for col in ["morph_type", "MORPHTYPE", "Morph_type"]:
            if col in result.colnames:
                value = result[col][0]
                if value is not None and str(value).strip() not in ["", "--", "None"]:
                    return str(value).strip()

        return None

    except Exception as e:
        print(f"Помилка для {name}: {e}")
        return None


def main():
    source_dir = extract_archive_if_needed(INPUT_PATH)

    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(exist_ok=True)

    image_extensions = [".jpg", ".jpeg", ".png", ".webp"]

    files = [
        f for f in source_dir.rglob("*")
        if f.suffix.lower() in image_extensions
    ]

    print(f"Знайдено файлів: {len(files)}")

    report = []

    for file in files:

        galaxy_name = get_galaxy_name(file.name)

        if not galaxy_name:
            morph = None
            galaxy_type = "Unknown"
            galaxy_description = "Невідомий тип"

        else:
            morph = query_morphology(galaxy_name)

            if morph is None:
                galaxy_type = "Unknown"
                galaxy_description = "Невідомий тип"

            else:
                galaxy_type = safe_folder_name(morph)
                galaxy_description = explain_type(morph)

        target_folder = output_dir / galaxy_type
        target_folder.mkdir(exist_ok=True)

        target_path = target_folder / file.name

        shutil.copy2(file, target_path)

        report.append((
            file.name,
            galaxy_name,
            morph,
            galaxy_type,
            galaxy_description
        ))

        print(
            f"{file.name} -> "
            f"{galaxy_name} -> "
            f"{morph} -> "
            f"{galaxy_type}"
        )

    report_path = output_dir / "classification_report.csv"

    with open(report_path, "w", encoding="utf-8") as f:

        f.write(
            "file,galaxy_name,morphology,folder,description\n"
        )

        for row in report:
            f.write(",".join([str(x) for x in row]) + "\n")

    print("\nГотово!")
    print(f"Результат: {output_dir}")

if __name__ == "__main__":
    main()