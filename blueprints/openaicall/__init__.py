from fastapi import APIRouter, Response, Request
from blueprints.openaicall.models import (
    Speak,
    Essay,
    VocabList,
    ChatbotMessage
)
from configs import (
    OPEN_AI_API_KEY,
    SPEECHSUPER_APPKEY,
    SPEECHSUPER_SECRETKEY
)
from fastapi.responses import StreamingResponse
import openai
from blueprints.openaicall.prompts import *
from nltk.tokenize import sent_tokenize
import math
import json
import time
import hashlib
import requests
import urllib.request as urllib2
from blueprints.openaicall.controller import OpenAIController
from utils.response_tools import (SuccessDataResponse, ArgumentExceptionResponse)
from utils import generate_uuid_id

openai.api_key = OPEN_AI_API_KEY
appKey = SPEECHSUPER_APPKEY
secretKey = SPEECHSUPER_SECRETKEY

router = APIRouter(
    prefix="/v1/modelapi",
    tags=["openaicall"]
)

global_state = {}


# ================================== Tofel Study ===========================#
@router.post("/writing/gradeWriting/")
async def gradeWriting(essay: Essay):
    d = {}

    # Read Request
    if essay.gradeType == "Academic Discussion":
        sys_prompt = ACADEMIC_DISCUSSION_GRADING_SYSPROMPT
    elif essay.gradeType == "Integrated Writing":
        sys_prompt = INTEGRATED_WRITING_GRADING_SYSPROMPT
    else:
        return ArgumentExceptionResponse(msg='Error: Invalid gradeType')

    content = {}
    # Add spaces between sentences as necessary
    len_content = len(essay.content) - 1
    i = 0
    while i < len_content:
        if essay.content[i] == "." and essay.content[i + 1].isupper():
            essay.content = essay.content[:i + 1] + " " + essay.content[i + 1:]
            len_content += 1
        i += 1
    # Use nltk sent_tokenize to separate sentences
    paragraph = sent_tokenize(essay.content)
    for i in range(len(paragraph)):
        content[str(i + 1)] = paragraph[i]
    user_prompt = essay.prompt + "\n\n" + json.dumps(content, indent=4)
    d.update({"Content": content})

    res, data = OpenAIController().GeneralOpenAICall(
        sys_prompt=sys_prompt,
        user_prompt=user_prompt,
        model="gpt-4-0125-preview",
        token_size=512,
        temp=1
    )
    if not res:
        return ArgumentExceptionResponse(msg=data)
    try:
        sum = 0
        for k, v in data["Grades"].items():
            sum += int(v)
        if essay.gradeType == "Academic Discussion":
            d["Overall"] = str(sum / 4)
        elif essay.gradeType == "Integrated Writing":
            d["Overall"] = str(math.floor(sum * 4 / 3) / 4)
    except Exception as e:
        return ArgumentExceptionResponse(msg=str(e))

    d.update(data)
    print(d)
    # Send Feedback Request
    if essay.gradeType == "Academic Discussion":
        sys_prompt = ACADEMIC_DISCUSSION_FEEDBACK_SYSPROMPT
    elif essay.gradeType == "Integrated Writing":
        sys_prompt = INTEGRATED_WRITING_FEEDBACK_SYSPROMPT
    else:
        return ArgumentExceptionResponse(msg='Error: Invalid gradeType')

    user_prompt += "\n\nScore:\n"
    for k, v in data["Grades"].items():
        user_prompt += k + ": " + str(v) + "\n"

    # get feedback
    res, feedback = OpenAIController().GeneralOpenAICall(
        sys_prompt=sys_prompt,
        user_prompt=user_prompt,
        model="gpt-4-0125-preview",
        token_size=4096,
        temp=1
    )
    if not res:
        return ArgumentExceptionResponse(msg=data)

    try:
        gen_feedback = ""
        for k, v in feedback["General Feedback"].items():
            gen_feedback += k + ": " + v + "\n"
        d.update({"General Feedback": gen_feedback})
    except Exception as e:
        return ArgumentExceptionResponse(msg=str(e))

    # Send Editing Request
    if essay.gradeType == "Academic Discussion":
        sys_prompt = ACADEMIC_DISCUSSION_EDITING_SYSPROMPT
    elif essay.gradeType == "Integrated Writing":
        sys_prompt = INTEGRATED_WRITING_EDITING_SYSPROMPT
    else:
        return ArgumentExceptionResponse(msg='Error: Invalid gradeType')

    user_prompt += "\n" + json.dumps(feedback, indent=4)

    # get editing
    res, edit = OpenAIController().GeneralOpenAICall(
        sys_prompt=sys_prompt,
        user_prompt=user_prompt,
        model="gpt-4-0125-preview",
        token_size=4096,
        temp=1
    )
    if not res:
        return ArgumentExceptionResponse(msg=data)

    sentence_feedback = {}
    for i in range(len(feedback["Sentence Feedback"])):
        try:
            sentence_feedback[str(i + 1)] = {
                "Feedback": feedback["Sentence Feedback"][str(i + 1)],
                "Edited": edit["Edited Version"][str(i + 1)]
            }
        except:
            pass

    d.update({"Sentence Feedback": sentence_feedback})

    # Make a mind-map
    if essay.gradeType == "Academic Discussion":
        sys_prompt = ACADEMIC_DISCUSSION_MINDMAP_SYSPROMPT
    elif essay.gradeType == "Integrated Writing":
        sys_prompt = INTEGRATED_WRITING_MINDMAP_SYSPROMPT
    else:
        return ArgumentExceptionResponse(msg='Error: Invalid gradeType')

    user_prompt = json.dumps(content, indent=4)

    # get editing
    res, mindmap = OpenAIController().GeneralOpenAICall(
        sys_prompt=sys_prompt,
        user_prompt=user_prompt,
        model="gpt-4-0125-preview",
        token_size=1024,
        temp=1
    )
    if not res:
        return ArgumentExceptionResponse(msg=data)
    d.update(mindmap)

    res, data = OpenAIController().censorOutput(d)
    if res:
        return SuccessDataResponse(data=data)
    else:
        return ArgumentExceptionResponse(msg=data)


@router.post("/speaking/gradeSpeaking/")
async def gradeSpeaking(speak: Speak):
    d = {}

    # Feed to SpeechSuper
    userId = "guest"
    timestamp = str(int(time.time()))
    url = "https://api.speechsuper.com/speak.eval.pro"
    connectStr = (appKey + timestamp + secretKey).encode("utf-8")
    connectSig = hashlib.sha1(connectStr).hexdigest()
    startStr = (appKey + timestamp + userId + secretKey).encode("utf-8")
    startSig = hashlib.sha1(startStr).hexdigest()
    params = {
        "connect": {
            "cmd": "connect",
            "param": {
                "sdk": {
                    "version": 16777472,
                    "source": 9,
                    "protocol": 2
                },
                "app": {
                    "applicationId": appKey,
                    "sig": connectSig,
                    "timestamp": timestamp
                }
            }
        },
        "start": {
            "cmd": "start",
            "param": {
                "app": {
                    "userId": "guest",
                    "applicationId": "1709716879000299",
                    "sig": startSig,
                    "timestamp": timestamp
                },
                "audio": {
                    "audioType": "mp3",
                    "channel": 1,
                    "sampleBytes": 2,
                    "sampleRate": 16000
                },
                "request": {
                    "test_type": "ielts",
                    "coreType": "speak.eval.pro"
                }

            }
        }
    }
    data = {'text': json.dumps(params)}
    headers = {"Request-Index": "0"}
    files = {"audio": urllib2.urlopen(speak.audioLink)}
    res = requests.post(url, data=data, headers=headers, files=files)
    speech_res = json.loads(res.text.encode('utf-8', 'ignore'))

    # GPT Grading
    if speak.gradeType == "Independent Speaking":
        sys_prompt = INDEPENDENT_SPEAKING_GRADING_SYSPROMPT
    elif speak.gradeType == "Integrated Writing":
        sys_prompt = INTEGRATED_WRITING_GRADING_SYSPROMPT
    else:
        return ArgumentExceptionResponse(msg='Error: Invalid gradeType')
    user_prompt = "Prompt: " + speak.prompt + "\n\nStudent Transcript: " + speech_res["result"]["transcription"]

    res, data = OpenAIController().GeneralOpenAICall(
        sys_prompt=sys_prompt,
        user_prompt=user_prompt,
        model="gpt-4-0125-preview",
        token_size=512,
        temp=1
    )
    if not res:
        return ArgumentExceptionResponse(msg=data)
    try:
        grades = data["Grades"]
        grades["Grammar"] = str(speech_res["result"]["grammar"] // 2)
        grades["Vocabulary Usage"] = str(speech_res["result"]["lexical_resource"] // 2)
        grades["Fluency"] = str(speech_res["result"]["fluency_coherence"] // 2)
        tot = math.ceil(int(grades["Content"]) + int(grades["Coherence"]) + (
                (int(grades["Grammar"]) + int(grades["Vocabulary Usage"])) / 2) + int(grades["Fluency"]))
        avg = math.floor(tot / 2) / 2
        d["Overall"] = str(avg)
        d.update({"Grades": grades})
        return SuccessDataResponse(data=d)
    except Exception as e:
        return ArgumentExceptionResponse(msg=str(e))


# ================================== AI Assistant (streaming) ===========================#
@router.post("/assistantChatbot_old/")
async def chatbotRespond(chatbotMessage: ChatbotMessage):
    sys_prompt = ASSISTANT_CHATBOT_SYSPROMPT
    user_prompt = chatbotMessage.chatbotQuery

    # Make a request to the OpenAI API
    response = openai.chat.completions.create(
        model="gpt-3.5-turbo-0125",
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt}
        ],
        max_tokens=1024,  # Change as needed
        temperature=0
    )
    return OpenAIController().censorOutput({"response": response.choices[0].message.content})


@router.post("/streaming/")
async def setup_endpoint(request: Request):
    data = await request.json()
    _uuid = generate_uuid_id()
    global_state[_uuid] = data
    return SuccessDataResponse(data={"message": "message received", "clientId": _uuid})


@router.get('/assistantChatbot/{client_id}/', status_code=200)
async def chatbotRespond(client_id: str):
    if client_id not in global_state:
        return ArgumentExceptionResponse(msg='ID not found')

    sys_prompt = ASSISTANT_CHATBOT_SYSPROMPT
    data_input = global_state.get(client_id, {})
    del global_state[client_id]
    user_prompt = data_input["chatbotQuery"]
    model = "gpt-3.5-turbo-0125"
    token_size = 1024
    temp = 0
    response = StreamingResponse(OpenAIController().OpenAiStreaming(
        sys_prompt=sys_prompt,
        user_prompt=user_prompt,
        model=model,
        token_size=token_size,
        temp=temp
    ), media_type="text/event-stream")
    return response
    # Start the OpenAI stream in a background thread


@router.get("/getVocabContent/{client_id}/", status_code=200)
async def getVocabContent(client_id: str):
    if client_id not in global_state:
        return ArgumentExceptionResponse(msg='ID not found')

    data_input = global_state.get(client_id, {})
    del global_state[client_id]
    sys_prompt = VOCAB_PASSAGE_GEN_TEST
    model = "gpt-4-0125-preview"
    token_size = 4096
    temp = 0.75
    return StreamingResponse(OpenAIController().OpenAiVocabStreaming(
        sys_prompt=sys_prompt,
        model=model,
        token_size=token_size,
        temp=temp,
        vocabs=data_input
    ), media_type="text/event-stream")


# ================================== Vocal Learning (streaming) ===========================#
"""
@router.post("/reading/getVocabContent/")
async def getVocabContent(vocablist: VocabList):
  d = {}

  start = time.time()
  counter = 1
  while(counter <= 3):
    sys_prompt = prompts.VOCAB_PASSAGE_GEN
    user_prompt = "Vocabulary List\n"
    for k, v in vocablist.vocab.items():
      user_prompt += k + " - "+ v + "\n"

    #Generate the vocabulary passage in English
    response = openai.chat.completions.create(
      model="gpt-4-0125-preview",
      messages=[
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_prompt}
      ],
      max_tokens=4096,
      temperature=0.75,
      response_format={"type": "json_object"}
    )
    passage = json.loads(response.choices[0].message.content)
    vocab_used = passage["Vocab Words Used"]

    #Correspond each vocabulary word to a sentence
    vocab_words = {}
    for word in vocablist.vocab.keys():  
      for k, v in vocab_used.items():
        if word.lower() in [x.lower() for x in v]:
          vocab_words[word] = passage["Sentences"][k]
          break
    if len(vocab_words) == 20:
      break
    else:
      counter += 1
      print(counter)
      print(len(vocab_words))

  if counter > 3:
     return {"Status": "Error"}
  d.update({"Vocab Sentences": vocab_words})

  print(time.time()-start)
  #Translate the passage into Chinese minus the vocabulary words
  sys_prompt = prompts.VOCAB_TRANSLATION_GEN
  user_prompt += "\n" + json.dumps({"Title": passage["Title"], "Sentences": passage["Sentences"]}, indent=4)
  response = openai.chat.completions.create(
    model="gpt-4-0125-preview",
    messages=[
      {"role": "system", "content": sys_prompt},
      {"role": "user", "content": user_prompt}
    ],
    max_tokens=4096,
    temperature=0.75,
    response_format={"type": "json_object"}
  )
  passage = json.loads(response.choices[0].message.content)
  d.update(passage)
  d.update({"Status": "OK"})

  return censorOutput(d)
"""


@router.post("/test/")
async def heartbeat():
    return SuccessDataResponse(data={"msg": "success"})
