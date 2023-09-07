import os

from gallon import Gallon, GallonClient, Request

URL = "https://api.openai.com/v1/chat/completions"

client = GallonClient()

app = Gallon()

@app.get("/")
def ask(request:Request):
	text = request.query.get("q", "")
	response = client.post(
		URL,
		headers={"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"], "Content-Type": "application/json"},
		body={
			"messages":[
				{
					"role":"user",
					"content":text,
				}
			],
			"model":"gpt-4-0613",
			"max_tokens":2048,
		},
	)
	return response

app.run()