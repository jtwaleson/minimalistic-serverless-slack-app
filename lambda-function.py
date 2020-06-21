import base64
import hmac
import os
import time
import hashlib
import traceback
from urllib.parse import parse_qsl


# A - settings

try:
    SLACK_SIGNING_SECRET = os.environ["SLACK_SIGNING_SECRET"]
except KeyError:
    raise Exception(
        "Set SLACK_SIGNING_SECRET as an environment variable. "
        "You can find this on the Slack 'App Settings' under "
        "'Signing Secret'."
    )

# B - bot command routing boilerplate

SLACK_COMMAND_TO_HANDLER = {}


def _handle_command(command, message, slack_team):
    print("handling command", command)
    if command in SLACK_COMMAND_TO_HANDLER:
        handler = SLACK_COMMAND_TO_HANDLER[command]
        kwargs = {
            "message": message,
            "slack_team": slack_team,
        }
        response = handler(**kwargs)
        if response is None:
            raise Exception(f"Handler {str(handler)} should return a string")
        else:
            return response
    else:
        return f"No handler registered for command {command}"


# this is a decorator for routing commands
def slack_command(command):
    global SLACK_COMMAND_TO_HANDLER
    if command in SLACK_COMMAND_TO_HANDLER:
        raise Exception(f"command {command} is already registered")

    def wrapper(command_handler):
        SLACK_COMMAND_TO_HANDLER[command] = command_handler
        return command_handler

    return wrapper


# C - actual bot functions


@slack_command("/test")
def _bot_add_quote(message, slack_team):
    return "Hello, World"


# D - slack message handling boilerplate


def _validate_signature(event):
    print("validating signature")

    # 1 - get data from request
    request_timestamp = event["headers"]["x-slack-request-timestamp"]
    provided_signature = event["headers"]["x-slack-signature"]
    body = base64.b64decode(event["body"])

    # 2 - validate timestamp
    if abs(time.time() - int(request_timestamp)) > 60 * 5:
        raise Exception(
            "Message timestamp is stale, something is wrong. "
            "Are you replaying an old request?"
        )

    # 3 - create signature
    sig_basestring = str.encode("v0:" + request_timestamp + ":") + body

    calculated_signature = (
        "v0="
        + hmac.new(
            str.encode(SLACK_SIGNING_SECRET),
            msg=sig_basestring,
            digestmod=hashlib.sha256,
        ).hexdigest()
    )

    # 4 - ensure calculated signature matches provided signature
    if not hmac.compare_digest(calculated_signature, provided_signature):
        raise Exception("Signature does not match, will not execute request")


# E - entry point of the app


def lambda_handler(event, context):
    try:
        _validate_signature(event)

        print("parsing body data and handling command")
        data = dict(parse_qsl(base64.b64decode(event["body"]).decode("utf-8")))
        response_text = _handle_command(
            data["command"], data.get("text"), data["team_id"]
        )
        return {
            "statusCode": 200,
            "body": response_text,
        }
    except Exception:
        traceback.print_exc()
        return {
            "statusCode": 200,
            "body": ("Oops, I failed to execute properly:\n" + traceback.format_exc()),
        }
