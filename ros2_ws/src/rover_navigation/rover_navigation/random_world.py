import argparse
import math
import random
import xml.etree.ElementTree as ET
from pathlib import Path


PATROL_POINTS = [(0.0, 0.0), (0.0, -1.5), (1.8, -1.5), (1.8, 1.5), (0.0, 1.5)]


def sample_obstacles(seed, count):
    if count < 0:
        raise ValueError("count must not be negative")
    rng = random.Random(seed)
    obstacles = []
    attempts = 0
    while len(obstacles) < count and attempts < count * 100 + 1:
        attempts += 1
        x, y = rng.uniform(-2.35, 2.35), rng.uniform(-2.35, 2.35)
        radius = rng.uniform(0.12, 0.24)
        if any(math.hypot(x - px, y - py) < radius + 0.48 for px, py in PATROL_POINTS):
            continue
        if any(math.hypot(x - ox, y - oy) < radius + other + 0.18 for ox, oy, other in obstacles):
            continue
        obstacles.append((x, y, radius))
    if len(obstacles) != count:
        raise RuntimeError("could not place requested obstacles without blocking patrol points")
    return obstacles


def write_world(template, output, seed, count):
    tree = ET.parse(template)
    world = tree.getroot().find("world")
    if world is None:
        raise ValueError("template has no SDF world")
    for index, (x, y, radius) in enumerate(sample_obstacles(seed, count)):
        model = ET.SubElement(world, "model", {"name": f"random_obstacle_{index}"})
        ET.SubElement(model, "static").text = "true"
        ET.SubElement(model, "pose").text = f"{x:.6f} {y:.6f} 0.35 0 0 0"
        link = ET.SubElement(model, "link", {"name": "link"})
        for tag in ("collision", "visual"):
            item = ET.SubElement(link, tag, {"name": tag})
            geometry = ET.SubElement(item, "geometry")
            cylinder = ET.SubElement(geometry, "cylinder")
            ET.SubElement(cylinder, "radius").text = f"{radius:.6f}"
            ET.SubElement(cylinder, "length").text = "0.70"
    ET.indent(tree, space="  ")
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    tree.write(output, encoding="unicode", xml_declaration=True)


def main(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("template")
    parser.add_argument("output")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--count", type=int, default=8)
    options = parser.parse_args(args)
    write_world(options.template, options.output, options.seed, options.count)
    print(f"Generated {options.count} obstacles with seed {options.seed}: {options.output}")
