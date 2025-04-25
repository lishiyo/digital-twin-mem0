"""Import redirection file to maintain backward compatibility.

This file exists to maintain compatibility with existing code that imports from app.worker.tasks.
The actual task implementations have been moved to submodules in the app.worker.tasks directory.
"""

# Re-export tasks from file_tasks to maintain backward compatibility
from app.worker.tasks.file_tasks import process_file, process_directory

# Import any other tasks that need to be exposed at this level
from app.worker.tasks.graphiti_tasks import (
    process_chat_message_graphiti,
    process_pending_messages_graphiti,
    process_conversation_graphiti
)

# Note: Any new tasks should be added to appropriate submodules in the app/worker/tasks/ directory
