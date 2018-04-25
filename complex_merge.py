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
from check_redo import CheckRedo
from flow import Flow

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
process_id = zoo.get_node(process_path)
pl.set_log(log_path, process_id)
line_limit = cfg["common"]["line_limit"]
input_path = cfg["common"]["inputdir"]
output_path = cfg["common"]["destdir"]
redo_path = cfg["common"]["redopath"]
batch_size = cfg["common"]["batchsize"]
bak_path = cfg["common"]["bakpath"]
filename_part = cfg["rule"]["filenamepart"]

my_flow = Flow(process_id, line_limit, input_path, output_path, redo_path, batch_size, bak_path, filename_header)
redo_file = redo_path + "/" + "merge." + process_id + ".redo"
check_redo = CheckRedo(redo_file, process_id, config.output_dirs)
recover, zk_seq, filename = check_redo.do_task()
if recover == 1:
    logging.info('redo:recover=1,Revert...')
    filename = filename.strip(os.linesep)
    file_date, prov, zk_seq = filename.split(".")
    file_date = re.sub("[A-Za-z.]", "", file_date)
    my_flow.work(file_date, prov, zk_seq, filename_part)
while 1:
    current_time = datetime.datetime.now().strftime('%Y%m%d-%H-%M-%S')
    merge_date, hh, mi, ss = current_time.split('-')
    # 获取当前系统序号
    sequence = (int(hh) * 3600 + int(mi) * 60 + int(ss)) / merge_interval - 1
    sequence = '%03d' % int(sequence)
    sys_sequence = merge_date + str(sequence)
    logging.info('get system sequence:%s' % sys_sequence)
    file_date, prov, zk_seq = zoo.zk_get_merge_fn(sys_sequence, zk_filenamepool)
    # logging.info("get zookeeper file date:%s, prov:%s, sequence:%s " % (file_date, prov, zk_seq))
    if zk_seq == "":
        # zk_seq > cur_seq，未到合并时间点
        time.sleep(20)
        continue
    else:
        logging.info("match expr:%s" % (match_expr + prov))
        my_flow.get_file(match_expr + prov)
        my_flow.work(file_date, prov, zk_seq, filename_part)
        logging.info("work end")
        time.sleep(1)
