# -*- coding: utf-8 -*-
# 客户端加密文档：https://help.aliyun.com/document_detail/74371.html
# 断点续传文档：https://help.aliyun.com/document_detail/88433.html
import os
import sqlite3
import oss2
from oss2.crypto import AliKMSProvider

import config
from scan_files import Get_File_sha256

MultipartUpload_Min_Filesize = (1024 * 1024 * 1024) * 13 # 当文件大小大于该值时使用断点续传（GB）。不得大于5GB
assert MultipartUpload_Min_Filesize <= 1024 * 1024 * 1024 * 5, "断点续传启用大小必须小于5GB"


auth = oss2.Auth(config.AccessKeyId, config.AccessKeySecret)
kms_provider = AliKMSProvider(config.AccessKeyId, config.AccessKeySecret, config.KMSRegion, config.CMKID)
bucket = oss2.CryptoBucket(auth, config.OssEndpoint, config.bucket_name, crypto_provider=kms_provider)

key = 'motto.zip'
content = open(key, "rb")
filename = 'download.zip'

org_file_sha256 = Get_File_sha256(key)
# 上传文件。
bucket.put_object(
    key, content.read(),
    headers={
        "content-length": str(os.path.getsize(key)),
        "x-oss-server-side-encryption": "KMS",
        "x-oss-storage-class": "IA",
        "x-oss-meta-sha256": org_file_sha256
    }
)

# 下载OSS文件到本地内存。
result = bucket.get_object(key)
# 下载OSS文件到本地文件。
result = bucket.get_object_to_file(key, filename)
if Get_File_sha256(filename) == org_file_sha256:
    print("校验通过")
else:
    print("数据不匹配")
