from pydantic import BaseModel


# ================================== Toefl Study ===========================#
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
    toeflType: str
    queryType: str
    chatbotQuery: str
    mainContent: str
    mcq: str
    problemMethod: str
