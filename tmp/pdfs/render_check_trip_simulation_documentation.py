from pathlib import Path

import pypdfium2 as pdfium
from pypdf import PdfReader


PDF_PATH = Path("output/pdf/trip_simulation_and_fuel_card_modality.pdf")
OUT_DIR = Path("tmp/pdfs/rendered_trip_modality_doc")


reader = PdfReader(str(PDF_PATH))
print("pages", len(reader.pages))
text = "\n".join((page.extract_text() or "") for page in reader.pages)
for needle in [
	"Trip Simulation and Fuel Card Modality",
	"Net Profit Margin",
	"Driver Mileage Per Day",
	"Fuel Card Modality",
	"Fuel Card Movement Report",
	"Project Customer Details",
]:
	print(needle, needle in text)

OUT_DIR.mkdir(parents=True, exist_ok=True)
for old_file in OUT_DIR.glob("*.png"):
	old_file.unlink()

pdf = pdfium.PdfDocument(str(PDF_PATH))
for idx, page in enumerate(pdf):
	bitmap = page.render(scale=1.5)
	image = bitmap.to_pil()
	image.save(OUT_DIR / f"page-{idx + 1:02d}.png")

print("rendered", len(pdf), "pages")
