# -*- coding: utf-8 -*-
import hashlib
import json
import logging
import os
import sys
import time

import oss2

import config
import oss_sync_libs

bucket = oss2.Bucket(oss2.Auth(config.OSSAccessKeyId, config.OSSAccessKeySecret), 'https://' + config.OssEndpoint, config.bucket_name)


def Get_Remote_sha256(obj):
    global bucket
    while True:
        try:
            objectmeta = bucket.head_object(obj).headers
            break
        except:
            time.sleep(15)
    if 'x-oss-meta-sha256' in objectmeta:
        return objectmeta['x-oss-meta-sha256']
    else:
        return False


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
        break
with open('sha256-rebuild.json', 'w') as fobj:
    json.dump(sha256_to_files, fobj)
print(err_files)
print("无sha256的文件总数：" + str(len(err_files)))
