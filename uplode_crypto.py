# -*- coding: utf-8 -*-
# 客户端加密文档：https://help.aliyun.com/document_detail/74371.html
# 断点续传文档：https://help.aliyun.com/document_detail/88433.html
import os
import sqlite3
import oss2
import hashlib
from oss2.crypto import AliKMSProvider
import hashlib
import config
from scan_files import Calculate_File_sha256

auth = oss2.Auth(config.AccessKeyId, config.AccessKeySecret)
kms_provider = AliKMSProvider(config.AccessKeyId, config.AccessKeySecret, config.KMSRegion, config.CMKID)
bucket = oss2.CryptoBucket(auth, config.OssEndpoint, config.bucket_name, crypto_provider=kms_provider)

uplode_file = "oss-sync.zip"
download_filename = 'download.zip'


def Uplode_File_Encrypted(uplode_file):
    org_file_sha256 = Calculate_File_sha256(uplode_file)  # TODO 从json获取文件sha256
    oss2.resumable_upload(
        bucket, uplode_file, uplode_file,
        # store=oss2.ResumableStore(root='/tmp'),
        multipart_threshold=1024*1024*50,
        part_size=1024*1024*50,
        num_threads=4,
        headers={
            "content-length": str(os.path.getsize(uplode_file)),
            "x-oss-server-side-encryption": "KMS",
            "x-oss-storage-class": "IA",
            "x-oss-meta-sha256": org_file_sha256
        }
    )


def Verify_Remote_File_Integrity(remote_file):
    result = bucket.get_object(remote_file)
    sha256 = hashlib.sha256()
    for chunk in result:
        sha256.update(chunk)
    print(result.headers)
    if sha256.hexdigest() == result.headers['x-oss-meta-sha256']:
        print("校验通过")
    else:
        print("数据不匹配")


if __name__ == "__main__":
    pass
    #Uplode_File_Encrypted(uplode_file)
    # 下载OSS文件到本地文件。
    #result = bucket.get_object_to_file(uplode_file, download_filename)
