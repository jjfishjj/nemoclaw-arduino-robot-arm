import unittest

from rover_navigation.frontier_math import cluster_frontiers, frontier_cells, nearest_free_cell


class FrontierMathTest(unittest.TestCase):
    def test_detects_and_clusters_unknown_free_boundary(self):
        width = height = 7
        data = [-1] * (width * height)
        for y in range(2, 5):
            for x in range(2, 5):
                data[y * width + x] = 0
        cells = frontier_cells(data, width, height)
        self.assertGreaterEqual(len(cells), 8)
        clusters = cluster_frontiers(cells, minimum_size=5)
        self.assertEqual(len(clusters), 1)

    def test_goal_is_projected_to_known_free_cell(self):
        width = height = 5
        data = [-1] * 25
        data[2 * width + 2] = 0
        self.assertEqual(nearest_free_cell(data, width, height, 3, 2), (2, 2))

    def test_rejects_bad_grid(self):
        with self.assertRaises(ValueError):
            frontier_cells([0], 2, 2)


if __name__ == "__main__":
    unittest.main()
