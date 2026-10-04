from pathlib import Path
import json
import shutil

from PIL import Image
import py7zr
import trimesh


ROOT = Path(__file__).resolve().parents[1]


def main():
    links = []
    for path in sorted((ROOT / 'Hack-Gear').glob('*.jpg')):
        with Image.open(path) as image:
            title = image.getexif().get(40091)  # Windows XPTitle field
        if title:
            if isinstance(title, tuple):
                title = bytes(title)
            url = title.decode('utf-16-le').rstrip('\x00')
            links.append({'file': path.name, 'tag': 'XPTitle (40091)', 'url': url})
    (ROOT / 'results/metadata_links.json').write_text(json.dumps(links, indent=2) + '\n')

    riddle = (ROOT / 'clues/Mini_Riddle.txt').read_text()
    word = riddle.split()[-1]
    # The Caesar clue uses an encryption shift of three letters backwards.
    password = ''.join(chr((ord(letter) - ord('A' if letter.isupper() else 'a') + 3) % 26 +
                            ord('A' if letter.isupper() else 'a')) for letter in word)
    destination = ROOT / 'cad/recovered'
    destination.mkdir(exist_ok=True)
    with py7zr.SevenZipFile(ROOT / 'clues/Original STL.7z', password=password) as archive:
        archive.extractall(destination)
    original = destination / 'Original STL/Hack gear.STL'
    final = ROOT / 'cad/final_gear.stl'
    shutil.copyfile(original, final)
    mesh = trimesh.load_mesh(final)
    summary = {'riddle_word': word, 'caesar_shift_to_decode': 3, 'archive_password': password,
               'source_image': 'Ball_rec2161.jpg', 'archive': 'clues/Original STL.7z',
               'final_file': 'cad/final_gear.stl', 'extents_mm': mesh.extents.tolist(),
               'triangles': len(mesh.faces), 'watertight': bool(mesh.is_watertight),
               'winding_consistent': bool(mesh.is_winding_consistent),
               'closed_shells': len(mesh.split()), 'volume_mm3': float(mesh.volume)}
    (ROOT / 'results/recovered_model_summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
