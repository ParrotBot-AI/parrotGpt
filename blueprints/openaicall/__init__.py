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
# import nltk
# nltk.download('punkt')
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
from utils.redis_tools import RedisWrapper
from utils.logger_tools import get_general_logger
from utils import abspath
openai.api_key = OPEN_AI_API_KEY
appKey = SPEECHSUPER_APPKEY
secretKey = SPEECHSUPER_SECRETKEY

router = APIRouter(
    prefix="/v1/modelapi",
    tags=["openaicall"]
)

logger = get_general_logger('gpt_res', path=abspath('logs', 'web_res'))

# ================================== Toefl Study ===========================#
@router.post("/writing/gradeWriting/")
async def gradeWriting(essay: Essay):
    d = {}
    logger.info(f"API: /writing/gradeWriting/ was called")
    # Read Request
    if essay.gradeType == "Academic Discussion":
        sys_prompt = ACADEMIC_DISCUSSION_GRADING_SYSPROMPT
        format = ACADEMIC_DISCUSSION_GRADING_FORMAT
    elif essay.gradeType == "Integrated Writing":
        sys_prompt = INTEGRATED_WRITING_GRADING_SYSPROMPT
        format = INTEGRATED_WRITING_GRADING_FORMAT
    else:
        return ArgumentExceptionResponse(msg='Error: Invalid gradeType')

    new_content = []
    gpt_content = {}
    # Add spaces between sentences as necessary
    len_content = len(essay.content) - 1
    i = 0
    while i < len_content:
        if essay.content[i] == "." and essay.content[i + 1].isupper():
            essay.content = essay.content[:i + 1] + " " + essay.content[i + 1:]
            len_content += 1
        i += 1

    # Split the student's essay into paragraphs
    content = essay.content.splitlines()
    # Use nltk sent_tokenize to separate sentences
    for i in range(len(content)):
        content[i] = sent_tokenize(content[i])
    counter = 1
    # new_counter holds the object that will be returned
    # gpt_counter holds the object that gpt gets
    for i in range(len(content)):
        new_content.append({})
        for j in range(len(content[i])):
            new_content[i][str(counter)] = content[i][j]
            gpt_content[str(counter)] = content[i][j]
            counter += 1
    user_prompt = essay.prompt + "\n\n" + json.dumps(gpt_content, indent=4)
    d.update({"Content": new_content})
    res, data = OpenAIController().FormatOpenAICall(
        sys_prompt=sys_prompt,
        user_prompt=user_prompt,
        model="gpt-4-0125-preview",
        token_size=512,
        temp=1,
        format=format
    )
    if not res:
        return ArgumentExceptionResponse(msg=data)
    try:
        sum = 0
        for k, v in data["Grades"].items():
            sum += v
            data["Grades"][k] = str(v)
        if essay.gradeType == "Academic Discussion":
            d["Overall"] = str(sum / 4)
        elif essay.gradeType == "Integrated Writing":
            d["Overall"] = str(math.floor(sum * 4 / 3) / 4)
    except Exception as e:
        return ArgumentExceptionResponse(msg=str(e))

    d.update(data)
    # Send Feedback Request
    if essay.gradeType == "Academic Discussion":
        sys_prompt = ACADEMIC_DISCUSSION_FEEDBACK_SYSPROMPT
        format = ACADEMIC_DISCUSSION_FEEDBACK_FORMAT
    elif essay.gradeType == "Integrated Writing":
        sys_prompt = INTEGRATED_WRITING_FEEDBACK_SYSPROMPT
        format = INTEGRATED_WRITING_FEEDBACK_FORMAT
    else:
        return ArgumentExceptionResponse(msg='Error: Invalid gradeType')
    user_prompt += "\n\nScore:\n"
    for k, v in data["Grades"].items():
        user_prompt += k + ": " + v + "\n"

    # get feedback
    res, feedback = OpenAIController().FormatOpenAICall(
        sys_prompt=sys_prompt,
        user_prompt=user_prompt,
        model="gpt-4-0125-preview",
        token_size=4096,
        temp=1,
        format=format
    )
    if not res:
        return ArgumentExceptionResponse(msg=feedback)
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
        format = ACADEMIC_DISCUSSION_EDITING_FORMAT
    elif essay.gradeType == "Integrated Writing":
        sys_prompt = INTEGRATED_WRITING_EDITING_SYSPROMPT
        format = ACADEMIC_DISCUSSION_EDITING_FORMAT
    else:
        return ArgumentExceptionResponse(msg='Error: Invalid gradeType')

    dict_feedback = {}
    for i in range(len(feedback["Sentence Feedback"])):
        dict_feedback[str(i+1)] = feedback["Sentence Feedback"][i]["feedback"]
    user_prompt += "\n" + json.dumps(dict_feedback, indent=4)
    # get editing
    res, edit = OpenAIController().FormatOpenAICall(
        sys_prompt=sys_prompt,
        user_prompt=user_prompt,
        model="gpt-4-0125-preview",
        token_size=4096,
        temp=1,
        format=format
    )
    if not res:
        return ArgumentExceptionResponse(msg=edit)
    sentence_feedback = {}
    for i in range(len(feedback["Sentence Feedback"])):
        try:
            sentence_feedback[str(i + 1)] = {
                "Feedback": feedback["Sentence Feedback"][i]["feedback"],
                "Edited": edit["Edited Version"][i]["sentence"],
                "Type": feedback["Sentence Feedback"][i]["feedbackType"]
            }
        except Exception as e:
            return ArgumentExceptionResponse(msg=str(e))

    d.update({"Sentence Feedback": sentence_feedback})

    # Make a mind-map
    if essay.gradeType == "Academic Discussion":
        sys_prompt = ACADEMIC_DISCUSSION_MINDMAP_SYSPROMPT
    elif essay.gradeType == "Integrated Writing":
        sys_prompt = INTEGRATED_WRITING_MINDMAP_SYSPROMPT
    else:
        return ArgumentExceptionResponse(msg='Error: Invalid gradeType')

    user_prompt = json.dumps(content, indent=4)
    format = MINDMAP_FORMAT

    # get mindmap
    res, mindmap = OpenAIController().FormatOpenAICall(
        sys_prompt=sys_prompt,
        user_prompt=user_prompt,
        model="gpt-4-0125-preview",
        token_size=1024,
        temp=1,
        format=format
    )
    if not res:
        return ArgumentExceptionResponse(msg=mindmap)
    d.update(mindmap)

    res, censorData = OpenAIController().censorOutput(d)
    if res:
        return SuccessDataResponse(data=censorData)
        logger.info(f"API: /writing/gradeWriting/ responded")
        return SuccessDataResponse(data=censorData)
    else:
        return ArgumentExceptionResponse(msg=censorData)


@router.post("/speaking/gradeSpeaking/")
async def gradeSpeaking(speak: Speak):
    d = {}
    logger.info(f"API: /speaking/gradeSpeaking/ was called")
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
                    "audioType": "wav",
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
    try:
        if "error" in speech_res.keys():
            return ArgumentExceptionResponse(msg=speech_res["error"])
        elif "warning" in speech_res["result"]:
            return ArgumentExceptionResponse(msg=speech_res["result"]["warning"]["message"])
        elif speech_res["result"]["effective_speech_length"] <= 10:
            return ArgumentExceptionResponse(msg="Error: Input too short")
        student_transcript = {}
        for i in range(len(speech_res["result"]["sentences"])):
            student_transcript[str(i+1)] = speech_res["result"]["sentences"][i]["sentence"]
        d.update({"Content": [student_transcript]})

    except Exception as e:
        return ArgumentExceptionResponse(msg=str(e))
    
    # GPT Grading
    format = SPEAKING_GRADING_FORMAT
    if speak.gradeType == "Independent Speaking":
        sys_prompt = INDEPENDENT_SPEAKING_GRADING_SYSPROMPT
    elif speak.gradeType == "Integrated Speaking":
        sys_prompt = INTEGRATED_SPEAKING_GRADING_SYSPROMPT
    else:
        return ArgumentExceptionResponse(msg='Error: Invalid gradeType')
    user_prompt = "Prompt: " + speak.prompt + "\n\nStudent Transcript: " + speech_res["result"]["transcription"]
    res, data = OpenAIController().FormatOpenAICall(
        sys_prompt=sys_prompt,
        user_prompt=user_prompt,
        model="gpt-4-0125-preview",
        token_size=512,
        temp=1,
        format=format
    )
    if not res:
        return ArgumentExceptionResponse(msg=data)
    try:
        grades = data["Grades"]
        grades["Grammar"] = speech_res["result"]["grammar"] // 2
        grades["Vocabulary Usage"] = speech_res["result"]["lexical_resource"] // 2
        grades["Fluency"] = speech_res["result"]["fluency_coherence"] // 2
        grades["Pronunciation"] = speech_res["result"]["pronunciation"] // 2
        tot = math.ceil(
            grades["Content"] + grades["Coherence"] + ((grades["Grammar"] + grades["Vocabulary Usage"]) / 2) + (
                        grades["Fluency"] + grades["Pronunciation"]) / 2)
        avg = math.floor(tot / 2) / 2
        d["Overall"] = str(avg)
        for k, v in grades.items():
            grades[k] = str(v)
        d.update({"Grades": grades})
    except Exception as e:
        return ArgumentExceptionResponse(msg=str(e))
    # Send Feedback Request
    try:
        format = SPEAKING_FEEDBACK_FORMAT
        if speak.gradeType == "Independent Speaking":
            sys_prompt = INDEPENDENT_SPEAKING_FEEDBACK_SYSPROMPT
        elif speak.gradeType == "Integrated Speaking":
            sys_prompt = INTEGRATED_SPEAKING_FEEDBACK_SYSPROMPT
        else:
            return ArgumentExceptionResponse(msg='Error: Invalid gradeType')
        user_prompt = "Prompt:\n" + speak.prompt + "\nStudent Transcript:\n" + json.dumps(student_transcript,
                                                                                          indent=4) + "\nScore:\n"
        user_prompt += "Content: " + grades["Content"] + "\nCoherence: " + grades[
            "Coherence"] + "\nGrammar and Language Use: " + str(
            (int(grades["Grammar"]) + int(grades["Vocabulary Usage"])) / 2) + "\nDelivery: " + str(
            (int(grades["Fluency"]) + int(grades["Pronunciation"])) / 2)
    except Exception as e:
        return ArgumentExceptionResponse(msg=str(e))
    res, feedback = OpenAIController().FormatOpenAICall(
        sys_prompt=sys_prompt,
        user_prompt=user_prompt,
        model="gpt-4-0125-preview",
        token_size=4096,
        temp=1,
        format=format
    )
    if not res:
        return ArgumentExceptionResponse(msg=feedback)
    try:
        gen_feedback = ""
        for k, v in feedback["General Feedback"].items():
            gen_feedback += k + ": " + v + "\n"
        temp_sent_feedback = {}
        for i in range(len(feedback["Sentence Feedback"])):
            temp_sent_feedback[str(i+1)] = {"Feedback": feedback["Sentence Feedback"][i]["feedback"], "Type": feedback["Sentence Feedback"][i]["feedbackType"]}

            temp_sent_feedback[str(i + 1)] = feedback["Sentence Feedback"][i]["sentence"]

        d.update({"General Feedback": gen_feedback})
        d.update({"Sentence Feedback": temp_sent_feedback})
        word_pronunciation = {}
        pronunciation = {}
        for s in speech_res["result"]["sentences"]:
            for w in s["details"]:
                if w["word"] not in word_pronunciation.keys():
                    word_pronunciation[w["word"]] = [w["pronunciation"]]
                else:
                    word_pronunciation[w["word"]].append(w["pronunciation"])
        for k, v in word_pronunciation.items():
            if math.floor(sum(v) / len(v)) < 60:
                pronunciation[k] = str(math.floor(sum(v) / len(v)))
        d.update({"Bad Pronunciation Scores": pronunciation})

    except Exception as e:
        return ArgumentExceptionResponse(msg=str(e))

    res, censorData = OpenAIController().censorOutput(d)
    if res:
        return SuccessDataResponse(data=censorData)
        logger.info(f"API: /writing/gradeSpeaking/ responded")
        return SuccessDataResponse(data=censorData)
    else:
        return ArgumentExceptionResponse(msg=censorData)


# ================================== AI Assistant (streaming) ===========================#
@router.post("/assistantChatbot_old/")
async def chatbotRespond(chatbotMessage: ChatbotMessage):
    sys_prompt = OLD_ASSISTANT_CHATBOT_SYSPROMPT
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
    r = RedisWrapper()
    r.set(_uuid, data, 60 * 60 * 8)  # 缓存8个小时
    return SuccessDataResponse(data={"message": "message received", "clientId": _uuid})


@router.get('/assistantChatbot/{client_id}/', status_code=200)
async def chatbotRespond(client_id: str):
    r = RedisWrapper()
    usr_input = RedisWrapper('memory')
    client_request = r.get(client_id)
    if not client_request:
        return ArgumentExceptionResponse(msg='未找到ID或已过期，请重新请求')

    data_input = client_request
    if data_input["chatbotQuery"]:
        usr_input.set(client_id, data_input["chatbotQuery"])

    r.delete(client_id)

    match data_input["toeflType"]:
        case "Reading":
            user_prompt = data_input["Main Content"] + "\n"
            match data_input["queryType"]:
                case "其他问题":
                    sys_prompt = CHATBOT_其他问题_SYSPROMPT
                    user_prompt += data_input["chatbotQuery"]
                case "错题解析":
                    sys_prompt = CHATBOT_错题解析_SYSPROMPT
                    user_prompt += data_input["mcq"]
                case "解题思路":
                    sys_prompt = CHATBOT_解题思路_SYSPROMPT
                    user_prompt += data_input["mcq"] + "\n" + data_input["problemMethod"]
                case "重点信息":
                    sys_prompt = CHATBOT_重点信息_SYSPROMPT
                    user_prompt += data_input["mcq"]
                case "段落逻辑":
                    sys_prompt = CHATBOT_MINDMAP_SYSPROMPT
                case _:
                    return ArgumentExceptionResponse(msg='Invalid queryType')
        case "Listening":
            user_prompt = data_input["Main Content"] + "\n"
            match data_input["queryType"]:
                case "其他问题":
                    sys_prompt = CHATBOT_其他问题_SYSPROMPT
                    user_prompt += data_input["chatbotQuery"]
                case "错题解析":
                    sys_prompt = CHATBOT_错题解析_SYSPROMPT
                    user_prompt += data_input["mcq"]
                case "解题思路":
                    sys_prompt = CHATBOT_解题思路_SYSPROMPT
                    user_prompt += data_input["mcq"] + "\n" + data_input["problemMethod"]
                case "重点信息":
                    sys_prompt = CHATBOT_重点信息_SYSPROMPT
                    user_prompt += data_input["mcq"]
                case "听力逻辑":
                    sys_prompt = CHATBOT_MINDMAP_SYSPROMPT
                case _:
                    return ArgumentExceptionResponse(msg='Invalid queryType')
        case "Speaking":
            user_prompt = data_input["Main Content"] + "\n"
            if data_input["queryType"] == "其他问题":
                sys_prompt = CHATBOT_其他问题_SYSPROMPT
                user_prompt += data_input["chatbotQuery"]
            else:
                return ArgumentExceptionResponse(msg='Invalid queryType')
        case "Writing":
            user_prompt = data_input["Main Content"] + "\n"
            if data_input["queryType"] == "其他问题":
                sys_prompt = CHATBOT_其他问题_SYSPROMPT
                user_prompt += data_input["chatbotQuery"]
            else:
                return ArgumentExceptionResponse(msg='Invalid queryType')
        case "Misc":
            sys_prompt = CHATBOT_MISC_SYSPROMPT
            user_prompt = data_input["chatbotQuery"]
        case _:
            return ArgumentExceptionResponse(msg='Invalid toeflType')

    model = "gpt-4-0125-preview"
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


# ================================== Vocab Learning (streaming) ===========================#
@router.get("/getVocabContent/{client_id}/", status_code=200)
async def getVocabContent(client_id: str):
    r = RedisWrapper()
    client_request = r.get(client_id)
    if not client_request:
        return ArgumentExceptionResponse(msg='未找到ID或已过期，请重新请求')

    data_input = client_request
    r.delete(client_id)

    model = "gpt-4-0125-preview"
    token_size = 4096
    temp = 0.75
    return StreamingResponse(OpenAIController().OpenAiVocabStreaming(
        model=model,
        token_size=token_size,
        temp=temp,
        vocabs=data_input
    ), media_type="text/event-stream")


@router.post("/test/")
async def heartbeat():
    return SuccessDataResponse(data={"msg": "success"})
