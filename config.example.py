AccessKeyId = ""
AccessKeySecret = ""
OssEndpoint = "https://oss-cn-hangzhou.aliyuncs.com"
CMKID = ""
KMSRegion = ""
bucket_name = ""
storage_class = "IA" # Object的存储类型，取值：Standard、IA、Archive和ColdArchive

local_bace_dir = "/mnt/"  # 本地工作目录（绝对路径, eg：/mnt/）
remote_bace_dir = "nas-backup/"
backup_dirs = ["personal/", "www/nextcloud/data/"]  # 备份目录（相对于local_bace_dir, eg:data/）
backup_exclude = ('personal/path/to/exclude',)  # 相对路径，将会在扫描本地目录是进行前缀匹配，如果只有一个参数是请保留一个逗号以确保为tuple类型
temp_dir = "/tmp/oss-sync/"

LogFile = "/root/oss-sync.log"
LogFormat = "%(asctime)s - [%(levelname)s]: %(message)s"

# 在计算文件哈希值时允许一次性打开的最大文件大小(MB)，提高此参数可以加快大文件的计算速度，但是会增加内存消耗
MaxMemoryUsageAllow = (1024 * 1024) * 1024
