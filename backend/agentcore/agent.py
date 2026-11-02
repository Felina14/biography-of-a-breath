"""Puff, the Biography of a Breath narrator, hosted on Amazon Bedrock AgentCore Runtime.

The agent loop is a Nova Lite tool-use agent (Bedrock Converse) with a grounding reviewer:
storyboard / moment / towns / events / overview tools over live NOAA GFS data, every line
checked against the tool results before Polly voices it. Same code as the API's narrate(),
so the Lambda can fall back to it if the runtime is unreachable."""
import json, os

_cfg = os.path.join(os.path.dirname(__file__), "breath_config.json")
if os.path.exists(_cfg):
    for k, v in json.load(open(_cfg)).items(): os.environ.setdefault(k, v)
os.environ["IN_AGENTCORE"] = "1"                 # never proxy back to ourselves

from bedrock_agentcore.runtime import BedrockAgentCoreApp
import app as breath

App = BedrockAgentCoreApp()

@App.entrypoint
def invoke(payload, context=None):
    q = {k: str(v) for k, v in (payload or {}).items() if k in ("lat", "lon", "level", "dir", "half", "name")}
    r = breath.narrate({"queryStringParameters": q})
    body = json.loads(r["body"])
    body["served_by"] = "Amazon Bedrock AgentCore Runtime"
    return body

if __name__ == "__main__":
    App.run()
