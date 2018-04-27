# coding: utf-8
import time
import logging
import datetime
import sys
import os
import getopt
import re
from config import Config
from lib.nframe import PublicLib
from zookeeper import Zookeeper
from flow import Flow
from zk_redo import ZkRedo

pl = PublicLib()
config_file = ''

# 获取用户传入的参数
try:
    opts, args = getopt.getopt(sys.argv[1:], 'c')
    opt = opts[0][0]
    if opt == '-c':
        config_file = args[0]
    else:
        print('-c:  configfile')
        sys.exit()
except getopt.GetoptError as e:
    print(e)
    sys.exit()
if not os.path.isfile(config_file):
    print("config file :%s not exsit" % config_file)
    sys.exit()
# 创建配置文件实例,获取配置文件内容
config = Config(config_file)
cfg = config.get_config()
match_expr = cfg["rule"]["input_rule_exp"]
log_path = cfg["common"]["logpath"]
if not os.path.exists(log_path):
    logging.info("logpath:%s not exist" % log_path)
    sys.exit()

filename_header = cfg["rule"]["filenameheader"]
merge_interval = int(cfg["common"]["mergeinterval"])
process_path = cfg["zookeeper"]["processpath"]
zk_filenamepool = cfg["zookeeper"]["filenamepool"]
MAX_MERGE_FILE_SEQUENCE = 86400 / merge_interval - 1
zk_host_list = cfg["zookeeper"]["zklist"]

# 创建zookeeper实例
zoo = Zookeeper(zk_host_list, MAX_MERGE_FILE_SEQUENCE)
work_node = zoo.get_node(process_path)
process_id = ''.join(work_node.split('_')[1:])
pl.set_log(log_path, process_id)
# ------------------------------------
line_limit = cfg["common"]["line_limit"]
input_path = cfg["common"]["inputdir"]
output_path = cfg["common"]["destdir"]
redo_path = cfg["common"]["redopath"]
batch_size = cfg["common"]["batchsize"]
bak_path = cfg["common"]["bakpath"]
filename_part = cfg["rule"]["filenamepart"]
# ------------------------------------
redo_node = process_path + "/" + work_node + "/" + "redo"
redo_node_flag = zoo.check_exists(redo_node)
my_flow = Flow(process_id, line_limit, input_path, output_path, redo_path, batch_size, bak_path, filename_header,
               zoo, redo_node)
recover = 0

if redo_node_flag is not None:
    redo_info, stat = zoo.get_node_value(redo_node)
    if redo_info is not None:
        bak_path = cfg["common"]["bakpath"]
        input_dir = cfg["common"]["inputdir"]
        output_dirs = config.output_dirs
        zk_redo = ZkRedo(redo_info, process_id, input_dir, output_dirs, bak_path)
        recover, filename_pool_str = zk_redo.do_task()
        file_date, prov, zk_seq = filename_pool_str.split(",")
        my_flow.work(file_date, prov, zk_seq, filename_part)
# ------------------------------------

# redo_file = redo_path + "/" + "merge." + process_id + ".redo"
# check_redo = CheckRedo(redo_file, process_id, config.output_dirs)
# recover, zk_seq, filename = check_redo.do_task()

while 1:
    redo_info = []
    current_time = datetime.datetime.now().strftime('%Y%m%d-%H-%M-%S')
    merge_date, hh, mi, ss = current_time.split('-')
    # 获取当前系统序号
    sequence = (int(hh) * 3600 + int(mi) * 60 + int(ss)) / merge_interval - 1
    sequence = '%03d' % int(sequence)
    sys_sequence = merge_date + str(sequence)
    logging.info('get system sequence:%s' % sys_sequence)
    file_date, prov, zk_seq = zoo.zk_get_merge_fn(sys_sequence, zk_filenamepool)
    if zk_seq == "":
        # zk_seq > cur_seq，未到合并时间点
        time.sleep(20)
        continue
    else:
        filename_pool = ",".join([file_date, prov, zk_seq])
        redo_info.append("filenamepool:" + filename_pool)
        zoo.create_node(redo_node)
        zoo.set_node_value(redo_node, ";".join(redo_info).encode("utf-8"))
        logging.info("match expr:%s" % (match_expr + prov))
        my_flow.get_file(match_expr + prov)
        my_flow.work(file_date, prov, zk_seq, filename_part)
        logging.info("work end")
        time.sleep(1)
