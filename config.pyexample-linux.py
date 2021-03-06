OSSAccessKeyId = ""  # OSS服务用户AK
OSSAccessKeySecret = ""  # OSS服务用户SK
OssEndpoint = ""  # OSS Endpoint
bucket_name = ""  # OSS Bucket名称
default_storage_class = "Archive"  # Object的存储类型，取值：Standard、IA、Archive和ColdArchive

KMSAccessKeyId = ""  # KMS服务的用户AK
CMKID = ""  # KMS密钥ID（密钥类型必须为AES256）
KMSRegion = ""  # KMS密钥所在地域 eg: cn-shanghai

local_base_dir = "/mnt/"  # 本地工作目录（绝对路径, eg：/mnt/）
remote_base_dir = "nas-backup/"  # 上传至OSS时的路径前缀
backup_dirs = ["personal/", "www/nextcloud/data/"]  # 备份目录（相对于local_bace_dir, eg:data/）
backup_exclude = ('personal/path/to/exclude',)  # 相对路径，将会在扫描本地目录是进行前缀匹配，如果只有一个参数是请保留一个逗号以确保为tuple类型
temp_dir = "/tmp/oss-sync/"  # 临时文件位置，绝对路径
Max_Retries = 5  # 遇到网络错误时最大重试次数

LogFile = "/root/oss-sync.log"  # 日志文件位置，推荐使用绝对路径
LogLevel = "INFO"  # 日志级别，取值：DEBUG，INFO，WARNING，ERROR，CRITICAL
LogFormat = "%(asctime)s %(name)s - [%(levelname)s]: %(message)s"  # 日志输出格式

SCT_Send_Key = ""  # Server酱·Turbo推送密钥 （可选填）

# 在计算文件哈希值时允许一次性打开的最大文件大小(MB)，提高此参数可以加快大文件的计算速度，但是会增加内存消耗
MaxMemoryUsageAllow = (1024 * 1024) * 1024
