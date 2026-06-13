import csv

CSV_FILE = r"classified_galaxies\classification_report.csv"
OUT_FILE = "galaxy_rows.tex"

def esc(s):
    return str(s).replace("_", r"\_").replace("&", r"\&")

with open(CSV_FILE, encoding="utf-8") as f:
    lines = f.read().splitlines()[1:]

with open(OUT_FILE, "w", encoding="utf-8") as out:
    for line in lines:
        file, name, morph, folder, desc = line.split(",", 4)

        out.write(
            rf"""\includegraphics[width=2.2cm]{{images/{file}}}
& {esc(name)}
& {esc(morph)}
& {esc(desc)} \\
\hline

"""
        )

print("Готово: galaxy_rows.tex")