"""Optional OpenAI Responses API adapter for evidence-grounded synthetic recommendations.

The desktop demo works without a provider. Live requests require OPENAI_API_KEY and
OPENAI_MODEL in the process environment; secrets are never persisted by this module.
"""
from __future__ import annotations
import json
import os
import urllib.request
import urllib.error

DEFAULT_URL = "https://api.openai.com/v1/responses"
ALLOWED_OWNER_ROLES = {
    "Engineering Manager", "Service Manager", "Delivery Assurance Lead",
    "Control Owner", "Account Lead", "Finance/Commercial Lead",
    "Auditor / Control Reviewer"
}
ALLOWED_HORIZONS = {30, 60, 90}
ALLOWED_PRIORITIES = {"Critical", "High", "Medium", "Low"}


def provider_ready():
    return bool(os.getenv("OPENAI_API_KEY", "").strip() and os.getenv("OPENAI_MODEL", "").strip())


def provider_label():
    return os.getenv("OPENAI_MODEL", "No live model configured")


def _extract_text(response):
    chunks=[]
    for item in response.get("output", []):
        if item.get("type") == "message":
            for content in item.get("content", []):
                if content.get("type") == "output_text" and content.get("text"):
                    chunks.append(content["text"])
    if not chunks and isinstance(response.get("output_text"), str):
        chunks.append(response["output_text"])
    return "\n".join(chunks).strip()


def generate_recommendation(context):
    api_key=os.getenv("OPENAI_API_KEY", "").strip()
    model=os.getenv("OPENAI_MODEL", "").strip()
    if not api_key or not model:
        raise RuntimeError("Configure OPENAI_API_KEY and OPENAI_MODEL in the environment to enable live recommendations.")
    endpoint=os.getenv("OPENAI_RESPONSES_URL", DEFAULT_URL).strip() or DEFAULT_URL
    allowed_refs=context.get("allowed_evidence_refs", [])
    prompt=(
        "You are drafting one proposed delivery-assurance action for a synthetic contest demonstration. "
        "Use only the supplied synthetic facts. Do not infer an unobserved cause or invent evidence. "
        "Return a single JSON object with keys: title, rationale, owner_role, horizon_days, expected_outcome, "
        "success_measure, priority, confidence, evidence_refs, assumptions. "
        "owner_role must be exactly one of: " + ", ".join(sorted(ALLOWED_OWNER_ROLES)) + ". "
        "horizon_days must be 30, 60, or 90. priority must be Critical, High, Medium, or Low. "
        "evidence_refs must contain only IDs from the allowed list and must include at least one ID. "
        "Separate observed facts from hypotheses in rationale. If evidence is insufficient, say so and recommend evidence collection. "
        "The human must review this draft; do not state that an action has been assigned.\n\n"
        "Allowed evidence IDs: " + json.dumps(allowed_refs, ensure_ascii=False) + "\n"
        "Synthetic engagement context:\n" + json.dumps(context, ensure_ascii=False, default=str)
    )
    payload={"model":model,"input":prompt,"store":False}
    request=urllib.request.Request(endpoint, data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization":f"Bearer {api_key}","Content-Type":"application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=50) as response:
            body=json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail=exc.read().decode("utf-8",errors="replace")[:600]
        raise RuntimeError(f"AI provider returned HTTP {exc.code}: {detail}") from exc
    except Exception as exc:
        raise RuntimeError(f"AI provider request failed: {exc}") from exc
    text=_extract_text(body)
    if not text: raise RuntimeError("The model response did not contain output text.")
    try:
        result=json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("The model response was not valid JSON. No recommendation was saved.") from exc
    required={"title","rationale","owner_role","horizon_days","expected_outcome","success_measure","priority","confidence","evidence_refs","assumptions"}
    missing=required-set(result)
    if missing: raise RuntimeError("The model response is missing required fields: " + ", ".join(sorted(missing)))
    if result["owner_role"] not in ALLOWED_OWNER_ROLES: raise RuntimeError("The model returned an owner role outside the approved role list.")
    try: result["horizon_days"]=int(result["horizon_days"])
    except Exception as exc: raise RuntimeError("The model returned an invalid action horizon.") from exc
    if result["horizon_days"] not in ALLOWED_HORIZONS: raise RuntimeError("The model returned a horizon other than 30, 60, or 90 days.")
    if result["priority"] not in ALLOWED_PRIORITIES: raise RuntimeError("The model returned an invalid priority.")
    refs=result["evidence_refs"]
    if not isinstance(refs,list) or not refs or any(ref not in allowed_refs for ref in refs):
        raise RuntimeError("The model cited evidence outside the engagement context; no recommendation was saved.")
    for key in ("title","rationale","expected_outcome","success_measure","confidence"):
        if not isinstance(result[key],str) or not result[key].strip(): raise RuntimeError(f"The model returned an empty {key} field.")
    if not isinstance(result["assumptions"],list): result["assumptions"]=[str(result["assumptions"])]
    result["model"] = model
    return result
