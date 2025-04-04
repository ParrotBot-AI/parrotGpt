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
import tiktoken
import urllib.request as urllib2
from blueprints.openaicall.controller import OpenAIController
from utils.response_tools import (SuccessDataResponse, ArgumentExceptionResponse)
from utils import generate_uuid_id
from utils.redis_tools import RedisWrapper
from utils.logger_tools import get_general_logger
from utils import abspath
from sklearn.feature_extraction.text import TfidfVectorizer

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
    #Check length of input
    encoding = tiktoken.encoding_for_model(OPENAI_MODEL)
    if len(encoding.encode(essay.content)) > 700:
        if essay.gradeType == "Academic Discussion":
            returnval = EMPTY_ACADEMIC_DISCUSSION_SCORE
        elif essay.gradeType == "Integrated Writing":
            returnval = EMPTY_INTEGRATED_WRITING_SCORE
        else:
            return ArgumentExceptionResponse(msg='Error: Invalid gradeType')
        returnval["General Feedback"] = "Error: Input too long"
        return SuccessDataResponse(data=returnval)

    d = {}
    logger.info(f"API: /writing/gradeWriting/ was called")

    # Check similarity of student response with given content
    endOfPassage = essay.prompt.find("Source: ")
    if endOfPassage != -1:
        corpus = [essay.prompt[:endOfPassage],essay.content]
    else:
        corpus = [essay.prompt,essay.content]
    vect = TfidfVectorizer(min_df=1)                                                                                                                                                                                                   
    tfidf = vect.fit_transform(corpus)                                                                                                                                                                                                                       
    pairwise_similarity = tfidf * tfidf.T
    similarity_score = pairwise_similarity.toarray()
    #print(similarity_score)
    plagiarism = 0
    if similarity_score[0][1] >= 0.90:
        if essay.gradeType == "Academic Discussion":
            returnval = EMPTY_ACADEMIC_DISCUSSION_SCORE
        elif essay.gradeType == "Integrated Writing":
            returnval = EMPTY_INTEGRATED_WRITING_SCORE
        else:
            return ArgumentExceptionResponse(msg='Error: Invalid gradeType')
        returnval["General Feedback"] = "Plagiarism " + str(similarity_score[0][1])
        return SuccessDataResponse(data=returnval)
    if similarity_score[0][1] >= 0.80:
        plagiarism = 1
    
    # Check word count of student response
    if essay.gradeType == "Academic Discussion" and len(essay.content.split()) < 10:
        returnval = EMPTY_ACADEMIC_DISCUSSION_SCORE
        returnval["General Feedback"] = "Nonsense. Are you even trying?"
        return SuccessDataResponse(data=returnval)
    elif essay.gradeType == "Integrated Writing" and len(essay.content.split()) < 10:
        returnval = EMPTY_INTEGRATED_WRITING_SCORE
        returnval["General Feedback"] = "Nonsense. Are you even trying?"
        return SuccessDataResponse(data=returnval)

    wordCountEnough = 1
    if essay.gradeType == "Academic Discussion" and len(essay.content.split()) < 90:
        wordCountEnough = 0
    elif essay.gradeType == "Integrated Writing" and len(essay.content.split()) < 140:
        wordCountEnough = 0

    # Read Request
    if essay.gradeType == "Academic Discussion":
        sys_prompt = ACADEMIC_DISCUSSION_GRADING_SYSPROMPT
        format = ACADEMIC_DISCUSSION_GRADING_FORMAT
    elif essay.gradeType == "Integrated Writing":
        sys_prompt = INTEGRATED_WRITING_GRADING_SYSPROMPT
        format = INTEGRATED_WRITING_GRADING_FORMAT
    else:
        return ArgumentExceptionResponse(msg='Error: Invalid gradeType')
    
    content = []
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
    unclean_content = essay.content.splitlines()
    for i in unclean_content:
        if i != '':
            content.append(i)

    # Use nltk sent_tokenize to separate sentences
    for i in range(len(content)):
        content[i] = sent_tokenize(content[i])
    num_sentences = 0
    # Prepare Grades Request
    # new_content holds the object that will be returned to requester
    # gpt_content holds the object that gpt gets
    for i in range(len(content)):
        new_content.append({})
        for j in range(len(content[i])):
            new_content[i][str(num_sentences+1)] = content[i][j]
            gpt_content[str(num_sentences+1)] = content[i][j]
            num_sentences += 1
    d.update({"Content": new_content})
    # Send Grades Request
    res, data = OpenAIController().FormatOpenAICall(
        sys_prompt=sys_prompt,
        user_prompt=essay.prompt + "\n\n" + essay.content,
        model=OPENAI_MODEL,
        token_size=512,
        temp=1,
        format=format
    )
    user_prompt = essay.prompt + "\n\n" + json.dumps(gpt_content, indent=4)
    if not res:
        return ArgumentExceptionResponse(msg=data)
    
    # Set Up Grades
    try:
        sum = 0
        for k, v in data.items():
            # Maximize score to 2 if there aren't enough words
            if (not wordCountEnough or plagiarism) and v > 2:
                sum += 2
                data[k] = "2"
            else:
                sum += v
                data[k] = str(v)
        if essay.gradeType == "Academic Discussion":
            d["Overall"] = str(sum / 4)
        elif essay.gradeType == "Integrated Writing":
            d["Overall"] = str(math.floor(sum * 4 / 3) / 4)
    except Exception as e:
        return ArgumentExceptionResponse(msg=str(e))
    d.update({"Grades":data})


    # Prepare Feedback Request
    if essay.gradeType == "Academic Discussion":
        sys_prompt = ACADEMIC_DISCUSSION_FEEDBACK_SYSPROMPT
        format = ACADEMIC_DISCUSSION_FEEDBACK_FORMAT
    elif essay.gradeType == "Integrated Writing":
        sys_prompt = INTEGRATED_WRITING_FEEDBACK_SYSPROMPT
        format = INTEGRATED_WRITING_FEEDBACK_FORMAT
    else:
        return ArgumentExceptionResponse(msg='Error: Invalid gradeType')
    if plagiarism:
        sys_prompt += "In the general feedback section, give standard feedback but also add that the score was decreased since the student's response is too similar to the reading passage."
    if not wordCountEnough:
        sys_prompt += "In the general feedback section, give standard feedback but also add that the score was decreased since the student's response doesn't contain enough words."
    #format[0]["parameters"]["properties"]["Sentence Feedback"]["minItems"] = num_sentences
    #format[0]["parameters"]["properties"]["Sentence Feedback"]["maxItems"] = num_sentences

    user_prompt += "\n\nScore:\n"
    for k, v in data.items():
        user_prompt += k + ": " + v + "\n"
    # Send Feedback Request
    res, feedback = OpenAIController().FormatOpenAICall(
        sys_prompt=sys_prompt,
        user_prompt=user_prompt,
        model=OPENAI_MODEL,
        token_size=4096,
        temp=1,
        format=format
    )
    if not res:
        return ArgumentExceptionResponse(msg=feedback)
    
    #Set up General Feedback
    try:
        gen_feedback = ""
        for k, v in feedback["General Feedback"].items():
            gen_feedback += k + ": " + v + "\n"
        d.update({"General Feedback": gen_feedback})
    except Exception as e:
        return ArgumentExceptionResponse(msg=str(e))

    # Prepare Editing Request
    if essay.gradeType == "Academic Discussion":
        sys_prompt = ACADEMIC_DISCUSSION_EDITING_SYSPROMPT
        format = ACADEMIC_DISCUSSION_EDITING_FORMAT
    elif essay.gradeType == "Integrated Writing":
        sys_prompt = INTEGRATED_WRITING_EDITING_SYSPROMPT
        format = INTEGRATED_WRITING_EDITING_FORMAT
    else:
        return ArgumentExceptionResponse(msg='Error: Invalid gradeType')
    dict_feedback = {}
    for i in range(len(feedback["Sentence Feedback"])):
        dict_feedback[str(i+1)] = feedback["Sentence Feedback"][i]["feedback"]
    user_prompt += "\n" + json.dumps(dict_feedback, indent=4)
    #format[0]["parameters"]["properties"]["Edited Version"]["minItems"] = num_sentences
    #format[0]["parameters"]["properties"]["Edited Version"]["maxItems"] = num_sentences

    # Send Editing Request
    res, edit = OpenAIController().FormatOpenAICall(
        sys_prompt=sys_prompt,
        user_prompt=user_prompt,
        model=OPENAI_MODEL,
        token_size=4096,
        temp=1,
        format=format
    )
    if not res:
        return ArgumentExceptionResponse(msg=edit)
    
    #Set Up Sentence Feedback
    i = 0
    sentence_feedback = {}
    try:
        while i < num_sentences:
            sentence_feedback[str(i + 1)] = {}
            if i < len(feedback["Sentence Feedback"]):
                sentence_feedback[str(i + 1)]["Feedback"] = feedback["Sentence Feedback"][i]["feedback"]
                sentence_feedback[str(i + 1)]["Type"] = feedback["Sentence Feedback"][i]["feedbackType"]
            if i < len(edit["Edited Version"]):
                sentence_feedback[str(i + 1)]["Edited"] = edit["Edited Version"][i]["sentence"]      
            i+=1
        j = i
        while j < len(feedback["Sentence Feedback"]):
            sentence_feedback[str(i)]["Feedback"] += feedback["Sentence Feedback"][j]["feedback"]
            sentence_feedback[str(i)]["Type"] = list(set(sentence_feedback[str(i)]["Type"]).union(set(feedback["Sentence Feedback"][j]["feedbackType"])))
            j += 1
        j = i
        while j < len(edit["Edited Version"]):
            if sentence_feedback[str(i)]["Edited"] == "No Change" and edit["Edited Version"][j]["sentence"] != "No Change":
                sentence_feedback[str(i)]["Edited"] = edit["Edited Version"][j]["sentence"]
            else:
                if edit["Edited Version"][j]["sentence"] != "No Change":
                    sentence_feedback[str(i)]["Edited"] += " " + edit["Edited Version"][j]["sentence"]
            j += 1
    except Exception as e:
        return ArgumentExceptionResponse(msg=str(e))
    #print(num_sentences, len(feedback["Sentence Feedback"]), len(edit["Edited Version"]))
    """
    for i in range(num_sentences):
        try:
            sentence_feedback[str(i + 1)] = {
                "Feedback": feedback["Sentence Feedback"][i]["feedback"],
                "Edited": edit["Edited Version"][i]["sentence"],
                "Type": feedback["Sentence Feedback"][i]["feedbackType"]
            }
        except Exception as e:
            return ArgumentExceptionResponse(msg=str(e))
    """

    d.update({"Sentence Feedback": sentence_feedback})

    #Set Up Edited Score
    try:
        sum = 0
        for k, v in edit["New Score"].items():
            sum += v
        if essay.gradeType == "Academic Discussion":
            d["Edited Overall"] = str(sum / 4)
        elif essay.gradeType == "Integrated Writing":
            d["Edited Overall"] = str(math.floor(sum * 4 / 3) / 4)
    except Exception as e:
        return ArgumentExceptionResponse(msg=str(e))

    # Prepare the Mind-Map Request
    format = MINDMAP_FORMAT
    if essay.gradeType == "Academic Discussion":
        sys_prompt = ACADEMIC_DISCUSSION_MINDMAP_SYSPROMPT
    elif essay.gradeType == "Integrated Writing":
        sys_prompt = INTEGRATED_WRITING_MINDMAP_SYSPROMPT
    else:
        return ArgumentExceptionResponse(msg='Error: Invalid gradeType')
    user_prompt = json.dumps(gpt_content, indent=4)

    # Send the Mind-Map Request
    res, mindmap = OpenAIController().FormatOpenAICall(
        sys_prompt=sys_prompt,
        user_prompt=user_prompt,
        model=OPENAI_MODEL,
        token_size=1024,
        temp=1,
        format=format
    )
    if not res:
        return ArgumentExceptionResponse(msg=mindmap)
    d.update(mindmap)

    #Censor
    res, censorData = OpenAIController().censorOutput(d)
    if res:
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
    url = "http://api.stkouyu.com:8080/speak.eval.pro"
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
                    "applicationId": appKey,
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
    for i in range(3):
        try:
            files = {"audio": urllib2.urlopen(speak.audioLink)}
            res = requests.post(url, data=data, headers=headers, files=files)
            break
        except Exception as e:
            time.sleep(30)
            if i == 2:  
                returnval = EMPTY_SPEAKING_SCORE
                returnval["General Feedback"] = "SpeechSuper Error"
                return SuccessDataResponse(data=returnval)

    speech_res = json.loads(res.text.encode('utf-8', 'ignore'))
    try:
        if "error" in speech_res.keys():
            return ArgumentExceptionResponse(msg=speech_res["error"])
        elif "warning" in speech_res["result"]:
            returnval = EMPTY_SPEAKING_SCORE
            returnval["General Feedback"] = speech_res["result"]["warning"][0]["message"]
            return SuccessDataResponse(data=returnval)
        elif speech_res["result"]["effective_speech_length"] <= 10:
            returnval = EMPTY_SPEAKING_SCORE
            returnval["General Feedback"] = "Input too short."
            return SuccessDataResponse(data=returnval)
        student_transcript = {}
        for i in range(len(speech_res["result"]["sentences"])):
            student_transcript[str(i+1)] = speech_res["result"]["sentences"][i]["sentence"]
        d.update({"Content": [student_transcript]})
        #print(student_transcript)
    except Exception as e:
        return ArgumentExceptionResponse(msg=str(e))
    
    # Prepare GPT Grading Request
    format=SPEAKING_GRADING_FORMAT
    if speak.gradeType == "Independent Speaking":
        sys_prompt = INDEPENDENT_SPEAKING_GRADING_SYSPROMPT
    elif speak.gradeType == "Integrated Speaking":
        sys_prompt = INTEGRATED_SPEAKING_GRADING_SYSPROMPT
    else:
        return ArgumentExceptionResponse(msg='Error: Invalid gradeType')
    user_prompt = "Prompt: " + speak.prompt + "\n\nStudent Transcript: " + speech_res["result"]["transcription"]

    # Send GPT Grading Request
    res, data = OpenAIController().FormatOpenAICall(
        sys_prompt=sys_prompt,
        user_prompt=user_prompt,
        model=OPENAI_MODEL,
        token_size=512,
        temp=1,
        format=format
    )
    if not res:
        return ArgumentExceptionResponse(msg=data)
    
    #Set up Grades
    try:
        grades = data
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
    
    # Prepare Feedback Request
    try:
        format = SPEAKING_FEEDBACK_FORMAT
        #format[0]["parameters"]["properties"]["Sentence Feedback"]["minItems"] = len(student_transcript)
        #format[0]["parameters"]["properties"]["Sentence Feedback"]["maxItems"] = len(student_transcript)
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
    
    #Send Feedback Request
    res, feedback = OpenAIController().FormatOpenAICall(
        sys_prompt=sys_prompt,
        user_prompt=user_prompt,
        model=OPENAI_MODEL,
        token_size=4096,
        temp=1,
        format=format
    )
    if not res:
        return ArgumentExceptionResponse(msg=feedback)
    
    #Set Up General Feedback
    try:
        gen_feedback = ""
        for k, v in feedback["General Feedback"].items():
            gen_feedback += k + ": " + v + "\n"
        d.update({"General Feedback": gen_feedback})
    except Exception as e:
        return ArgumentExceptionResponse(msg=str(e)) 
    
    # Prepare Editing Request
    format=SPEAKING_EDITING_FORMAT
    #format[0]["parameters"]["properties"]["Edited Version"]["minItems"] = len(student_transcript)
    #format[0]["parameters"]["properties"]["Edited Version"]["maxItems"] = len(student_transcript)
    if speak.gradeType == "Independent Speaking":
        sys_prompt = INDEPENDENT_SPEAKING_EDITING_SYSPROMPT
    elif speak.gradeType == "Integrated Speaking":
        sys_prompt = INTEGRATED_SPEAKING_EDITING_SYSPROMPT
    else:
        return ArgumentExceptionResponse(msg='Error: Invalid gradeType')
    dict_feedback = {}
    for i in range(len(feedback["Sentence Feedback"])):
        dict_feedback[str(i+1)] = feedback["Sentence Feedback"][i]["feedback"]
    user_prompt += "\n" + json.dumps(dict_feedback, indent=4)

    # Send Editing Request
    res, edit = OpenAIController().FormatOpenAICall(
        sys_prompt=sys_prompt,
        user_prompt=user_prompt,
        model=OPENAI_MODEL,
        token_size=4096,
        temp=1,
        format=format
    )
    if not res:
        return ArgumentExceptionResponse(msg=edit)
    
    #Set Up Sentence Feedback
    i = 0
    sentence_feedback = {}
    try:
        while i < len(student_transcript):
            sentence_feedback[str(i + 1)] = {}
            if i < len(feedback["Sentence Feedback"]):
                sentence_feedback[str(i + 1)]["Feedback"] = feedback["Sentence Feedback"][i]["feedback"]
                sentence_feedback[str(i + 1)]["Type"] = feedback["Sentence Feedback"][i]["feedbackType"]
            if i < len(edit["Edited Version"]):
                sentence_feedback[str(i + 1)]["Edited"] = edit["Edited Version"][i]["sentence"]      
            i+=1
        j = i
        while j < len(feedback["Sentence Feedback"]):
            sentence_feedback[str(i)]["Feedback"] += feedback["Sentence Feedback"][j]["feedback"]
            sentence_feedback[str(i)]["Type"] = list(set(sentence_feedback[str(i)]["Type"]).union(set(feedback["Sentence Feedback"][j]["feedbackType"])))
            j += 1
        j = i
        while j < len(edit["Edited Version"]):
            if sentence_feedback[str(i)]["Edited"] == "No Change" and edit["Edited Version"][j]["sentence"] != "No Change":
                sentence_feedback[str(i)]["Edited"] = edit["Edited Version"][j]["sentence"]
            else:
                if edit["Edited Version"][j]["sentence"] != "No Change":
                    sentence_feedback[str(i)]["Edited"] += " " + edit["Edited Version"][j]["sentence"]
            j += 1

        #Remove "Delivery" from feedback types and change to "Coherence" as necessary
        for i in range(len(student_transcript)):
            if "Delivery" in sentence_feedback[str(i+1)]["Type"]:
                if "Coherence" in sentence_feedback[str(i+1)]["Type"]:
                    for j in range(len(sentence_feedback[str(i+1)]["Type"])):
                        if sentence_feedback[str(i+1)]["Type"][j] == "Delivery":
                            del sentence_feedback[str(i+1)]["Type"][j]
                            break
                else:
                    for j in range(len(sentence_feedback[str(i+1)]["Type"])):
                        if sentence_feedback[str(i+1)]["Type"][j] == "Delivery":
                            sentence_feedback[str(i+1)]["Type"][j] = "Coherence"
                            break
        #print(len(student_transcript), len(feedback["Sentence Feedback"]), len(edit["Edited Version"]))
    except Exception as e:
        return ArgumentExceptionResponse(msg=str(e))

    """
    for i in range(len(feedback["Sentence Feedback"])):
        try:
            sentence_feedback[str(i + 1)] = {
                "Feedback": feedback["Sentence Feedback"][i]["feedback"],
                "Edited": edit["Edited Version"][i]["sentence"],
                "Type": feedback["Sentence Feedback"][i]["feedbackType"]
            }
        except Exception as e:
            return ArgumentExceptionResponse(msg=str(e))
    """
        
    d.update({"Sentence Feedback": sentence_feedback})

    #Set Up Edited Score
    try:
        tot = math.ceil(edit["New Score"]["Content"] + edit["New Score"]["Coherence"] + edit["New Score"]["Grammar and Language Use"] + (int(grades["Fluency"]) + int(grades["Pronunciation"])) / 2)
        avg = math.floor(tot / 2) / 2
        d["Edited Overall"] = str(avg)
    except Exception as e:
        return ArgumentExceptionResponse(msg=str(e))

    # Set Up Mind-Map Request
    format = MINDMAP_FORMAT
    if speak.gradeType == "Independent Speaking":
        sys_prompt = INDEPENDENT_SPEAKING_MINDMAP_SYSPROMPT
    elif speak.gradeType == "Integrated Speaking":
        sys_prompt = INTEGRATED_SPEAKING_MINDMAP_SYSPROMPT
    else:
        return ArgumentExceptionResponse(msg='Error: Invalid gradeType')
    user_prompt = json.dumps(student_transcript, indent=4)

    # Send Mind-Map Request
    res, mindmap = OpenAIController().FormatOpenAICall(
        sys_prompt=sys_prompt,
        user_prompt=user_prompt,
        model=OPENAI_MODEL,
        token_size=1024,
        temp=1,
        format=format
    )
    if not res:
        return ArgumentExceptionResponse(msg=mindmap)
    d.update(mindmap)

    #Set Bad Pronunciation Scores
    try:
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

    #Censor
    res, censorData = OpenAIController().censorOutput(d)
    if res:
        logger.info(f"API: /writing/gradeSpeaking/ responded")
        return SuccessDataResponse(data=censorData)
    else:
        return ArgumentExceptionResponse(msg=censorData)


# ================================== AI Assistant (streaming) ===========================#
@router.post("/assistantChatbot_old/") #depreciated
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

    sys_prompt = CHATBOT_PRE_SYSPROMPT
    match data_input["toeflType"]:
        case "Reading":
            user_prompt = data_input["Main Content"] + "\n"
            match data_input["queryType"]:
                case "其他问题":
                    sys_prompt += CHATBOT_其他问题_SYSPROMPT
                    user_prompt += data_input["chatbotQuery"]
                case "错题解析":
                    sys_prompt += CHATBOT_错题解析_SYSPROMPT
                    user_prompt += data_input["mcq"]
                case "解题思路":
                    sys_prompt += CHATBOT_解题思路_SYSPROMPT
                    user_prompt += data_input["mcq"] + "\n" + data_input["problemMethod"]
                case "重点信息":
                    sys_prompt += CHATBOT_重点信息_SYSPROMPT
                    user_prompt += data_input["mcq"]
                case "段落逻辑":
                    sys_prompt += CHATBOT_MINDMAP_SYSPROMPT
                case _:
                    return ArgumentExceptionResponse(msg='Invalid queryType')
        case "Listening":
            user_prompt = data_input["Main Content"] + "\n"
            match data_input["queryType"]:
                case "其他问题":
                    sys_prompt += CHATBOT_其他问题_SYSPROMPT
                    user_prompt += data_input["chatbotQuery"]
                case "错题解析":
                    sys_prompt += CHATBOT_错题解析_SYSPROMPT
                    user_prompt += data_input["mcq"]
                case "解题思路":
                    sys_prompt += CHATBOT_解题思路_SYSPROMPT
                    user_prompt += data_input["mcq"] + "\n" + data_input["problemMethod"]
                case "重点信息":
                    sys_prompt += CHATBOT_重点信息_SYSPROMPT
                    user_prompt += data_input["mcq"]
                case "听力逻辑":
                    sys_prompt += CHATBOT_MINDMAP_SYSPROMPT
                case _:
                    return ArgumentExceptionResponse(msg='Invalid queryType')
        case "Speaking":
            user_prompt = data_input["Main Content"] + "\n"
            if data_input["queryType"] == "其他问题":
                sys_prompt += CHATBOT_其他问题_SYSPROMPT
                user_prompt += data_input["chatbotQuery"]
            else:
                return ArgumentExceptionResponse(msg='Invalid queryType')
        case "Writing":
            user_prompt = data_input["Main Content"] + "\n"
            if data_input["queryType"] == "其他问题":
                sys_prompt += CHATBOT_其他问题_SYSPROMPT
                user_prompt += data_input["chatbotQuery"]
            else:
                return ArgumentExceptionResponse(msg='Invalid queryType')
        case "Misc":
            sys_prompt += CHATBOT_MISC_SYSPROMPT
            user_prompt = data_input["chatbotQuery"]
        case _:
            return ArgumentExceptionResponse(msg='Invalid toeflType')

    #Check length of input - bypass system and user prompt if token size is too large
    encoding = tiktoken.encoding_for_model(OPENAI_MODEL)
    if len(encoding.encode(data_input["chatbotQuery"])) > 100:
        sys_prompt = "用简体中文跟学生说你的问题太长了，秋秋无法回答"
        user_prompt = ""

    token_size = 1024
    temp = 0
    response = StreamingResponse(OpenAIController().OpenAiStreaming(
        sys_prompt=sys_prompt,
        user_prompt=user_prompt,
        model=OPENAI_MODEL,
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

    model = OPENAI_MODEL
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
