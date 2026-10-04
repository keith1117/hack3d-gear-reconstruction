from pathlib import Path
import csv
import hashlib
import json
import time

import numpy as np
from PIL import Image
from scipy import ndimage
from scipy.signal import find_peaks
from skimage.measure import marching_cubes
import trimesh


ROOT = Path(__file__).resolve().parents[1]
SIZE = 400
PIXEL_MM = 0.0055
STEP = PIXEL_MM * 4000 / SIZE
THRESHOLD = 110


def keep_largest(mask):
    labels, count = ndimage.label(mask)
    if count == 0:
        return mask
    sizes = np.bincount(labels.ravel())
    sizes[0] = 0
    return labels == sizes.argmax()


def read_slice(path, angle):
    with Image.open(path) as image:
        small = image.convert('L').resize((SIZE, SIZE))
        aligned = small.rotate(-angle, resample=Image.Resampling.BICUBIC)
    gray = np.asarray(aligned, dtype=np.float32)
    mask = ndimage.gaussian_filter(gray, 0.8) > THRESHOLD
    y, x = np.indices(mask.shape)
    mask[(x - SIZE / 2)**2 + (y - SIZE / 2)**2 > (SIZE / 2 - 5)**2] = False
    mask = keep_largest(mask)
    # Fill isolated dark pixels, but keep the larger holes.
    holes, count = ndimage.label(~mask)
    sizes = np.bincount(holes.ravel())
    mask |= sizes[holes] < 6
    return gray, mask


def main():
    start = time.time()
    files = sorted((ROOT / 'Hack-Gear').glob('Ball_rec*.jpg'))
    numbers = np.array([int(p.stem.replace('Ball_rec', '')) for p in files])
    for folder in ['cad', 'results', 'figures']:
        (ROOT / folder).mkdir(exist_ok=True)

    fields = []
    inventory = []
    sample_numbers = [103, 331, 714, 801, 1063, 1274, 1515, 1863, 2191, 2242]
    samples = {}
    trailers = 0
    for order, path in enumerate(files):
        raw = path.read_bytes()
        with Image.open(path) as image:
            shape = image.size
            has_exif = bool(image.getexif())
        if raw.rfind(b'\xff\xd9') != len(raw) - 2:
            trailers += 1
        gray, mask = read_slice(path, order)
        # A signed distance gives smoother interpolation than blending binary masks.
        distance = (ndimage.distance_transform_edt(mask) -
                    ndimage.distance_transform_edt(~mask))
        fields.append(distance.astype(np.float32))
        inventory.append([path.name, int(numbers[order]), round(numbers[order] * PIXEL_MM, 4),
                          order, shape[0], shape[1], len(raw),
                          hashlib.sha256(raw).hexdigest(), has_exif, int(mask.sum())])
        if numbers[order] in sample_numbers:
            samples[str(numbers[order])] = np.stack([gray, mask.astype(float) * 255])
        if order % 100 == 0:
            print(f'Read {order + 1}/{len(files)} slices', flush=True)

    with (ROOT / 'results/dataset_inventory.csv').open('w', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(['filename', 'slice_number', 'z_mm', 'undo_rotation_deg',
                         'width_px', 'height_px', 'bytes', 'sha256', 'has_exif', 'mask_pixels'])
        writer.writerows(inventory)
    np.savez_compressed(ROOT / 'results/example_slices.npz', **samples)

    # Use the original slice numbers for height, not positions in the file list.
    # This keeps the missing ranges from shrinking the model.
    target = np.arange(numbers[0], numbers[-1] + 11, 10)
    volume = np.empty((len(target), SIZE, SIZE), dtype=np.float32)
    for i, number in enumerate(target):
        right = np.searchsorted(numbers, number)
        if right == 0:
            volume[i] = fields[0]
        elif right == len(numbers):
            volume[i] = fields[-1]
        else:
            left = right - 1
            fraction = (number - numbers[left]) / (numbers[right] - numbers[left])
            volume[i] = fields[left] * (1 - fraction) + fields[right] * fraction
    volume = ndimage.gaussian_filter(volume, 0.6)
    # Add empty space at both ends so marching cubes closes the surface.
    volume = np.pad(volume, ((1, 1), (1, 1), (1, 1)), constant_values=-2)
    vertices, faces, _, _ = marching_cubes(volume, level=0, spacing=(STEP, STEP, STEP))
    vertices = vertices[:, [2, 1, 0]]
    vertices[:, 1] *= -1
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
    pieces = mesh.split(only_watertight=False)
    mesh = max(pieces, key=lambda part: len(part.faces))
    mesh.fix_normals()
    offset = np.array([mesh.bounds[:, 0].mean(), mesh.bounds[:, 1].mean(), mesh.bounds[0, 2]])
    mesh.vertices -= offset
    mesh.export(ROOT / 'cad/reconstructed_gear.stl')
    preview_vertices, preview_faces, _, _ = marching_cubes(volume, level=0,
                                                          spacing=(STEP, STEP, STEP), step_size=3)
    preview_vertices = preview_vertices[:, [2, 1, 0]]
    preview_vertices[:, 1] *= -1
    preview_vertices -= offset
    np.savez_compressed(ROOT / 'results/preview_geometry.npz',
                        vertices=preview_vertices, faces=preview_faces)

    # Estimate the tooth count from a complete lower slice.
    mask = samples['331'][1] > 0
    y, x = np.indices(mask.shape)
    bore = keep_largest(~mask & ((x - 200)**2 + (y - 200)**2 < 65**2))
    cy, cx = ndimage.center_of_mass(bore)
    angles = np.linspace(0, 2 * np.pi, 1440, endpoint=False)
    radii = np.linspace(100, 195, 380)
    values = ndimage.map_coordinates(mask.astype(float),
                                    [cy + np.sin(angles[:, None]) * radii,
                                     cx + np.cos(angles[:, None]) * radii], order=1)
    outline = (values > 0.5).sum(axis=1) * (radii[1] - radii[0]) + radii[0]
    extended = np.r_[outline[-60:], outline, outline[:60]]
    peaks, _ = find_peaks(extended, distance=40, prominence=5)
    peaks = peaks[(peaks >= 60) & (peaks < 1500)] - 60
    gaps = [[int(a + 1), int(b - 1)] for a, b in zip(numbers, numbers[1:]) if b - a > 1]
    result = {
        'input_files': len(files), 'first_slice': int(numbers[0]), 'last_slice': int(numbers[-1]),
        'missing_slices_between_endpoints': int(numbers[-1] - numbers[0] + 1 - len(files)),
        'missing_ranges': gaps, 'jpeg_files_with_trailing_data': trailers,
        'files_with_exif': sum(row[8] for row in inventory),
        'pixel_and_slice_spacing_mm': PIXEL_MM, 'output_voxel_mm': STEP,
        'rotation_rule': 'Rotate each image clockwise by its zero-based sorted file index in degrees.',
        'threshold': THRESHOLD, 'estimated_teeth': len(peaks),
        'mesh_offset_before_centering_mm': offset.tolist(),
        'estimated_tip_diameter_mm': float(np.median(outline[peaks]) * 2 * STEP),
        'estimated_root_diameter_mm': float(np.quantile(outline, 0.05) * 2 * STEP),
        'estimated_bore_diameter_mm': float(2 * np.sqrt(bore.sum() / np.pi) * STEP),
        'mesh_extents_mm': mesh.extents.tolist(), 'mesh_volume_mm3': float(mesh.volume),
        'vertices': len(mesh.vertices), 'triangles': len(mesh.faces),
        'watertight': bool(mesh.is_watertight), 'winding_consistent': bool(mesh.is_winding_consistent),
        'connected_components': len(mesh.split(only_watertight=False)),
        'seconds': round(time.time() - start, 1),
        'limitations': ['Missing ranges are interpolated, so their geometry is an estimate.',
                        'The lower face is capped at the earliest supplied slice.',
                        'Small scan details are smoothed; this is not a precision manufacturing model.']
    }
    (ROOT / 'results/reconstruction_summary.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
