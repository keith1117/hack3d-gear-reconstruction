from pathlib import Path
import numpy as np
from PIL import Image
import trimesh
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]


def draw_model(ax, vertices, faces, title):
    ax.plot_trisurf(vertices[:, 0], vertices[:, 1], vertices[:, 2], triangles=faces,
                    color='#a2b2c0', linewidth=0, antialiased=False, shade=True)
    low = vertices.min(axis=0)
    high = vertices.max(axis=0)
    ax.set_xlim(low[0], high[0])
    ax.set_ylim(low[1], high[1])
    ax.set_zlim(low[2], high[2])
    ax.set_box_aspect(high - low)
    ax.view_init(30, -60)
    ax.set_axis_off()
    ax.set_title(title, fontsize=11)


def main():
    preview = np.load(ROOT / 'results/preview_geometry.npz')
    original = trimesh.load_mesh(ROOT / 'cad/final_gear.stl')
    figure = plt.figure(figsize=(10, 4.5))
    draw_model(figure.add_subplot(121, projection='3d'), preview['vertices'], preview['faces'],
               'Approximate model from CT slices')
    draw_model(figure.add_subplot(122, projection='3d'), original.vertices, original.faces,
               'Recovered original STL - final model')
    figure.tight_layout()
    figure.savefig(ROOT / 'figures/gear_comparison.png', dpi=180)
    plt.close(figure)

    figure = plt.figure(figsize=(6, 4.5))
    draw_model(figure.add_subplot(111, projection='3d'), original.vertices, original.faces,
               'Final gear model')
    figure.tight_layout()
    figure.savefig(ROOT / 'figures/final_gear.png', dpi=180)
    plt.close(figure)

    slices = np.load(ROOT / 'results/example_slices.npz')
    figure, axes = plt.subplots(2, 4, figsize=(10, 5.5))
    for column, number in enumerate(['331', '714', '1274', '2191']):
        axes[0, column].imshow(slices[number][0], cmap='gray', vmin=0, vmax=255)
        axes[1, column].imshow(slices[number][1], cmap='gray', vmin=0, vmax=255)
        axes[0, column].set_title('Slice ' + number, fontsize=10)
        for row in range(2):
            axes[row, column].axis('off')
    figure.text(0.01, 0.74, 'Aligned', rotation=90, va='center', fontsize=10)
    figure.text(0.01, 0.26, 'Mask', rotation=90, va='center', fontsize=10)
    figure.tight_layout(rect=(0.02, 0, 1, 1))
    figure.savefig(ROOT / 'figures/aligned_slices.png', dpi=160)
    plt.close(figure)

    files = sorted((ROOT / 'Hack-Gear').glob('*.jpg'))
    figure, axes = plt.subplots(1, 2, figsize=(8, 3.2))
    index = next(i for i, path in enumerate(files) if int(path.stem[8:]) == 331)
    image = Image.open(files[index]).convert('L').resize((400, 400))
    axes[0].imshow(image, cmap='gray')
    axes[1].imshow(image.rotate(-index, resample=Image.Resampling.BICUBIC), cmap='gray')
    axes[0].set_title('Slice 331 - provided', fontsize=11)
    axes[1].set_title('Slice 331 - rotation corrected', fontsize=11)
    for axis in axes:
        axis.axis('off')
    figure.tight_layout()
    figure.savefig(ROOT / 'figures/rotation_correction.png', dpi=160)
    plt.close(figure)


if __name__ == '__main__':
    main()
