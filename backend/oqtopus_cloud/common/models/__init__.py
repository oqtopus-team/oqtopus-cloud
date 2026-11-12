# Don't erase this definition, it is used to import all models in the api.models package
# https://stackoverflow.com/questions/7478403/sqlalchemy-classes-across-files
# if table has foreign key, it should be imported in the same file
__all__ = [
    "Base",
    "Device",
    "DeviceInfoHistory",
    "Job",
    "User",
    "Announcement",
    "WhitelistUser",
]
from oqtopus_cloud.common.models.base import Base
from oqtopus_cloud.common.models.device import Device
from oqtopus_cloud.common.models.device_info_history import DeviceInfoHistory
from oqtopus_cloud.common.models.job import Job
from oqtopus_cloud.common.models.user import User
from oqtopus_cloud.common.models.announcements import Announcement
from oqtopus_cloud.common.models.whitelist_user import WhitelistUser
