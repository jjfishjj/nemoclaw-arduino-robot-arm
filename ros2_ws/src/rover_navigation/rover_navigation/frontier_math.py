from collections import deque


def frontier_cells(data, width, height):
    if width <= 0 or height <= 0 or len(data) != width * height:
        raise ValueError("occupancy grid dimensions do not match data")
    result = set()
    for y in range(1, height - 1):
        for x in range(1, width - 1):
            index = y * width + x
            if data[index] != -1:
                continue
            neighbors = (
                data[index - 1], data[index + 1],
                data[index - width], data[index + width],
            )
            if any(value == 0 for value in neighbors):
                result.add((x, y))
    return result


def cluster_frontiers(cells, minimum_size=5):
    if minimum_size <= 0:
        raise ValueError("minimum_size must be positive")
    remaining = set(cells)
    clusters = []
    while remaining:
        seed = remaining.pop()
        queue = deque([seed])
        cluster = [seed]
        while queue:
            x, y = queue.popleft()
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    candidate = (x + dx, y + dy)
                    if candidate in remaining:
                        remaining.remove(candidate)
                        queue.append(candidate)
                        cluster.append(candidate)
        if len(cluster) >= minimum_size:
            cx = sum(point[0] for point in cluster) / len(cluster)
            cy = sum(point[1] for point in cluster) / len(cluster)
            clusters.append((cx, cy, len(cluster)))
    return sorted(clusters, key=lambda item: item[2], reverse=True)


def nearest_free_cell(data, width, height, x, y, search_radius=4):
    center_x, center_y = round(x), round(y)
    candidates = []
    for cell_y in range(max(0, center_y - search_radius), min(height, center_y + search_radius + 1)):
        for cell_x in range(max(0, center_x - search_radius), min(width, center_x + search_radius + 1)):
            if data[cell_y * width + cell_x] == 0:
                distance = (cell_x - x) ** 2 + (cell_y - y) ** 2
                candidates.append((distance, cell_x, cell_y))
    if not candidates:
        return None
    _, cell_x, cell_y = min(candidates)
    return cell_x, cell_y
