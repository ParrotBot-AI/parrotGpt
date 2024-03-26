import openai
from openai import OpenAI
import json
from blueprints.openaicall.prompts import *
from configs import OPEN_AI_API_KEY
from threading import Thread
from queue import Queue, Empty


class OpenAIController():
    def GeneralOpenAICall(
            self,
            sys_prompt,
            user_prompt,
            model,
            token_size,
            temp
    ):
        try:
            response = openai.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=token_size,
                temperature=temp,
                response_format={"type": "json_object"}
            )
            data = json.loads(response.choices[0].message.content)
            return True, data
        except Exception as e:
            return False, f"{str(e)}"

    def FormatOpenAICall(
            self,
            sys_prompt,
            user_prompt,
            model,
            token_size,
            temp,
            format
    ):
        try:
            response = openai.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=token_size,
                temperature=temp,
                functions=format,
                function_call='auto'
            )
            if response.choices[0].finish_reason == 'function_call':
                data = json.loads(response.choices[0].message.function_call.arguments)
            elif response.choices[0].finish_reason == 'stop':
                data = json.loads(response.choices[0].message.content.replace("```json\n", "").replace("`", ""))
            else:
                return False, "OPENAI FUNCTION CALLING ERROR"
            return True, data
        except Exception as e:
            return False, f"{str(e)}"

    def censorOutput(
            self,
            o
    ):
        TRY_TIME = 2
        count = 0
        valid = 0
        while count < TRY_TIME and valid != 1:
            res, status = self.GeneralOpenAICall(
                sys_prompt=CENSORSHIP_CHECKER_SYSPROMPT,
                user_prompt=json.dumps(o, indent=4),
                model="gpt-4-0125-preview",
                token_size=128,
                temp=1
            )
            if not res:
                return False, "Gptcall error"

            try:
                if status["Status"] == "OK":
                    o.update(status)
                    valid = 1
            except Exception as e:
                valid = 2
            finally:
                count += 1

        if valid == 1:
            return True, o
        elif valid == 0:
            return False, "Not Safe Content"
        elif valid == 2:
            return False, "GPT Error"

    def OpenAiStreaming(self, model, sys_prompt, user_prompt, token_size, temp):
        def generate_stream(queue):
            try:
                client = OpenAI(api_key=OPEN_AI_API_KEY)
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=temp,
                    max_tokens=token_size,
                    stream=True
                )
                for chunk in response:
                    if chunk.choices[0].delta.content != None:
                        data = chunk.choices[0].delta.content
                        queue.put(f"data: {data}\n")
                    else:
                        break  # Exit if no content
                queue.put(f"data: [DONE!]\n\n")
            finally:
                queue.put(None)  # Signal that streaming is done

        queue = Queue()
        Thread(target=generate_stream, args=(queue,), daemon=True).start()

        async def event_generator():
            while True:
                try:
                    data = queue.get(timeout=20)  # Adjust timeout as necessary
                    print(131, data)
                    if data is None:
                        break
                    yield data
                except Empty:
                    break

        return event_generator()

    def OpenAiVocabStreaming(
            self,
            model,
            token_size,
            temp,
            vocabs: dict,
    ):
        def generate_stream(queue):
            try:
                finish = False
                client = OpenAI(api_key=OPEN_AI_API_KEY)

                # init generate
                sys_prompt = VOCAB_PASSAGE_GEN.format(numVocab=len(vocabs))
                user_prompt = "Vocabulary List\n"
                for k, v in vocabs.items():
                    user_prompt += k + " - " + v + "\n"

                words_c = vocabs.copy()
                res_txt = ''
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=temp,
                    max_tokens=token_size,
                    stream=True
                )
                for chunk in response:
                    if chunk.choices[0].delta.content != None:
                        data = chunk.choices[0].delta.content
                        queue.put(f"data: {data}\n")
                        res_txt += data
                    else:
                        # queue.put(f"data: \n")
                        break

                word_miss = {}
                for k, v in words_c.items():
                    if k.lower() not in res_txt.lower() or v.lower() not in res_txt.lower():
                        word_miss[k] = v
                words_c = word_miss.copy()

                if len(list(word_miss.keys())) > 0:
                    user_prompt = "Vocabulary List\n"
                    for k, v in word_miss.items():
                        user_prompt += k + " - " + v + "\n"
                    user_prompt += "\n" + res_txt
                else:
                    finish = True

                TRY_TIME = 2
                count = 0

                total_txt = res_txt + "\n"
                sys_prompt = VOCAB_PASSAGE_FOLLOWUP_GEN.format(numVocab=len(word_miss))
                # generate for 2 more times
                while count < TRY_TIME and not finish:
                    word_miss = {}
                    res_txt = ''
                    response = client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": sys_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        temperature=temp,
                        max_tokens=token_size,
                        stream=True
                    )
                    for chunk in response:
                        if chunk.choices[0].delta.content != None:
                            data = chunk.choices[0].delta.content
                            queue.put(f"data: {data}\n")
                            res_txt += data
                            total_txt += data
                        else:
                            # queue.put(f"data: \n")
                            break
                    for k, v in words_c.items():
                        if k.lower() not in res_txt.lower() or v.lower() not in res_txt.lower():
                            word_miss[k] = v
                    words_c = word_miss.copy()

                    if len(list(word_miss.keys())) > 0:
                        user_prompt = "Vocabulary List\n"
                        for k, v in word_miss.items():
                            user_prompt += k + " - " + v + "\n"
                        user_prompt += total_txt
                        count += 1
                    else:
                        finish = True
                queue.put(f"data: [DONE!]\n\n")
                total_txt += '[DONE!]'
                # print("TOTAL: ", total_txt)
            finally:
                queue.put(None)  # Signal that streaming is done

        queue = Queue()
        Thread(target=generate_stream, args=(queue,), daemon=True).start()

        async def event_generator():
            while True:
                try:
                    data = queue.get(timeout=20)  # Adjust timeout as necessary
                    print(246, data)
                    if data is None:
                        break
                    yield data
                except Empty:
                    break

        return event_generator()
