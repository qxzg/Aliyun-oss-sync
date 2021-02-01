AccessKeyId = ""
AccessKeySecret = ""
OssEndpoint = ""
CMKID = ""
KMSRegion = ""
bucket_name = ""

local_bace_dir = "/mnt/"  # 本地工作目录（绝对路径, eg：/mnt/）
remote_bace_dir = "nas-backup/"
backup_dirs = ["personal/", "www/nextcloud/data/"]  # 备份目录（相对于local_bace_dir, eg:data/）

temp_dir = "/tmp/oss-sync/"

LogFile = "/root/oss-sync.log"
LogFormat = "%(asctime)s - [%(levelname)s]: %(message)s"