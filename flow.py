#!/usr/bin/env python3

# encoding: utf-8

'''

@author: lipd

@file: work2

@time: 2018/4/17 16:10

@desc:

'''
import os
import re
import logging
import sys
import copy
import datetime
from redo import Redo


class Flow:
    def __init__(self, process_id, line_limit, input_path, output_path,
                 batch_size, bak_path, filename_header, zoo, redo_node):
        self.process_id = process_id
        self.fieldlen = ""
        self.line_limit = int(line_limit)
        self.input_path = input_path
        self.output_path = output_path
        self.batch_size = batch_size
        self.bak_path = bak_path
        self.filename_header = filename_header
        self.input_temp = self.input_path + "/" + self.process_id
        self.output_temp = self.output_path + "/" + self.process_id
        self.zoo = zoo
        self.redo_node = redo_node

    def work(self, file_date, prov, seq, filename_part):
        """

        :param file_date: 合并日期，用来组成输出文件名
        :param prov: 省代码，用来组成输出文件名
        :param seq: 合并序号，用来组成输出文件名
        :param filename_part: 输出文件名组成规则
        :return:
        """
        HEAD = self.filename_header
        OFN = file_date
        PROV = prov
        SPLIT = "."
        SEQ = seq
        new_filename = ""
        redo_info = []
        filename_pool = ",".join([file_date, prov, seq])
        redo_info.append("filenamepool:" + filename_pool)
        redo_info.append("begin")
        self.zoo.set_node_value(self.redo_node, ";".join(redo_info).encode("utf-8"))
        filename_part_list = filename_part.split(",")
        for part in filename_part_list:
            if part.startswith("$"):
                part = part.strip("$")
                new_filename += locals()[part]
            else:
                new_filename += part
        logging.info("new file name:%s" % new_filename)
        file_list = os.listdir(self.input_temp)
        if not os.path.exists(self.output_temp):
            os.mkdir(self.output_temp)
        new_file = open(self.output_temp + "/" + new_filename, "a")
        arrive_time = ""
        line_num = 0
        file_num = 0
        end_file_list = copy.deepcopy(file_list)
        for file in file_list:
            file_num += 1
            filename = self.input_temp + "/" + file  # os.path.join(self.input_path, file)
            file_content = []
            this_arrivetime = ""
            # 判断是否超过行数限制
            if line_num >= self.line_limit:
                logging.info("line num > line limit, move file back")
                target_file = self.input_path + "/" + file
                try:
                    os.rename(filename, target_file)
                    end_file_list.remove(file)
                    continue
                except Exception as e:
                    logging.error("move file back err:%s" % e)
                    sys.exit()
            this_file = open(filename)

            for line in this_file:
                line_list = line.split(";")
                line_list[130] = new_filename
                # line_list.index()
                this_arrivetime = line_list[134][0:8]
                file_content.append(";".join(line_list))
            # 判断此文件arrive_time与上一个文件的arrive_time是否一致，若不一致，将此文件挪回入口目录
            # this_arrivetime = file_content[0][134][0:8]
            if file_num != 1 and this_arrivetime != arrive_time:
                logging.info("there is diff arrivetime in a batch file, filename:%s, before:%s,this:%s. move back" % (file, arrive_time, this_arrivetime))
                target_file = self.input_path + "/" + file
                try:
                    this_file.close()
                    os.rename(filename, target_file)
                    logging.info('MOVE FILE:%s-->%s' % (filename, target_file))
                    end_file_list.remove(file)
                except Exception as e:
                    logging.error("MOVE FILE ERR %s" % e)
                    sys.exit()
                continue

            line_num += len(file_content)
            # 重置arrive_time
            arrive_time = this_arrivetime
            new_file.writelines(file_content)
            logging.info("write %s,len:%d" % ((self.output_temp + "/" + new_filename), (len(file_content))))
            this_file.close()
            logging.info("finish file:%s" % file)

        new_file.close()
        redo_info.append("filenamepool:" + filename_pool)
        redo_info.append("end")
        self.zoo.set_node_value(self.redo_node, ";".join(redo_info).encode("utf-8"))
        self.move_file(end_file_list, new_filename)
        self.zoo.delete_node(self.redo_node)

    def move_file(self, sourcefile_list, outputfile):
        """

        :param sourcefile_list:
        :param outputfile:
        :return:
        """
        for file in sourcefile_list:

            try:
                target_file = self.bak_path + "/" + file
                source_file = self.input_temp + "/" + file
                os.rename(source_file, target_file)
                logging.info('END: MOVE FILE:%s-->%s' % (source_file, target_file))
            except Exception as e:
                logging.error("MOVE FILE ERR %s" % e)
                sys.exit()
        source_file = self.output_temp + "/" + outputfile
        target_file = self.output_path + '/' + outputfile
        try:
            os.rename(source_file, target_file)
            logging.info('END: MOVE FILE:%s-->%s' % (source_file, target_file))
        except Exception as e:
            logging.error("MOVE FILE ERR %s" % e)
            sys.exit()
        logging.info("move end")

    def get_file(self, match_expr):
        if not os.path.exists(self.input_temp):
            os.mkdir(self.input_temp)
        file_num = 0
        file_list = os.listdir(self.input_path)
        for file in file_list:
            source_file = self.input_path + "/" + file
            if (not (os.path.exists(source_file))) or (not (os.path.isfile(source_file))):
                continue
            p1 = re.compile(match_expr)
            if re.findall(p1, file):
                new_file = self.input_temp + "/" + file
                os.rename(source_file, new_file)
                logging.info('BEGIN: MOVE %s TO %s' % (source_file, new_file))
                file_num += 1
            if file_num >= int(self.batch_size):
                break
        logging.info("get %d file" % file_num)
