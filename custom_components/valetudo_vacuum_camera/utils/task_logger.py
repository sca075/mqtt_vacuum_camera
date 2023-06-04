import logging

class TaskLogger(logging):

    task_counter = 0

    def log(self, level, msg, *args, **kwargs):
        TaskLogger.task_counter += 1
        task_msg = f"Task: {TaskLogger.task_counter}, {msg}"
        super().log(level, task_msg, *args, **kwargs)





