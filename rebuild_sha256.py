# -*- coding: utf-8 -*-
import hashlib
import json
import logging
import os
import sys
import time

import oss2

import config
from oss_sync_libs import SCT_Push

bucket = oss2.Bucket(oss2.Auth(config.OSSAccessKeyId, config.OSSAccessKeySecret), 'https://' + config.OssEndpoint, config.bucket_name)
rebuild_file = 'sha256-rebuild.json'


def Get_Remote_sha256(obj):
    global bucket
    while True:
        try:
            objectmeta = bucket.head_object(obj).headers
            break
        except:
            print('retrying on file "%s"' % (obj))
            time.sleep(15)
    if 'x-oss-meta-sha256' in objectmeta:
        return objectmeta['x-oss-meta-sha256']
    else:
        return False


def check_diff():
    with open(rebuild_file, 'r') as fobj:
        nsha = json.load(fobj)
    with open('sha256-old.json', 'r') as fobj:
        osha = json.load(fobj)

    dif = nsha.keys() - osha.keys()
    with open('sha256.diff', 'w', encoding='utf-8') as fobj:
        for i in iter(dif):
            fobj.write(i + '\n')


if __name__ == '__main__':
    sha256_to_files = {}
    err_files = []
    for obj in oss2.ObjectIteratorV2(bucket, prefix=config.remote_bace_dir):
        obj = obj.key
        if obj[-1] == '/':  # 判断obj为文件夹。
            continue
        sha256 = Get_Remote_sha256(obj)
        if sha256 == False:
            err_files.append(obj)
        else:
            sha256_to_files[obj[11:]] = sha256
    with open(rebuild_file, 'w') as fobj:
        json.dump(sha256_to_files, fobj)
    print(err_files)
    print("无sha256的文件总数：" + str(len(err_files)))
    SCT_Push("[rebuild-sha256]重建完成", "#### sha256.json已重建完成，请登录服务器检查")
