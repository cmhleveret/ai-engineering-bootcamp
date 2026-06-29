# Here we use the fast api server enpoint with our front end
all our apps will be in he apps folder
now were looking at the `chatbot_ui` folder
1. so as we did with the api we go to the apps folder
```
cd apps
cd chatbot ui
```
we init the a new library
```
uv init --lib
```
adding the chatbot ui to the workspace
and initialising a new project -> the chatbotui project
2. add some additonal values to pyproject.toml
in this case some libs
```
cd ../../
```
because we have initialised this as a project we can add the additional libs from the root using 'chatbotui' after uv add --packages
```
uv add --packkage chatbotui
```
this will be reflected in the pyproject.toml
the llm libs have also been manually removed 
we are using these in the api now instead
3. update the config file
'''
from pydantic_settings import BaseSettings, SettingsConfigDict

class Config(BaseSettings):

    API_URL: str = "http://api:8000"

    model_config = SettingsConfigDict(env_file=".env")

config = Config()
```
4. update the app.py code
import the core config 
(dont need httpx as not running async for now)
we create a fn that calls the api 
```
def api_call(method, url, **kwargs):

    def _show_error_popup(message):
        """Show error message as a popup in the top-right corner."""
        st.session_state["error_popup"] = {
            "visible": True,
            "message": message,
        }

    try:
        response = getattr(requests, method)(url, **kwargs)

        try:
            response_data = response.json()
        except requests.exceptions.JSONDecodeError:
            response_data = {"message": "Invalid response format from server"}

        if response.ok:
            return True, response_data

        return False, response_data

    except requests.exceptions.ConnectionError:
        _show_error_popup("Connection error. Please check your network connection.")
        return False, {"message": "Connection error"}
    except requests.exceptions.Timeout:
        _show_error_popup("The request timed out. Please try again later.")
        return False, {"message": "Request timeout"}
    except Exception as e:
        _show_error_popup(f"An unexpected error occurred: {str(e)}")
        return False, {"message": str(e)}
```
so
```
def api_call(method, url, **kwargs):
```
1. method -> this will be a post get delete or similar
2. url -> url string 
3. any other key value arguments

```
 response = getattr(requests, method)(url, **kwargs)
```
we run the requests lib with the method and variables to make the url call
the api will respond
or fail

4. so lets run a post request to the endpoint 
```
   output = api_call("post", f"{config.API_URL}/chat", json={"provider": st.session_state.provider, "models_name": st.session_state.model_name, "messages": st.session_state.messages})
```
    
so we will 
1. post 
2. to the api -> f"{config.API_URL}/chat" or "http://api:8000/chat"
3. with the json to be sent -> to the endpoint json={"provider": st.session_state.provider, "models_name": st.session_state.model_name, "messages": st.session_state.messages})

in this case the provider, the model name and messages 

we set the endoint in the config file using an f string -> f"{config.API_URL}/chat"
set using ->  API_URL: str = "http://api:8000"

we get the -> 
  response_data = output[1]
as we are running the api dn which returns two variables 
   answer = response_data["message"]
we need to extract the message key

5. now we create a new docker file for the streamlit application 
uisng an image compatibel with uv etc.

use uv img
copy deps and code
install relevany deps
set env
add user
expose port 
run app 

6. update the docker compose file in the root of the monorepo
add
```services:
  streamlit-app:
    build:
      context: .
      dockerfile: apps/chatbot_ui/Dockerfile
    ports:
      - 8501:8501
    env_file:
      - .env
    restart: unless-stopped
    volumes:
      - ./apps/chatbot_ui/src:/a pp/apps/chatbot_ui/src
```

7. take a look at localhost:8501

8. notes on the makefile 
'''
# equivelant of json.lock file for python
run-docker-compose:
	uv sync
	docker compose up --build

clean-notebook-outputs:
	jupyter nbconvert --clear-output --inplace notebooks/*/*.ipynb
'''

runs docker compose 
cleans jupyter oputputs

make sure to not print anything sensitive in jupyter - cleared so theyre not pushed into the git repo


-