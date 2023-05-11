


class Vacuum:
    def __init__(self, json_data):
        self.map_json = json_data
        self.flour_pixels = None
        self.walls_pixels = None
        self.path_pixels = None
        self.robot_pos = None
        self.robot_charger_pos = None
        self.map_data = self.parsed_data(self.map_json)

    def parsed_data(self, m_json):
        self.flour_pixels = m_json["layers"][0]["compressedPixels"]
        self.walls_pixels = m_json["layers"][1]["compressedPixels"]
        self.path_pixels = m_json["entities"][0]["points"]

