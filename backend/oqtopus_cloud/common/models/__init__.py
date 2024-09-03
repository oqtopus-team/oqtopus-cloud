# Don't erase this definition, it is used to import all models in the api.models package
# https://stackoverflow.com/questions/7478403/sqlalchemy-classes-across-files
# if table has foreign key, it should be imported in the same file
__all__ = ["Device", "Task", "Base", "Result"]
from oqtopus_cloud.common.models.base import Base
from oqtopus_cloud.common.models.device import Device
from oqtopus_cloud.common.models.result import Result
from oqtopus_cloud.common.models.task import Task
