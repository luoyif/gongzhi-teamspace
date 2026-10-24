"""Official OpenCode Go model catalogue and multi-protocol model construction.
Catalogue is generated from the dated official endpoint table, not invented aliases.
"""
from pathlib import Path
import json
from .store import Problem
CATALOG_PATH=Path(__file__).parent/'catalogs/opencode-go.json'
def catalog():
 return json.loads(CATALOG_PATH.read_text(encoding='utf8'))
def model_info(id):
 return next((m for m in catalog()['items'] if m['id']==id.removeprefix('opencode-go/')),None) if isinstance(id,str) else None
def is_go_url(url):
 from urllib.parse import urlsplit
 u=urlsplit(url or '')
 return u.scheme=='https' and u.netloc.lower()=='opencode.ai' and not u.query and not u.fragment and u.path.rstrip('/') in ('/zen/go/v1','/inference/go/v1','/inference/go/openai/v1','/inference/go/anthropic','/inference/go/anthropic/v1','/inference/go/google','/inference/go/google/v1beta')
def protocol_config(base_url,model):
 info=model_info(model) if is_go_url(base_url) else None
 return (info['protocol'],info['base_url']) if info else ('chat',base_url)
def safe_model_payload(value):
 # Provider private reasoning/signatures are neither UI trace nor exported data.
 if isinstance(value,dict):
  if value.get('type') in ('thinking','reasoning','redacted_thinking'):return {'type':value['type'],'omitted':True}
  return {k:safe_model_payload(v) for k,v in value.items() if k not in ('reasoning_content','thinking','encrypted_content','thoughtSignature','signature')}
 if isinstance(value,list):return [safe_model_payload(x) for x in value]
 return value

def build_google(provider,model,cap,transport):
 from langchain_google_genai import ChatGoogleGenerativeAI
 from google.genai import Client,types
 chat=ChatGoogleGenerativeAI(model=model,google_api_key=provider.api_key,base_url=provider.base_url,api_version='v1beta',additional_headers=provider.headers,max_output_tokens=cap,max_retries=0,timeout=120,include_thoughts=False)
 # Inject the same per-run transport used by other protocols for request auditing.
 # HttpOptions is a public SDK boundary, and retries are explicitly one attempt.
 old=chat.client
 options=types.HttpOptions(base_url=provider.base_url,api_version='v1beta',headers=provider.headers,timeout=120000,retry_options=types.HttpRetryOptions(attempts=1),httpx_async_client=transport)
 chat.client=Client(api_key=provider.api_key,http_options=options)
 try:old.close()
 except Exception:pass
 return chat
