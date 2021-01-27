import yaml


class Config:
    def __init__(self, config_file_path):
        # Load config file
        with open(config_file_path, "r") as stream:
            self._config = yaml.load(stream, Loader=yaml.FullLoader)

        # Define colors to be used internally through the app, and also externally if wanted
        self.colors = {
            "green": (0, 128, 0),
            "white": (255, 255, 255),
            "olive": (0, 128, 128),
            "black": (0, 0, 0),
            "navy": (128, 0, 0),
            "red": (0, 0, 255),
            "pink": (128, 128, 255),
            "maroon": (0, 0, 128),
            "grey": (128, 128, 128),
            "purple": (128, 0, 128),
            "yellow": (0, 255, 255),
            "lime": (0, 255, 0),
            "fuchsia": (255, 0, 255),
            "aqua": (255, 255, 0),
            "blue": (255, 0, 0),
            "teal": (128, 128, 0),
            "silver": (192, 192, 192),
        }

    def __getitem__(self, name):
        return self._config[name]
