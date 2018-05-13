# coding: utf-8
import time
import logging
import datetime
import sys
import os
import getopt
from config import Config
from lib.nframe import PublicLib
from zookeeper import Zookeeper
from flow import Flow
from zk_redo import ZkRedo
from lib.receive_signal import ReceiveSignal


ReceiveSignal.receive_signal()
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
process_id = str(os.path.basename(config_file).split("_")[0])

config = Config(config_file)
cfg = config.get_config()
match_expr = cfg["rule"]["input_rule_exp"].strip()
log_path = cfg["common"]["logpath"].strip()
if log_path == "":
    print("log path is null! please check the config file,exit")
    sys.exit()
if not os.path.exists(log_path):
    logging.info("logpath:%s not exist, please check the config file,exit" % log_path)
    sys.exit()

filename_header = cfg["rule"]["filenameheader"].strip()
merge_interval = cfg["common"]["mergeinterval"].strip()
if merge_interval == "":
    print("merge interval is null, please check the config file,exit")
    sys.exit()
merge_interval = int(merge_interval)
process_path = cfg["zookeeper"]["processpath"].strip()
zk_filenamepool = cfg["zookeeper"]["filenamepool"].strip()

if process_path == "":
    print("process path is null, please check the config file,exit")
    sys.exit()
if zk_filenamepool == "":
    print("zk filenamepool is null, please check the config file,exit")
    sys.exit()

MAX_MERGE_FILE_SEQUENCE = 86400 / merge_interval - 1
zk_host_list = cfg["zookeeper"]["zklist"].strip()

if zk_host_list == "":
    print("zk host list is null! please check the config file")
    sys.exit()

# 创建zookeeper实例
zoo = Zookeeper(zk_host_list, MAX_MERGE_FILE_SEQUENCE)
zoo.connect()
# work_node = zoo.get_node(process_path)
work_node = "process_" + process_id
# process_id = ''.join(work_node.split('_')[1:])
pl.set_log(log_path, process_id)
# ------------------------------------
line_limit = cfg["common"]["line_limit"].strip()
input_path = cfg["common"]["inputdir"].strip()
output_path = cfg["common"]["destdir"].strip()
batch_size = cfg["common"]["batchsize"].strip()
bak_path = cfg["common"]["bakpath"].strip()
filename_part = cfg["rule"]["filenamepart"].strip()
# ------------------------------------
if line_limit == "":
    line_limit = 2000000
if input_path == "":
    logging.error("input path is null! please check the config file,exit")
    sys.exit()
if bak_path == "":
    logging.error("bak path is null! please check the config file,exit")
    sys.exit()
if output_path == "":
    logging.error("output path is null! please check the config file,exit")
    sys.exit()
if not os.path.exists(input_path):
    logging.error("input_path:%s not exist, please check the config file,exit" % input_path)
    sys.exit()
if not os.path.exists(bak_path):
    logging.error("bak_path:%s not exist, please check the config file,exit" % bak_path)
    sys.exit()
if not os.path.exists(output_path):
    logging.error("output_path:%s not exist, please check the config file,exit" % output_path)
    sys.exit()
# ------------------------------------
redo_node = process_path + "/" + work_node + "/" + "redo"
redo_node_flag = zoo.check_exists(redo_node)
my_flow = Flow(process_id, line_limit, input_path, output_path, batch_size, bak_path, filename_header,
               zoo, redo_node)
recover = 0

if redo_node_flag is not None:
    redo_info, stat = zoo.get_node_value(redo_node)
    redo_info = bytes.decode(redo_info)
    if redo_info is not None:
        zk_redo = ZkRedo(redo_info, process_id, input_path, output_path, bak_path)
        filename_pool_str = zk_redo.do_task()
        file_date, prov, zk_seq = filename_pool_str.split(",")
        my_flow.work(file_date, zk_seq, prov, filename_part)

while 1:
    redo_info = []
    current_time = datetime.datetime.now().strftime('%Y%m%d-%H-%M-%S')
    merge_date, hh, mi, ss = current_time.split('-')
    # 获取当前系统序号
    sequence = (int(hh) * 3600 + int(mi) * 60 + int(ss)) / merge_interval - 1
    sequence = '%03d' % int(sequence)
    sys_sequence = merge_date + str(sequence)
    logging.info('get system sequence:%s' % sys_sequence)
    filename_seq = zoo.zk_get_merge_fn(process_path, work_node, sys_sequence, zk_filenamepool)

    if filename_seq == 0:
        # zk_seq > cur_seq，未到合并时间点
        time.sleep(10)
        continue
    if filename_seq == 1:
        logging.info("get filename_pool failed, try again")
        continue
    file_date, zk_seq, prov = filename_seq.split(".")
    filename_pool = ",".join([file_date, zk_seq, prov])
    redo_info.append("filenamepool:" + filename_pool)
    # zoo.create_node(redo_node)
    # zoo.set_node_value(redo_node, ";".join(redo_info).encode("utf-8"))
    logging.info("match expr:%s" % (match_expr + prov))
    my_flow.get_file(match_expr + prov)
    my_flow.work(file_date, prov, zk_seq, filename_part)
    if ReceiveSignal.EXIT_FLAG:
        sys.exit()
