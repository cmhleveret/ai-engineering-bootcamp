import instructor

from langsmith import traceable, get_current_run_tree
from pydantic import BaseModel, Field

from langchain_core.messages import SystemMessage, convert_to_openai_messages, AIMessage
from langchain_openai import ChatOpenAI

from api.agents.utils.prompt_management import prompt_template_config
from api.agents.utils.utils import postprocess_response
from api.agents.tools import get_formatted_item_context, get_formatted_reviews_context, get_shopping_cart, remove_from_cart, add_to_shopping_cart, check_warehouse_availability, reserve_warehouse_items
from typing import List
from langchain_litellm import ChatLiteLLM



### Global Agent Configs
MAX_ITERATIONS_PRODUCT_QNA = 5
MAX_ITERATIONS_SHOPPING_CART = 4
MAX_ITERATIONS_WAREHOUSE_MANAGER = 4
MAX_ITERATIONS_COORDINATOR = 6


### QnA Agent Response Model
class RAGUsedContext(BaseModel):
    id: str = Field(description="ID of the item used to answer the question")
    description: str = Field(description="Description of the item used to answer the question")

class FinalQnAAgentResponse(BaseModel):

    """Call this tool when the final answer is possible using available context."""

    answer: str = Field(description="Answer to the question")
    references: list[RAGUsedContext] = Field(description="List of items used to answer the question")

### General Agent Response Model
class FinalAgentResponse(BaseModel):

    answer: str = Field(description="Answer to the question")


### Coordinator Agent Response Model
class Plan(BaseModel):
    next_agent: str = Field(description="The next agent to invoke")
    next_agent_task: str = Field(description="The task to be performed by the next agent")


### QnA Agent Node
@traceable(
    name="product_qna_agent",
    run_type="llm",
    metadata={
        "ls_provider": "openai",
        "ls_model_name": "gpt-5.4-mini"
    }
)
def product_qna_agent(state, models=["gpt-5.4-mini", "groq/llama-3.3-70b-versatile"]) -> dict:

    prompts = {}
    for model in models:
        prompts[model] = prompt_template_config("api/agents/prompts/qna_agent.yaml", model).render()

    if state.product_qna_agent.iteration == MAX_ITERATIONS_PRODUCT_QNA:
        tools = [FinalQnAAgentResponse]
    else:
        tools = [get_formatted_item_context, get_formatted_reviews_context, FinalQnAAgentResponse]

    for model in models:
        try:
            llm = ChatLiteLLM(
                model=model,
                reasoning_effort="medium",
                use_responses_api=True
            )
            llm_with_tools = llm.bind_tools(
                tools,
                tool_choice="required"
            )

            response = llm_with_tools.invoke(
                [
                    SystemMessage(content=prompts[model]),
                    *state.messages
                ]
            )
            break
        except Exception as e:
            print(f"Error with model {model}: {e}")
            continue

    postprocessed_response = postprocess_response(response, "FinalQnAAgentResponse", "product_qna_agent")

    final_answer = postprocessed_response.get("final_answer")
    answer = postprocessed_response.get("answer")
    references = postprocessed_response.get("references")
    response = postprocessed_response.get("response")

    return {
        "messages": [response],
        "product_qna_agent": {
            "iteration": state.product_qna_agent.iteration + 1,
            "final_answer": final_answer
        },
        "answer": answer,
        "references": references
    }


### Shopping Cart Agent Node
@traceable(
    name="shopping_cart_agent",
    run_type="llm",
    metadata={
        "ls_provider": "openai",
        "ls_model_name": "gpt-5.4-mini"
    }
)
def shopping_cart_agent(state, models=["gpt-5.4-mini", "groq/llama-3.3-70b-versatile"]) -> dict:

    prompts = {}
    for model in models:
        prompts[model] = prompt_template_config("api/agents/prompts/shopping_cart_agent.yaml", model).render(
            user_id=state.user_id,
            cart_id=state.cart_id
        )

    if state.shopping_cart_agent.iteration == MAX_ITERATIONS_SHOPPING_CART:
        tools = [FinalAgentResponse]
    else:
        tools = [get_shopping_cart, remove_from_cart, add_to_shopping_cart, FinalAgentResponse]

    for model in models:
        try:
            llm = ChatLiteLLM(
                model=model,
                reasoning_effort="medium",
                use_responses_api=True
            )
            llm_with_tools = llm.bind_tools(
                tools,
                tool_choice="required"
            )

            response = llm_with_tools.invoke(
                [
                    SystemMessage(content=prompts[model]),
                    AIMessage(content=state.coordinator_agent.next_agent_task),
                    *state.shopping_cart_agent.messages
                ]
            )
            break
        except Exception as e:
            print(f"Error with model {model}: {e}")
            continue

    postprocessed_response = postprocess_response(response, "FinalAgentResponse", "shopping_cart_agent")

    final_answer = postprocessed_response.get("final_answer")
    answer = postprocessed_response.get("answer")
    response = postprocessed_response.get("response")

    return {
        "messages": [response] if final_answer else [],
        "shopping_cart_agent": {
            "iteration": state.shopping_cart_agent.iteration + 1,
            "final_answer": final_answer,
            "messages": [response]
        },
        "answer": answer
    }


### Warehouse Manager Agent Node
@traceable(
    name="warehouse_manager_agent",
    run_type="llm",
    metadata={
        "ls_provider": "openai",
        "ls_model_name": "gpt-5.4-mini"
    }
)
def warehouse_manager_agent(state, models=["gpt-5.4-mini", "groq/llama-3.3-70b-versatile"]) -> dict:

    prompts = {}
    for model in models:
        prompts[model] = prompt_template_config("api/agents/prompts/warehouse_manager_agent.yaml", model).render()

    if state.warehouse_manager_agent.iteration == MAX_ITERATIONS_WAREHOUSE_MANAGER:
        tools = [FinalAgentResponse]
    else:
        tools = [check_warehouse_availability, reserve_warehouse_items, FinalAgentResponse]

    for model in models:
        try:
            llm = ChatLiteLLM(
                model=model,
                reasoning_effort="medium",
                use_responses_api=True
            )
            llm_with_tools = llm.bind_tools(
                tools,
                tool_choice="required"
            )

            response = llm_with_tools.invoke(
                [
                    SystemMessage(content=prompts[model]),
                    AIMessage(content=state.coordinator_agent.next_agent_task),
                    *state.warehouse_manager_agent.messages
                ]
            )
            break
        except Exception as e:
            print(f"Error with model {model}: {e}")
            continue

    postprocessed_response = postprocess_response(response, "FinalAgentResponse", "warehouse_manager_agent")

    final_answer = postprocessed_response.get("final_answer")
    answer = postprocessed_response.get("answer")
    response = postprocessed_response.get("response")

    return {
        "messages": [response] if final_answer else [],
        "warehouse_manager_agent": {
            "iteration": state.warehouse_manager_agent.iteration + 1,
            "final_answer": final_answer,
            "messages": [response]
        },
        "answer": answer
    }


### Coordinator Agent Node
@traceable(
    name="coordinator_agent",
    run_type="llm",
    metadata={
        "ls_provider": "openai",
        "ls_model_name": "gpt-5.4-mini"
    }
)
def coordinator_agent(state, models=["gpt-5.4-mini", "groq/llama-3.3-70b-versatile"]) -> dict:

    prompts = {}
    for model in models:
        prompts[model] = prompt_template_config("api/agents/prompts/coordinator_agent.yaml", model).render()

    if state.coordinator_agent.iteration == MAX_ITERATIONS_COORDINATOR:
        tools = [FinalAgentResponse]
    else:
        tools = [Plan, FinalAgentResponse]

    for model in models:
        try:
            llm = ChatLiteLLM(
                model=model,
                reasoning_effort="medium",
                use_responses_api=True
            )
            llm_with_tools = llm.bind_tools(
                tools,
                tool_choice="required"
            )

            response = llm_with_tools.invoke(
                [
                    SystemMessage(content=prompts[model]),
                    *state.messages
                ]
            )
            break
        except Exception as e:
            print(f"Error with model {model}: {e}")
            continue

    current_run = get_current_run_tree()
    if current_run:
        trace_id = str(current_run.trace_id)
    else:
        trace_id = ""

    final_answer = False
    answer = ""
    next_agent = ""
    next_agent_task = ""

    if len(response.tool_calls) > 0:
        if response.tool_calls[0].get("name") == "Plan":
            next_agent = response.tool_calls[0].get("args").get("next_agent")
            next_agent_task = response.tool_calls[0].get("args").get("next_agent_task")
            response = AIMessage(content=f"[coordinator_agent decision] Next agent: {next_agent}. Next agent task: {next_agent_task}")
        else:
            postprocessed_response = postprocess_response(response, "FinalAgentResponse")

            final_answer = postprocessed_response.get("final_answer")
            answer = postprocessed_response.get("answer")
            response = postprocessed_response.get("response")

    return {
        "messages": [response] if response else [],
        "coordinator_agent": {
            "iteration": state.coordinator_agent.iteration + 1,
            "final_answer": final_answer,
            "next_agent": next_agent,
            "next_agent_task": next_agent_task
        },
        "answer": answer,
        "trace_id": trace_id
    }