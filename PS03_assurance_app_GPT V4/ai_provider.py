"""Configurable OpenAI-compatible Responses API adapter.

Configuration is read from environment variables first, then from secrets.toml in the
project root or .streamlit folder. Secret values are never logged or persisted in SQLite.
"""
from __future__ import annotations
import json
import os
import urllib.request
import urllib.error
from pathlib import Path
try:
    import tomllib
except ImportError:
    import tomli as tomllib

APP_DIR=Path(__file__).resolve().parent
DEFAULT_URL="https://api.openai.com/v1/responses"
ALLOWED_OWNER_ROLES={
    "Engineering Manager","Service Manager","Delivery Assurance Lead",
    "Control Owner","Account Lead","Finance/Commercial Lead","Auditor / Control Reviewer"
}
ALLOWED_HORIZONS={30,60,90}
ALLOWED_PRIORITIES={"Critical","High","Medium","Low"}


def _secrets_file():
    candidates=[APP_DIR/"secrets.toml",APP_DIR/".streamlit"/"secrets.toml",APP_DIR.parent/"secrets.toml"]
    return next((path for path in candidates if path.is_file()),None)


def _settings():
    data={}
    path=_secrets_file()
    if path:
        try:
            with path.open("rb") as stream: data=tomllib.load(stream)
        except Exception as exc:
            raise RuntimeError(f"Could not read {path.name}. Check its TOML syntax.") from exc
    section={}
    for name in ("ai","openai","model"):
        value=data.get(name)
        if isinstance(value,dict): section.update(value)
    # Allow simple top-level keys in secrets.toml as well as [ai]/[openai] sections.
    for key in ("api_key","model","model_name","responses_url","base_url","endpoint","provider"):
        if key in data and not isinstance(data[key],dict): section[key]=data[key]
    api_key=os.getenv("OPENAI_API_KEY") or section.get("api_key") or section.get("key")
    model=os.getenv("OPENAI_MODEL") or section.get("model") or section.get("model_name")
    url=(os.getenv("OPENAI_RESPONSES_URL") or section.get("responses_url") or section.get("endpoint"))
    if not url:
        base=section.get("base_url")
        if base: url=str(base).rstrip("/") + ("/responses" if not str(base).rstrip("/").endswith("/responses") else "")
    return {"api_key":str(api_key or "").strip(),"model":str(model or "").strip(),"url":str(url or DEFAULT_URL).strip(),"source":path.name if path else "environment"}


def provider_ready():
    try:
        config=_settings()
        return bool(config["api_key"] and config["model"])
    except RuntimeError:
        return False


def provider_label():
    try:
        config=_settings()
        if not config["model"]: return "No live model configured"
        return config["model"]
    except RuntimeError:
        return "Configuration file error"


def config_source():
    try:
        config=_settings()
        return config["source"] if config["api_key"] and config["model"] else "not configured"
    except RuntimeError:
        return "configuration error"


def _extract_text(response):
    chunks=[]
    for item in response.get("output",[]):
        if item.get("type")=="message":
            for content in item.get("content",[]):
                if content.get("type")=="output_text" and content.get("text"):
                    chunks.append(content["text"])
    if not chunks and isinstance(response.get("output_text"),str): chunks.append(response["output_text"])
    return "\n".join(chunks).strip()


def _request(prompt, json_object=False, json_schema=None):
    config=_settings()
    if not config["api_key"] or not config["model"]:
        raise RuntimeError("Configure the AI model and API key in secrets.toml or environment variables.")
    payload={"model":config["model"],"input":prompt,"store":False}
    if json_schema is not None:
        payload["text"]={"format":{
            "type":"json_schema",
            "name":"assurance_recommendation",
            "strict":True,
            "schema":json_schema,
        }}
    elif json_object:
        payload["text"]={"format":{"type":"json_object"}}
    request=urllib.request.Request(config["url"],data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization":f"Bearer {config['api_key']}","Content-Type":"application/json"},method="POST")
    try:
        with urllib.request.urlopen(request,timeout=60) as response: body=json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"AI provider returned HTTP {exc.code}. Check the model configuration.") from exc
    except Exception as exc:
        raise RuntimeError("AI provider request failed. Check connectivity and configuration.") from exc
    text=_extract_text(body)
    if not text: raise RuntimeError("The model response did not contain output text.")
    return text,config["model"]


def generate_recommendation(context, persona_name, persona_guidance):
    allowed_refs=context.get("allowed_evidence_refs",[])
    if not allowed_refs:
        raise RuntimeError("No evidence references are available for this engagement.")
    prompt=(
        "You are drafting one proposed delivery-assurance action for an executive application. "
        "Use only supplied case facts. Do not infer an unobserved cause or invent evidence. "
        f"Tailor the recommendation to the selected user persona: {persona_name}. {persona_guidance} "
        "Return a single JSON object with keys title, rationale, owner_role, horizon_days, expected_outcome, "
        "success_measure, priority, confidence, evidence_refs, assumptions. "
        "owner_role must exactly match one of: "+", ".join(sorted(ALLOWED_OWNER_ROLES))+". "
        "horizon_days must be 30, 60, or 90. priority must be Critical, High, Medium, or Low. "
        "Copy evidence_refs exactly from the allowed list and include at least one ID. "
        "Separate verified facts from hypotheses. "
        "If evidence is insufficient, say so and recommend evidence collection. This is a human-review draft, not an assigned action.\n\n"
        "Allowed evidence IDs: "+json.dumps(allowed_refs,ensure_ascii=False)+"\nEngagement context:\n"+
        json.dumps(context,ensure_ascii=False,default=str)
    )
    schema={
        "type":"object",
        "properties":{
            "title":{"type":"string"},
            "rationale":{"type":"string"},
            "owner_role":{"type":"string","enum":sorted(ALLOWED_OWNER_ROLES)},
            "horizon_days":{"type":"integer","enum":sorted(ALLOWED_HORIZONS)},
            "expected_outcome":{"type":"string"},
            "success_measure":{"type":"string"},
            "priority":{"type":"string","enum":sorted(ALLOWED_PRIORITIES)},
            "confidence":{"type":"string"},
            "evidence_refs":{"type":"array","items":{"type":"string","enum":allowed_refs}},
            "assumptions":{"type":"array","items":{"type":"string"}},
        },
        "required":[
            "title","rationale","owner_role","horizon_days","expected_outcome",
            "success_measure","priority","confidence","evidence_refs","assumptions",
        ],
        "additionalProperties":False,
    }
    text,model=_request(prompt,json_schema=schema)
    try: result=json.loads(text)
    except json.JSONDecodeError as exc: raise RuntimeError("The model response was not valid JSON. No recommendation was saved.") from exc
    required={"title","rationale","owner_role","horizon_days","expected_outcome","success_measure","priority","confidence","evidence_refs","assumptions"}
    missing=required-set(result)
    if missing: raise RuntimeError("The model response is missing required fields: "+", ".join(sorted(missing)))
    if result["owner_role"] not in ALLOWED_OWNER_ROLES: raise RuntimeError("The model returned an owner role outside the approved list.")
    try: result["horizon_days"]=int(result["horizon_days"])
    except Exception as exc: raise RuntimeError("The model returned an invalid action horizon.") from exc
    if result["horizon_days"] not in ALLOWED_HORIZONS: raise RuntimeError("The model returned a horizon outside 30, 60, or 90 days.")
    if result["priority"] not in ALLOWED_PRIORITIES: raise RuntimeError("The model returned an invalid priority.")
    refs=result["evidence_refs"]
    if not isinstance(refs,list) or not refs or any(ref not in allowed_refs for ref in refs):
        raise RuntimeError("The model cited evidence outside the engagement context; no recommendation was saved.")
    for key in ("title","rationale","expected_outcome","success_measure","confidence"):
        if not isinstance(result[key],str) or not result[key].strip(): raise RuntimeError(f"The model returned an empty {key} field.")
    if not isinstance(result["assumptions"],list): result["assumptions"]=[str(result["assumptions"])]
    result["model"]=model
    return result


def generate_chat_answer(question,context):
    prompt=(
        "You are a polite, neutral delivery-assurance chatbot for an executive application. "
        "Answer the user's question using only the supplied case facts and records. "
        "Cite engagement IDs and metric names when helpful. Clearly distinguish verified data from assumptions. "
        "If the context does not contain the answer, say so and state what data is missing. "
        "Do not invent facts, change official health ratings, or state that a proposed action is approved. "
        "Use concise, professional language and a neutral tone.\n\n"
        f"Question: {question}\n\nCase context:\n{json.dumps(context,ensure_ascii=False,default=str)}"
    )
    text,model=_request(prompt)
    return text,model
