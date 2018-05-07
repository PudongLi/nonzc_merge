import os
import re
import sys
import logging
# coding: utf-8


class ZkRedo:

    """
    检查redo信息
    """
    def __init__(self, redo_info, process_id, input_dir, output_dir, bak_path):
        self.redo_info = redo_info
        self.process_id = process_id
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.bak_path = bak_path

    def read_redo(self):
        filename_pool_str = ""

        redo_info_list = self.redo_info.split(";")
        logging.info("test redo info:%s" % redo_info_list)
        for info in redo_info_list:
            if info.startswith("filenamepool"):
                filename_pool_str = info.replace("filenamepool:", "").strip()
        step = 0
        if "begin" in redo_info_list:
            step = 1
        if "end" in redo_info_list:
            step = 2
        return filename_pool_str, step

    def move_pickfile(self, remove=False):
        """
        :param remove:
        """
        output_temp = self.output_dir + "/" + self.process_id
        if remove:
            # 将已经合并出的文件删掉
            files = os.listdir(output_temp)
            if not files:
                return
            for file in files:
                if not os.path.isfile(file):
                    continue
                try:
                    file_path = output_temp + "/" + file
                    os.remove(file_path)
                    logging.info("redo work:delete file success :%s " % file_path)
                except Exception as e:
                    logging.error("redo work:delete file failed, err:%s" % e)
                    sys.exit()
            return

        ofn_list = os.listdir(output_temp)
        if not ofn_list:
            return
        for ofn in ofn_list:
            file_path = output_temp + "/" + ofn
            if not os.path.isfile(file_path):
                continue
            try:
                new_path = self.output_dir + "/" + ofn
                os.rename(file_path, new_path)
                logging.info("redo work:move file success,%s to %s" % (file_path, new_path))
            except Exception as e:
                logging.error("redo work:move file failed, err:%s" % e)
                sys.exit()
        input_temp = self.input_dir + "/" + self.process_id
        ifn_list = os.listdir(input_temp)
        if not ifn_list:
            return
        for ifn in ifn_list:
            file_path = input_temp + "/" + ifn
            if not os.path.isfile(file_path):
                continue
            try:
                new_path = self.bak_path + "/" + ifn
                os.rename(file_path, new_path)
                logging.info("redo work:move file success,%s to %s" % (file_path, new_path))
            except Exception as e:
                logging.error("redo work:move file failed, err:%s" % e)
                sys.exit()
        return

    def do_task(self):
        filename_pool_str, action_step = self.read_redo()
        if action_step == 1:
            self.move_pickfile(True)
            return filename_pool_str
        elif action_step == 2:
            self.move_pickfile()
            return ""
        elif action_step == 0:
            return filename_pool_str
