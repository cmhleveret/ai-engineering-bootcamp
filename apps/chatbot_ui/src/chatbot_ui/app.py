import streamlit as st
import requests
from chatbot_ui.core.config import config
import json
import uuid

st.set_page_config(
    page_title="Ecommerce Assistant",
    layout="wide",
    initial_sidebar_state="expanded"
)

def get_session_id():
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    return st.session_state.session_id

thread_id = get_session_id()

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


def stream_agent_call(url, payload):
    """Consume the agent's SSE stream.

    Yields ("status", text) for progress updates, ("final", data) for the
    completed answer, and ("error", message) if the call fails.
    """
    try:
        with requests.post(url, json=payload, stream=True) as response:
            if not response.ok:
                try:
                    body = response.json()
                    message = body.get("message") or body.get("detail")
                except requests.exceptions.JSONDecodeError:
                    message = None
                yield "error", message or f"Request failed with status {response.status_code}."
                return

            for line in response.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data:"):
                    continue

                content = line[len("data:"):].strip()
                if not content:
                    continue

                # Progress updates are plain text; the final answer is a JSON event.
                try:
                    event = json.loads(content)
                except json.JSONDecodeError:
                    yield "status", content
                    continue

                if isinstance(event, dict) and event.get("type") == "final_answer":
                    yield "final", event.get("data", {})
                else:
                    yield "status", content

    except requests.exceptions.ConnectionError:
        yield "error", "Connection error. Please check your network connection."
    except requests.exceptions.Timeout:
        yield "error", "The request timed out. Please try again later."
    except Exception as e:
        yield "error", f"An unexpected error occurred: {str(e)}"


def submit_feedback(feedback_type=None, feedback_text=""):
    """Submit feedback to the API endpoint"""

    def _feedback_score(feedback_type):
        if feedback_type == "positive":
            return 1
        elif feedback_type == "negative":
            return 0
        else:
            return None

    feedback_data = {
        "feedback_score": _feedback_score(feedback_type),
        "feedback_text": feedback_text,
        "trace_id": st.session_state.trace_id,
        "feedback_source_type": "api"
    }

    return api_call("post", f"{config.API_URL}/submit_feedback/", json=feedback_data)


## Lets create a sidebar with a dropdown for the model list and providers

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Hello! How can I assist you today?"}]

if "used_context" not in st.session_state:
    st.session_state.used_context = []

if "shopping_cart" not in st.session_state:
    st.session_state.shopping_cart = []

if "thread_id" not in st.session_state:
    st.session_state.thread_id = thread_id

if "trace_id" not in st.session_state:
    st.session_state.trace_id = ""

if "shopping_cart" not in st.session_state:
    st.session_state.shopping_cart = None

# Feedback state for the most recent assistant answer
if "latest_feedback" not in st.session_state:
    st.session_state.latest_feedback = None

if "show_feedback_box" not in st.session_state:
    st.session_state.show_feedback_box = False

if "feedback_submission_status" not in st.session_state:
    st.session_state.feedback_submission_status = None



with st.sidebar:

    suggestions_tab, shopping_cart_tab = st.tabs(["🔍 Suggestions", "🛒 Shopping Cart"])

    with suggestions_tab:
        if st.session_state.used_context:
            for idx, item in enumerate(st.session_state.used_context):
                st.caption(item.get('description', 'No description'))
                if 'image_url' in item:
                    st.image(item["image_url"], width=250)
                st.caption(f"Price: {item['price']} USD")
                st.divider()
        else:
            st.info("No suggestions yet")

    with shopping_cart_tab:
        if st.session_state.shopping_cart:
            
            for idx, item in enumerate(st.session_state.shopping_cart):
                st.caption(item.get('description', 'No description'))
                if 'product_image_url' in item:
                    st.image(item["product_image_url"], width=250)
                st.caption(f"Price: {item['price']} {item['currency']}")
                st.caption(f"Quantity: {item['quantity']}")
                st.caption(f"Total price: {item['total_price']} {item['currency']}")
                st.divider()
        else:
            st.info("Your cart is empty")
            

for idx, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

        # Feedback only on the latest assistant message, skipping the opening greeting.
        # Requires a trace_id — an errored turn has none to attach feedback to.
        is_latest_assistant = (
            message["role"] == "assistant"
            and idx == len(st.session_state.messages) - 1
            and idx > 0
            and st.session_state.trace_id
        )

        if is_latest_assistant:
            feedback_key = f"feedback_{len(st.session_state.messages)}"
            feedback_result = st.feedback("thumbs", key=feedback_key)

            if feedback_result is not None:
                feedback_type = "positive" if feedback_result == 1 else "negative"

                # Only submit when the selection actually changed, otherwise every
                # rerun would re-post the same feedback.
                if st.session_state.latest_feedback != feedback_type:
                    with st.spinner("Submitting feedback..."):
                        status, response = submit_feedback(feedback_type=feedback_type)
                        if status:
                            st.session_state.latest_feedback = feedback_type
                            st.session_state.feedback_submission_status = "success"
                            st.session_state.show_feedback_box = (feedback_type == "negative")
                        else:
                            st.session_state.feedback_submission_status = "error"
                    st.rerun()

            if st.session_state.latest_feedback and st.session_state.feedback_submission_status == "success":
                if st.session_state.latest_feedback == "positive":
                    st.success("✅ Thank you for your positive feedback!")
                elif st.session_state.latest_feedback == "negative" and not st.session_state.show_feedback_box:
                    st.success("✅ Thank you for your feedback!")
            elif st.session_state.feedback_submission_status == "error":
                st.error("❌ Failed to submit feedback. Please try again.")

            if st.session_state.show_feedback_box:
                st.markdown("**Want to tell us more? (Optional)**")
                st.caption("Your negative feedback has already been recorded. You can optionally provide additional details below.")

                feedback_text = st.text_area(
                    "Additional feedback (optional)",
                    key=f"feedback_text_{len(st.session_state.messages)}",
                    placeholder="Please describe what was wrong with this response...",
                    height=100
                )

                col_send, col_spacer, col_close = st.columns([3, 5, 2])
                with col_send:
                    if st.button("Send Additional Details", key=f"send_additional_{len(st.session_state.messages)}"):
                        if feedback_text.strip():
                            with st.spinner("Submitting additional feedback..."):
                                status, response = submit_feedback(feedback_text=feedback_text)
                                if status:
                                    st.session_state.show_feedback_box = False
                                else:
                                    st.error("❌ Failed to submit additional feedback. Please try again.")
                            st.rerun()
                        else:
                            st.warning("Please enter some feedback text before submitting.")

                with col_close:
                    if st.button("Close", key=f"close_feedback_{len(st.session_state.messages)}"):
                        st.session_state.show_feedback_box = False
                        st.rerun()


if prompt := st.chat_input("Hello! How can I assist you today?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        status_placeholder = st.empty()

        answer = None
        used_context = []
        trace_id = ""
        error = None

        for kind, data in stream_agent_call(
            f"{config.API_URL}/agent/",
            {"query": prompt, "thread_id": st.session_state.thread_id},
        ):
            if kind == "status":
                status_placeholder.caption(f"⏳ {data}")
            elif kind == "final":
                answer = data.get("answer", "")
                used_context = data.get("used_context", [])
                trace_id = data.get("trace_id", "")
                shopping_cart = data.get("shopping_cart", [])
            elif kind == "error":
                error = data
                break

        status_placeholder.empty()

        if answer is None:
            answer = error or "Something went wrong."
            used_context = []
            trace_id = ""

        st.session_state.used_context = used_context
        st.session_state.trace_id = trace_id
        st.session_state.shopping_cart = shopping_cart

        st.write(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})

    # Reset feedback for the new answer
    st.session_state.latest_feedback = None
    st.session_state.show_feedback_box = False
    st.session_state.feedback_submission_status = None

    st.rerun()
