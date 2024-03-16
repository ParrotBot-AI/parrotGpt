from pydantic import BaseModel


# ================================== Tofel Study ===========================#
class Essay(BaseModel):
    prompt: str
    content: str
    gradeType: str


class Speak(BaseModel):
    prompt: str
    audioLink: str
    gradeType: str


# ================================== Vocal Learning ===========================#
class VocabList(BaseModel):
    vocab: dict


# ================================== AI Assistant ===========================#
class ChatbotMessage(BaseModel):
    queryType: str
    chatbotQuery: str
    passage: str
    mcq: str
