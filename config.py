import os
from configparser import ConfigParser

# coding: utf-8


class Config:
    def __init__(self, filepath):
        self.configPath = ""
        self.process_input_dir = ""
        self.input_dir = ""
        self.match_expr = ""
        self.parser = ConfigParser()
        if os.path.isfile(filepath):
            self.config_file = filepath
        self.batch_size = 5
        self.output_dirs = {}

    def get_config(self):
        """
        获取配置文件信息
        :return:config
        """
        parser = ConfigParser()
        parser.read(self.config_file)
        sections = []
        config = {}
        for section in parser.sections():
            sections.append(section)
            items = {}
            for key, value in parser.items(section):
                items[key] = value
                config[section] = items
        return config
