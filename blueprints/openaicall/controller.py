import openai
import json
import time
import hashlib
import requests
import urllib.request as urllib2
from blueprints.openaicall.prompts import *

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
      # Send Grading Request
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

  def censorOutput(
          self,
          o
  ):
    TRY_TIME = 2
    count = 0
    valid = 0
    while count < TRY_TIME and valid != 1:
      res, status = self.GeneralOpenAICall(
        sys_prompt= CENSORSHIP_CHECKER_SYSPROMPT,
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