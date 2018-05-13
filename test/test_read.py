#!/usr/bin/env python3

# encoding: utf-8

"""

    @author: lipd

    @file: test_read.py

    @time: 2018/4/16 9:52

    @desc:

"""
import time
import getopt
import sys
import os

try:
    opts, args = getopt.getopt(sys.argv[1:], 'c')
    opt = opts[0][0]
    if opt == '-c':
        opt_file = args[0]
    else:
        print('-c:  configfile')
        sys.exit()
except getopt.GetoptError as e:
    print(e)
    sys.exit()


file_list = ["1", "2", "3", "4"]
filename = ""
while 1:
    file = open(opt_file, "a")
    file.writelines(file_list)
    file.close()
    time.sleep(10)
