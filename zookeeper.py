import os
import sys
import re
import logging
import datetime
from kazoo.client import KazooClient


class Zookeeper:

    def __init__(self, hosts, max_merge_seq):
        print('create a zookeeper object')
        self.zk = ""
        self.IsConn = False
        self.Hosts = hosts
        self.MAX_MERGE_FILE_SEQUENCE = max_merge_seq
        self.filename = ''
        self.pattern = ''
        self.process_path = ''

    def connect(self):
        """
        connect to zookeeper
        :return:zookeeper object
        """
        print('try connect to zookeeper')
        self.zk = KazooClient(self.Hosts)
        try:
            self.zk.start()
        except Exception as e:
            print("connect zookeeper failed, err:%s" % e)
            sys.exit()
        self.IsConn = True
        print('connect zookeeper success')
        return self.zk

    def get_node(self, node_path):
        """
        获取空闲的process_id
        :return: process_id
        """
        self.connect()
        self.process_path = node_path
        node_list = []
        if not (self.zk.exists(node_path)):
            logging.error('zookeeper process node path: %s not exist' % node_path)
            sys.exit()
        childs = self.zk.get_children(node_path)
        # len = 0
        p1 = re.compile(r"^process")
        for c in childs:
            if re.findall(p1, c):
                node_list.append(c)
        node_list = sorted(node_list)
        if len(node_list) <= 0:
            print("no process id in zookeeper process path")
            sys.exit()
        get_times = 0
        while 1:
            for node in node_list:
                lock_flag = False
                node_name = '%s/%s' % (node_path, node)
                n_child = self.zk.get_children(node_name)
                if len(n_child) > 0:
                    for n in n_child:
                        if n == 'lock':
                            lock_flag = True
                if lock_flag:
                    continue
                lock_node = "%s/%s" % (node_name, 'lock')
                self.zk.create(lock_node, ephemeral=True)
                # process_id = ''.join(node.split('_')[1:])
                print('get process_id :%s from zookeeper ' % node)
                return node
            get_times += 1
            print("no free process id in zookeeper")
            if get_times >= 3:
                print("get process id faild three times, please check zookeeper process id, exit")
                sys.exit()

    def lock(self, lock):
        """
        lock the free node
        :param lock:
        :return:
        """
        self.zk.create(lock, ephemeral=True)

    def check_exists(self, node_path):
        return self.zk.exists(node_path)

    def get_config(self, config_path, config_node):
        """
        generate config files based on node's information
        :param config_path:
        :param config_node:
        :return:
        """
        data, stat = self.zk.get(config_node)
        with open(config_path + "config.ini", 'w') as f:
            f.writelines(data.decode())

    def get_node_value(self, zk_node):
        """
        获取zookeeper的节点信息
        :param zk_node:
        :return: data:node的value
                 stat:node的状态信息
        """
        data, stat = self.zk.get(zk_node)
        return data, stat

    def set_node_value(self, zk_node, data):
        """
        设置zookeeper节点的value
        :param zk_node:
        :param data:
        :return:
        """
        return self.zk.set(zk_node, value=data)

    def delete_node(self, zk_node):
        """
        删除某一节点
        :param zk_node:
        :return:
        """
        self.zk.delete(zk_node)

    def create_node(self, node, flag=False):
        """
        创建zookeeper节点
        :param node:
        :param flag:
        :return:
        """
        try:
            self.zk.create(node, ephemeral=flag)
        except Exception as e:
            logging.info("create zookeeper node:%s failed, err:%s" % (node, e))
            print(node, e)
            return False
        return True

    def cp(self, src, dest):
        """
        copy the local file to zookeeper
        :param src:local file
        :param dest:zookeeper node
        :return:
        """
        if not os.path.isfile(src):
            print("%s: `%s': Local file does not exist" % ('cp', src))
            sys.exit()

        file_size = os.path.getsize(src)
        if file_size > 1048576:
            print("%s: `%s': Local file maximum limit of 1M" % ('cp', src))
            sys.exit()

        self.connect()
        if self.zk.exists(dest):
            print("%s: `%s': Zookeeper exists" % ('cp', dest))
            sys.exit()

        with open(src, 'rb') as file:
            data = file.read()

        self.zk.create(dest)
        self.zk.set(dest, value=data)

    def zk_get_merge_fn(self, process_path, work_node, cur_seq, filename_pool):
        """
        获取filename_pool下的序号，记录redo
        :param process_path
        :param work_node
        :param cur_seq:
        :param filename_pool:
        :return: zk_seq:
                       0: 返回0代表未到合并时间点
                       1: 返回1代表没有抢占到filename_pool
                       next_child:返回获取到的filename_pool节点
        """
        if not self.zk.exists(filename_pool):
            logging.error('no filename_pool in zookeeper')
            sys.exit()
        childs = self.zk.get_children(filename_pool)
        if not childs:
            logging.error('the zookeeper filename_pool is empty')
            sys.exit()
        # zk_fn_seq = childs[0]
        childs = sorted(childs)
        redo_info = []
        for child in childs:
            file_date, zk_seq, prov = child.split('.')
            zk_fs = ("%s%s" % (file_date, zk_seq))
            zk_fs = re.sub("[A-Za-z.]", "", zk_fs)
            if int(zk_fs) > int(cur_seq):
                logging.info('zk_seq:%s > cur_seq:%s, wait...' % (zk_fs, cur_seq))
                return 0
            zk_seq = int(zk_seq) + 1
            if zk_seq > self.MAX_MERGE_FILE_SEQUENCE:
                zk_seq = 0
                file_date = datetime.datetime.strptime(file_date, '%Y%m%d')
                next_time = file_date + datetime.timedelta(days=1)
                file_date = ('%s%02d%02d' % (next_time.year, next_time.month, next_time.day))
            zk_seq = "%03d" % zk_seq
            next_child = '%s.%s.%s' % (file_date, zk_seq, prov)
            # 创建一次事务，删除旧的序号并创建新的序号，保证原子性
            transaction_request = self.zk.transaction()
            transaction_request.delete("%s/%s" % (filename_pool, child))
            transaction_request.create("%s/%s" % (filename_pool, next_child))
            redo_seq = ",".join([file_date, zk_seq, prov])
            redo_info.append("filenamepool:" + redo_seq)
            redo_node = process_path + "/" + work_node + "/" + "redo"
            self.create_node(redo_node)
            self.set_node_value(redo_node, ";".join(redo_info).encode("utf-8"))
            results = transaction_request.commit()
            if results[0] is True and results[1] == ("%s/%s" % (filename_pool, next_child)):
                return next_child
            else:
                continue
        return 1

