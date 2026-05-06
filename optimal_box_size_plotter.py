#!/usr/bin/env python3

import argparse
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Patch


def electron_wavelength(voltage_kv):
    """
    Relativistic electron wavelength in Angstroms.
    """
    V = voltage_kv * 1000.0

    h = 6.62607015e-34
    m = 9.1093837015e-31
    e = 1.602176634e-19
    c = 299792458.0

    wavelength_m = h / np.sqrt(
        2 * m * e * V * (1 + (e * V) / (2 * m * c**2))
    )

    return wavelength_m * 1e10


def optimal_box_size_angstrom(particle_diameter, wavelength, defocus, resolution):
    """
    B = D + 2 L defocus / resolution

    All values are in Angstroms.
    """
    return particle_diameter + 2.0 * wavelength * defocus / resolution


def ctf_aliasing_mask(wavelength, defocus_angstrom, resolution, box_size_px, pixel_size):
    """
    Return True where CTF oscillations are under-sampled by the Fourier-space
    sampling of a fixed extraction box.

    Fourier-space sampling:
        delta_s = 1 / (N * a)

    Approximate CTF phase:
        chi(s) ~= pi * wavelength * defocus * s^2

    Local phase step per Fourier pixel:
        delta_chi ~= 2 pi wavelength defocus s delta_s

    Aliasing-risk criterion:
        delta_chi > pi

    Boundary:
        d_alias = 2 * wavelength * defocus / (N * a)

    Aliasing-risk region:
        resolution < d_alias

    where:
        N = box_size_px
        a = pixel size in Angstroms/pixel
    """
    box_width_angstrom = box_size_px * pixel_size
    d_alias = 2.0 * wavelength * defocus_angstrom / box_width_angstrom
    return resolution < d_alias


def practical_box_sizes(min_size, max_size):
    """
    Sparse practical cryoEM box sizes in pixels.
    """
    good_sizes = np.array([
        64, 96, 128, 160, 192,
        224, 256, 288, 320, 384,
        448, 512, 576, 640, 768,
        896, 1024, 1152, 1280, 1536,
        1792, 2048, 2304, 2560, 3072,
        3584, 4096,
    ])

    return good_sizes[
        (good_sizes >= min_size) &
        (good_sizes <= max_size)
    ]


def choose_contour_levels(values, max_contours=6, trim_fraction=0.08):
    """
    Choose a sparse set of practical contour levels.
    """
    values = np.asarray(values)

    vmin = values.min()
    vmax = values.max()
    span = vmax - vmin

    lower = vmin + trim_fraction * span
    upper = vmax - trim_fraction * span

    levels = practical_box_sizes(lower, upper)

    if len(levels) == 0:
        levels = practical_box_sizes(vmin, vmax)

    if len(levels) == 0:
        return np.linspace(lower, upper, max_contours)

    if len(levels) > max_contours:
        idx = np.linspace(0, len(levels) - 1, max_contours, dtype=int)
        levels = levels[idx]

    return levels


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Plot cryoEM optimal box size as a function of defocus "
            "and target resolution."
        )
    )

    parser.add_argument(
        "--diameter",
        type=float,
        required=True,
        help="Particle diameter in Angstroms.",
    )

    parser.add_argument(
        "--voltage",
        type=float,
        default=300,
        help="Accelerating voltage in kV. Default: 300.",
    )

    parser.add_argument(
        "--defocus-min",
        type=float,
        default=0.5,
        help="Minimum defocus in micrometers. Default: 0.5.",
    )

    parser.add_argument(
        "--defocus-max",
        type=float,
        default=3.0,
        help="Maximum defocus in micrometers. Default: 3.0.",
    )

    parser.add_argument(
        "--resolution-min",
        type=float,
        default=2.0,
        help="Best target resolution in Angstroms. Default: 2.0.",
    )

    parser.add_argument(
        "--resolution-max",
        type=float,
        default=10.0,
        help="Worst target resolution in Angstroms. Default: 10.0.",
    )

    parser.add_argument(
        "--pixel-size",
        type=float,
        default=None,
        help="Pixel size in Angstroms/pixel. If provided, plot box size in pixels.",
    )

    parser.add_argument(
        "--box-size",
        type=float,
        default=None,
        help=(
            "Actual extraction box size in pixels. Requires --pixel-size. "
            "If provided, shades regions where this box size under-samples "
            "CTF oscillations."
        ),
    )

    parser.add_argument(
        "--max-contours",
        type=int,
        default=6,
        help="Maximum number of box-size contour lines to show. Default: 6.",
    )

    parser.add_argument(
        "--trim-fraction",
        type=float,
        default=0.08,
        help=(
            "Fraction of box-size range to trim before choosing contour levels. "
            "Default: 0.08."
        ),
    )

    parser.add_argument(
        "--line-color",
        type=str,
        default="white",
        help="Contour line and label color. Default: white.",
    )

    parser.add_argument(
        "--alias-color",
        type=str,
        default="red",
        help="Aliasing-risk shading color. Default: red.",
    )

    parser.add_argument(
        "--alias-alpha",
        type=float,
        default=0.22,
        help="Aliasing-risk shading opacity. Default: 0.22.",
    )

    parser.add_argument(
        "--output",
        type=str,
        default="optimal_box_size_plot.png",
        help="Output image filename. Default: optimal_box_size_plot.png.",
    )

    parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="Output figure DPI. Default: 300.",
    )

    args = parser.parse_args()

    if args.pixel_size is not None and args.pixel_size <= 0:
        raise ValueError("--pixel-size must be greater than zero")

    if args.box_size is not None and args.pixel_size is None:
        raise ValueError("--box-size requires --pixel-size")

    if args.box_size is not None and args.box_size <= 0:
        raise ValueError("--box-size must be greater than zero")

    if args.resolution_min <= 0 or args.resolution_max <= 0:
        raise ValueError("Resolution limits must be greater than zero")

    if args.resolution_min >= args.resolution_max:
        raise ValueError("--resolution-min should be smaller than --resolution-max")

    if args.defocus_min <= 0 or args.defocus_max <= 0:
        raise ValueError("Defocus limits must be greater than zero")

    if args.defocus_min >= args.defocus_max:
        raise ValueError("--defocus-min should be smaller than --defocus-max")

    D = args.diameter
    L = electron_wavelength(args.voltage)

    defocus_um = np.linspace(args.defocus_min, args.defocus_max, 400)
    resolution = np.linspace(args.resolution_min, args.resolution_max, 400)

    DEF_UM, RES = np.meshgrid(defocus_um, resolution)
    DEF_A = DEF_UM * 1e4

    B_A = optimal_box_size_angstrom(
        particle_diameter=D,
        wavelength=L,
        defocus=DEF_A,
        resolution=RES,
    )

    if args.pixel_size is not None:
        B_plot = B_A / args.pixel_size
        colorbar_label = "Optimal box size B (pixels)"
        title_units = f"B plotted in pixels, pixel size = {args.pixel_size:.3f} Å/pixel"

        contour_levels = choose_contour_levels(
            B_plot,
            max_contours=args.max_contours,
            trim_fraction=args.trim_fraction,
        )

        contour_label_fmt = lambda x: f"{int(round(x))} px"

    else:
        B_plot = B_A
        colorbar_label = "Optimal box size B (Å)"
        title_units = "B plotted in Å"

        vmin = B_plot.min()
        vmax = B_plot.max()
        span = vmax - vmin

        contour_levels = np.linspace(
            vmin + args.trim_fraction * span,
            vmax - args.trim_fraction * span,
            args.max_contours,
        )

        contour_label_fmt = "%.0f Å"

    fig, ax = plt.subplots(figsize=(8, 6))

    filled = ax.contourf(
        DEF_UM,
        RES,
        B_plot,
        levels=50,
        cmap="viridis",
    )

    cbar = fig.colorbar(filled, ax=ax)
    cbar.set_label(colorbar_label)

    legend_handles = []

    if args.box_size is not None:
        alias_mask = ctf_aliasing_mask(
            wavelength=L,
            defocus_angstrom=DEF_A,
            resolution=RES,
            box_size_px=args.box_size,
            pixel_size=args.pixel_size,
        )

        if np.any(alias_mask):
            ax.contourf(
                DEF_UM,
                RES,
                alias_mask.astype(float),
                levels=[0.5, 1.5],
                colors=[args.alias_color],
                alpha=args.alias_alpha,
            )

            ax.contour(
                DEF_UM,
                RES,
                alias_mask.astype(float),
                levels=[0.5],
                colors=args.alias_color,
                linewidths=1.4,
                linestyles="--",
            )

            legend_handles.append(
                Patch(
                    facecolor=args.alias_color,
                    edgecolor=args.alias_color,
                    alpha=args.alias_alpha,
                    label=f"CTF aliasing risk, box = {args.box_size:.0f} px",
                )
            )

    lines = ax.contour(
        DEF_UM,
        RES,
        B_plot,
        levels=contour_levels,
        colors=args.line_color,
        linewidths=1.2,
    )

    labels = ax.clabel(
        lines,
        inline=True,
        fontsize=9,
        fmt=contour_label_fmt,
        colors=args.line_color,
    )

    for label in labels:
        label.set_bbox({
            "facecolor": "black",
            "edgecolor": "none",
            "alpha": 0.45,
            "pad": 1.5,
        })

    ax.set_xlabel("Defocus ΔF (µm)")
    ax.set_ylabel("Target resolution d (Å)")

    ax.set_title(
        f"Optimal cryoEM box size\n"
        f"D = {D:.0f} Å, voltage = {args.voltage:.0f} kV, λ = {L:.4f} Å\n"
        f"{title_units}"
    )

    ax.invert_yaxis()

    if legend_handles:
        ax.legend(
            handles=legend_handles,
            loc="upper center",
            bbox_to_anchor=(0.5, -0.14),
            framealpha=0.85,
            ncol=1,
        )

    fig.tight_layout(rect=[0, 0.06, 1, 1])
    fig.savefig(args.output, dpi=args.dpi)
    plt.show()

    print(f"Saved plot to: {args.output}")
    print(f"Electron wavelength used: {L:.5f} Å")
    print(f"Box size range: {B_A.min():.1f}-{B_A.max():.1f} Å")

    if args.pixel_size is not None:
        B_px = B_A / args.pixel_size
        print(f"Pixel size: {args.pixel_size:.3f} Å/pixel")
        print(f"Box size range: {B_px.min():.1f}-{B_px.max():.1f} pixels")

    if args.box_size is not None:
        print(f"CTF aliasing checked for extraction box size: {args.box_size:.0f} px")

    print("Box-size contours shown:")
    print(", ".join(f"{x:.0f}" for x in contour_levels))


if __name__ == "__main__":
    main()
