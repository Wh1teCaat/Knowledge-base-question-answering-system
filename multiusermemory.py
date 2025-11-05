from langchain.memory import ConversationSummaryBufferMemory
from langchain_core.messages import SystemMessage, BaseMessage


class SummaryInjectMemory(ConversationSummaryBufferMemory):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def inject_messages(self):
        summary_text = getattr(self, "moving_summary_buffer", "") or ""
        messages = self.chat_memory.messages.copy()

        if summary_text.strip():
            summary_msg = SystemMessage(content=f"Summary: {summary_text}")
            return [summary_msg] + messages
        else:
            return messages

    @property
    def messages(self):
        return self.inject_messages()

    def add_messages(self, messages: list[BaseMessage]):
        self.chat_memory.add_messages(messages)
