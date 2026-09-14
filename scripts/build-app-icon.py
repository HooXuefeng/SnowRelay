"""Create SnowRelay application icons from the approved high-resolution master."""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets/brand"
MASTER = ROOT / "design/brand/snowrelay-logo-master.png"


def prepare_master(source: Image.Image) -> Image.Image:
    image = source.convert("RGB")
    pixels = image.load()
    bounds = [image.width, image.height, 0, 0]
    found = False
    for y in range(image.height):
        for x in range(image.width):
            red, green, blue = pixels[x, y]
            if blue > 120 and blue > red + 32 and blue > green + 32:
                found = True
                bounds = [min(bounds[0], x), min(bounds[1], y), max(bounds[2], x), max(bounds[3], y)]
    if not found:
        raise RuntimeError("The SnowRelay master image contains no visible indigo tile.")
    tile = image.crop((bounds[0] + 4, bounds[1] + 4, bounds[2] - 3, bounds[3] - 3))
    tile = tile.resize((1024, 1024), Image.Resampling.LANCZOS).convert("RGBA")
    mask = Image.new("L", tile.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, 1023, 1023), radius=185, fill=255)
    tile.putalpha(mask)
    return tile


def main() -> None:
    if not MASTER.is_file():
        raise FileNotFoundError(f"Missing approved SnowRelay master: {MASTER}")
    OUT.mkdir(parents=True, exist_ok=True)
    image = prepare_master(Image.open(MASTER))
    image.save(OUT / "snowrelay-app.png")
    for size in (32, 48, 64):
        image.resize((size, size), Image.Resampling.LANCZOS).save(OUT / f"snowrelay-app-{size}.png")
    image.save(OUT / "snowrelay.ico", sizes=[(size, size) for size in (16, 20, 24, 32, 40, 48, 64, 128, 256)])
    with Image.open(OUT / "snowrelay.ico") as icon:
        assert {(16, 16), (32, 32), (48, 48), (256, 256)} <= icon.ico.sizes()
    print("Built SnowRelay icon from the approved master: 9 Windows sizes.")


if __name__ == "__main__":
    main()
