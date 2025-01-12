from enum import Enum

class Status(Enum):
    NONE: "No status"
    IN_PROGRESS = "In progress"
    IN_REVISION = "In revision"
    COMPLETED = "Completed"