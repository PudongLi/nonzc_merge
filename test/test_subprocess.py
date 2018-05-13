#!/usr/bin/env python3

# encoding: utf-8

"""

    @author: lipd

    @file: test_subprocess.py

    @time: 2018/5/7 17:26

    @desc:

"""
import subprocess
opt_file = "f:/test_subprocess.txt"

out = subprocess.Popen(["python", "./test_read.py ", "-c", opt_file], stdout=subprocess.PIPE)
