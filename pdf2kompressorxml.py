import os
import re
import pdfplumber
import xml.etree.ElementTree as ET

SOURCE_DIR = "input_pdfs"
TARGET_DIR = "output_xml"

# Stelle sicher, dass Zielordner existiert
os.makedirs(TARGET_DIR, exist_ok=True)


def extract_pressures(text):
    """
    Sucht nach allen Druckangaben wie '5 bar', '7,5 bar' usw.
    Gibt eine Liste mit float-Werten zurück (in Original-Reihenfolge, ohne Duplikate).
    """
    matches = re.findall(r"(\d+(?:[.,]\d+)?)\s*bar", text)
    pressures = []
    for m in matches:
        p = m.replace(",", ".")
        try:
            pressures.append(float(p))
        except:
            pass

    # Duplikate entfernen, Reihenfolge beibehalten
    seen = set()
    unique_pressures = []
    for p in pressures:
        if p not in seen:
            seen.add(p)
            unique_pressures.append(p)
    return unique_pressures


def extract_data_from_pdf(pdf_path):
    """
    Extrahiert die Tabellen (FAD, Leistung, Drehzahl) aus einem PDF
    und ordnet sie den erkannten Referenzdrücken zu.
    """
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"

    # Druckwerte ermitteln
    pressures = extract_pressures(text)

    # FAD- und Power-Blöcke suchen
    fad_blocks = re.findall(r"FAD\*.*?(?=Total input power)", text, flags=re.S)
    pow_blocks = re.findall(r"Total input power\*.*?(?=FAD\*|$)", text, flags=re.S)

    result = []
    for idx, (fad_block, pow_block) in enumerate(zip(fad_blocks, pow_blocks)):
        pressure = pressures[idx] if idx < len(pressures) else None

        # FAD-Werte (Volumenstrom + Drehzahl)
        fad_matches = re.findall(r"([\d+.\d+,]+)\s*\((\d+)\)", fad_block)

        # Leistungswerte
        pow_matches = re.findall(r"([\d+.\d+,]+)\s*\(", pow_block)

        # Kommas in Dezimalpunkte umwandeln
        fad_values = [(v.replace(",", "."), d) for v, d in fad_matches]
        pow_values = [p.replace(",", ".") for p in pow_matches]

        curves = []
        for (v, d), l in zip(fad_values, pow_values):
            # print({"V": v, "L": l, "D": d})
            curves.append({"V": v, "L": l, "D": d})

        result.append({"pressure": pressure, "curves": curves})
    return result


def indent(elem, level=0):
    """
    Sorgt für sauberes Einrücken in der XML-Ausgabe
    """
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for child in elem:
            indent(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = i
    if level and (not elem.tail or not elem.tail.strip()):
        elem.tail = i


def create_xml(data, output_path):
    root = ET.Element("Volumenstrom_Leistungstabelle")
    for entry in data:
        curve = ET.SubElement(root, "Volumenstrom_Leistungskurve")
        ET.SubElement(curve, "Referenzdruck").text = str(entry["pressure"])
        vl_points = ET.SubElement(curve, "VL_Points")
        for vl in entry["curves"]:
            ET.SubElement(vl_points, "VL", V=vl["V"], L=vl["L"], D=vl["D"])

    # XML schön formatieren
    indent(root)

    tree = ET.ElementTree(root)
    tree.write(output_path, encoding="utf-8", xml_declaration=True)


def main():
    for file in os.listdir(SOURCE_DIR):
        if file.lower().endswith(".pdf"):
            print(file)
            pdf_path = os.path.join(SOURCE_DIR, file)
            xml_path = os.path.join(
                TARGET_DIR, os.path.splitext(file)[0] + ".kompressor"
            )
            data = extract_data_from_pdf(pdf_path)
            create_xml(data, xml_path)
            print(f"✅ Erzeugt: {xml_path}")


if __name__ == "__main__":
    main()
