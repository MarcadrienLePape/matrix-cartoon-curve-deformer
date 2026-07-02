# Cartoon Curve Deformer for Maya

A robust, production‑ready tool for building **cartoon‑style squash‑and‑stretch curve deformers** in Autodesk Maya.  
It creates a hierarchy of driver and bind joints driven by a primary curve, with an optional secondary curve sharing endpoints – perfect for facial rigging, limbs, and stylized animation.

![alt text](https://i.imgur.com/ViYbMcu.png)

---

## Features

- **Two‑stage deformation** – *LO* (low‑resolution) and *MID* (medium‑resolution) driver curves.
- **Fully automated setup** – creates joints, skin clusters, aim constraints, and point‑on‑curve networks.
- **Flexible parameters** – choose 2, 4 or 6 mid‑drivers and 3, 5, 7 or 9 bind joints.
- **Shared endpoints** – optionally build a second curve that shares the first curve’s start/end LO joints, enabling seamless blending between two curves.
- **Color‑coded joints** for easy identification:
  - 🔴 LO drivers (red)
  - 🟡 MID drivers (orange)
  - 🔵 Center joints (blue)
  - 🟡 Bind joints (White)
- **Clean UI** – intuitive window with selection buttons and live feedback.

---

## How It Works

1. **LO Curve** – rebuilt with 3 spans (cubic). Three LO driver joints are placed at the start, middle, and end. The LO curve is skinned to these joints.
2. **MID Curve** – duplicated and rebuilt with 6 spans. MID driver joints (2, 4 or 6) are placed at specific parameters along the *LO* curve (so they follow the LO deformation). The MID curve is skinned to all LO + MID joints.
3. **Bind Joints** – placed along the MID curve according to the chosen count. Each bind joint is:
   - Aimed at a target group that follows the MID curve (position + orientation via tangent/normal).
   - Directly constrained (parent constraint) to that target, ensuring **exact position and rotation** – no offsets, even after the center joint rotates.
   - Ready to be used as the final deformation joints for your mesh.

The whole system is parented under a clean group hierarchy, making it easy to move or scale.

---

## Installation

1. Copy the entire script into a Python file, e.g., `cartoon_curve_deformer.py`.
2. Place it in your Maya scripts folder (e.g., `~/Documents/maya/scripts/`).
3. In Maya, run the following Python code:

```python
import cartoon_curve_deformer
cartoon_curve_deformer.show_ui()
```

You can also assign this to a shelf button for quick access.

---

## Using the UI

1. **First Curve** – select a NURBS curve transform in the viewport and click *Select*. This curve will be rebuilt (you can use any curve, it will be modified).
2. **Second Curve (optional)** – enable the checkbox and select another curve. This curve will share the start/end LO joints of the first curve, allowing you to blend between two shapes.
3. **Center Node** – select a locator, joint, or group that defines the “root” aim point for the bind joints.
4. **Deformer Settings** – choose the number of MID drivers and Bind joints.
5. Click **BUILD**.

After a successful build, you’ll see a confirmation message. The newly created hierarchy is placed in the scene under a group named `<curve>_GRP`.

---

## Parameters Explained

| Parameter | Description |
|-----------|-------------|
| **First Curve** | The primary NURBS curve. It will be rebuilt to 3 spans. |
| **Second Curve** | Optional. When enabled, the second curve is rebuilt to 6 spans and shares the first curve’s start/end joints. Useful for asymmetrical deformations (e.g., mouth corners). |
| **Center Node** | Any transform that defines the “look‑at” point for the bind joints. The aim matrix uses this as the input matrix. |
| **Mid Deformers** | Number of mid‑driver joints (2, 4, or 6). They are placed at specific parameters along the LO curve (see the `MID_PARAMS` table in the script). |
| **Bind Joints** | Number of final output joints (3, 5, 7, or 9). They are evenly distributed along the MID curve. |

---

## Script Architecture

The script is split into:

- **Constants** – colors, span counts, and the mid‑driver parameter table.
- **Low‑level helpers** – curve rebuilding, point baking, orientation networks, and joint creation.
- **Core build function** – `build_curve_system()` that does the heavy lifting.
- **UI** – a clean Maya window built with `cmds`.

All functions are self‑contained and can be imported for batch processing.

---

## Notes & Tips

- The LO and MID curves are rebuilt with **`rebuildCurve`** (uniform, cubic, with 3/6 spans). The original curve is modified.
- The mid‑driver parameters are hard‑coded for even distribution; you can adjust the `MID_PARAMS` dictionary to customise positions.
- The bind joints are **parent‑constrained** directly to their target groups – this ensures they remain perfectly aligned even after the center joint rotates. No offset drift!
- The skin clusters use **default weight normalisation** – you can further paint weights as needed.
- If you use a second curve, ensure both curves have the same start/end points in world space (they will be shared, so they should align).

---

## Requirements

- Autodesk Maya (tested on 2018+)
- Python 2.7 or 3.x (Maya’s built‑in interpreter)

---

## License

This project is licensed under the **MIT License** – feel free to use, modify, and distribute it. Attribution is appreciated but not required.

---

## Author & Contributions

Created by [Marc-adrien LE PAPE].  
If you find bugs or have feature requests, please open an issue or submit a pull request on GitHub.

---

**Happy rigging!** 🎬
