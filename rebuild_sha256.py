# -*- coding: utf-8 -*-
import json
import time

import oss2

import config
from oss_sync_libs import sct_push, OssOperation

bucket = oss2.Bucket(oss2.Auth(config.OSSAccessKeyId, config.OSSAccessKeySecret), 'https://' + config.OssEndpoint, config.bucket_name)
rebuild_file = 'sha256-rebuild.json'

def get_remote_sha256(obj):
    global bucket
    while True:
        try:
            object_meta = bucket.head_object(obj).headers
            break
        except:
            print('retrying on file "%s"' % obj)
            time.sleep(15)
    if 'x-oss-meta-sha256' in object_meta:
        return object_meta['x-oss-meta-sha256']
    else:
        return False


def check_diff():
    with open(rebuild_file, 'r') as FOBJ:
        new_sha = json.load(FOBJ)
    with open('sha256-old.json', 'r') as FOBJ:
        old_sha = json.load(FOBJ)

    dif = new_sha.keys() - old_sha.keys()
    with open('sha256.diff', 'w', encoding='utf-8') as FOBJ:
        for i in iter(dif):
            FOBJ.write(i + '\n')


if __name__ == '__main__':
    sha256_to_files = {}
    err_files = []
    r_oss = OssOperation()
    for obj in oss2.ObjectIteratorV2(bucket, prefix=config.remote_base_dir):
        obj = obj.key
        if obj[-1] == '/':  # 判断obj为文件夹。
            continue
        sha256 = get_remote_sha256(obj)
        if not sha256:
            err_files.append(obj)
        else:
            sha256_to_files[obj[len(config.remote_base_dir):]] = sha256
    with open(rebuild_file, 'w') as fobj:
        json.dump(sha256_to_files, fobj)
    r_oss.encrypt_and_upload_files(
        rebuild_file,
        "index/%s.json" % config.remote_base_dir[:-1],
        compare_sha256_before_uploading=True,
        storage_class='Standard'
    )
    if len(err_files) > 0:
        print("[rebuild-sha256]重建完成，OSS中有 %d 个Object的Header中不存在sha256，分别是：" % len(err_files))
        print(err_files)
    print("[rebuild-sha256]记录总数 %d 条" % len(sha256_to_files))
    if config.SCT_Send_Key:
        sct_push("[rebuild-sha256]重建完成", "#### sha256.json已重建完成，请登录服务器检查")
