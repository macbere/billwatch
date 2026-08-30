"""BillWatch public web application.

The public workflow accepts bill text through POST /investigate, extracts
input-driven facts, evaluates every unique code pair, and reports potential
issues or missing context. It does not expose the old GET endpoint that could
trigger an expensive investigation from a crawler or link preview.
"""

import json
import os
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlsplit

from billwatch.arbitrary_analysis import (
    InputDrivenMockProvider,
    MAX_BILL_TEXT_CHARS,
    MAX_CODES_FOR_PAIR_ANALYSIS,
    analyze_bill,
    parse_analysis_context,
)
from billwatch.reference_bootstrap import load_bootstrap_data
from billwatch.reference_data import ReferenceStore
from billwatch.synthetic_demo import (
    HACKATHON_DEMO_MODE,
    SYNTHETIC_SAMPLE_BILL,
    analyze_synthetic_bill,
)


MAX_REQUEST_BYTES = 200_000
RATE_WINDOW_SECONDS = 60
MAX_REQUESTS_PER_WINDOW = max(
    1,
    int(os.environ.get("BILLWATCH_MAX_REQUESTS_PER_MINUTE", "12")),
)
_rate_lock = threading.Lock()
_request_times = {}


def route_path(raw_path):
    """Return only the path component of a request target."""
    return urlsplit(raw_path).path


def _allow_request(client_ip: str) -> bool:
    now = time.monotonic()
    with _rate_lock:
        recent = [
            timestamp
            for timestamp in _request_times.get(client_ip, [])
            if now - timestamp < RATE_WINDOW_SECONDS
        ]
        if len(recent) >= MAX_REQUESTS_PER_WINDOW:
            _request_times[client_ip] = recent
            return False
        recent.append(now)
        _request_times[client_ip] = recent
        return True


def _provider():
    if os.environ.get("GEMINI_API_KEY"):
        from billwatch.genai_sdk_provider import GenAISDKProvider

        return GenAISDKProvider(), "live"
    return InputDrivenMockProvider(), "offline_mock"


def _request_payload(body: bytes) -> dict:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("request body must be valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("request body must be a JSON object")
    return payload


def _run_analysis(payload: dict) -> dict:
    bill_text = payload.get("bill_text", payload.get("text"))
    if not isinstance(bill_text, str):
        raise ValueError("bill_text is required and must be text")
    if len(bill_text) > MAX_BILL_TEXT_CHARS:
        raise ValueError(f"bill_text exceeds the {MAX_BILL_TEXT_CHARS:,}-character limit")

    has_demo_mode = "demo_mode" in payload
    demo_mode = payload.get("demo_mode")
    if has_demo_mode and (
        not isinstance(demo_mode, str) or demo_mode != HACKATHON_DEMO_MODE
    ):
        raise ValueError(
            f"demo_mode must be exactly {HACKATHON_DEMO_MODE!r} when supplied"
        )

    context = parse_analysis_context(payload)
    if has_demo_mode:
        result = analyze_synthetic_bill(
            bill_text,
            context,
            demo_mode=demo_mode,
        )
    else:
        provider, mode = _provider()
        store = ReferenceStore()
        load_bootstrap_data(store)
        result = analyze_bill(bill_text, context, provider, store, gemini_mode=mode)
    output = result.to_dict()
    output["request_id"] = str(uuid.uuid4())
    output["limits"] = {
        "max_bill_text_chars": MAX_BILL_TEXT_CHARS,
        "max_codes_for_pair_analysis": MAX_CODES_FOR_PAIR_ANALYSIS,
        "max_requests_per_minute": MAX_REQUESTS_PER_WINDOW,
    }
    return output


INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>BillWatch — Evidence-grounded bill review</title>
<style>
:root{--bg:#09111f;--panel:#111d30;--panel2:#0d1727;--border:#26364e;--text:#eaf0f7;--muted:#9aa9bd;--accent:#416fce;--teal:#55c3b5;--warn:#e7ad57;--bad:#df7777;--good:#62c697;--radius:12px}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font-family:system-ui,-apple-system,"Segoe UI",sans-serif;line-height:1.55}.wrap{max-width:900px;margin:0 auto;padding:0 20px}header{border-bottom:1px solid var(--border);background:#0a1424;position:sticky;top:0;z-index:5}.nav{max-width:900px;margin:auto;padding:15px 20px;display:flex;justify-content:space-between;align-items:center}.brand{border:0;background:none;color:var(--text);font:inherit;font-weight:700;font-size:17px;cursor:pointer}.tagline{font-size:12px;color:var(--muted)}section{margin:30px 0}.hero{text-align:center;padding:54px 0 28px}.eyebrow,.kicker{color:var(--teal);font-size:11px;letter-spacing:.12em;text-transform:uppercase;font-weight:700}.hero h1{font-size:clamp(30px,5vw,46px);line-height:1.12;margin:13px 0;color:#f8fbff}.hero h1 em{font-style:normal;color:var(--accent)}.hero p{max-width:650px;margin:0 auto;color:var(--muted);font-size:16px}.card{background:var(--panel);border:1px solid var(--border);border-radius:var(--radius);padding:25px}.card h2{margin:5px 0 8px;font-size:21px}.muted{color:var(--muted)}.notice{border:1px solid #315f72;background:#102537;border-radius:10px;padding:14px 16px;margin:16px 0}.notice strong{color:#b9f1e8}.demo-card{border-color:#2e6a68;background:#10252d}.demo-label{display:inline-block;color:#b9f1e8;background:#173e3d;border:1px solid #2e6a68;border-radius:999px;padding:5px 9px;font-size:11px;font-weight:750;text-transform:uppercase;letter-spacing:.06em}.pause-card{border:1px solid #477d83;background:#112b36;border-radius:10px;padding:18px;margin-top:18px}.pause-card h3{margin:0 0 6px}.resume-field{padding:12px 0;border-top:1px solid #284553}.resume-field:first-child{border-top:0}.source-lock{color:#b9f1e8;font-size:12px}.timeline{margin:18px 0;padding:16px;background:var(--panel2);border:1px solid var(--border);border-radius:10px}.timeline h3{margin:0 0 10px}.timeline ol{margin:0;padding-left:22px}.timeline-item{padding:5px 0;color:var(--muted)}.timeline-item.human{color:#b9f1e8}.processing{color:var(--teal);font-size:13px;font-weight:650}details{margin:9px 0;padding:10px 12px;border:1px solid var(--border);border-radius:8px;background:var(--panel2)}summary{cursor:pointer;font-weight:650}label{display:block;color:#dce6f3;font-size:13px;font-weight:650;margin:15px 0 7px}textarea,input,select{width:100%;background:var(--panel2);color:var(--text);border:1px solid var(--border);border-radius:8px;padding:12px;font:inherit}textarea{min-height:190px;resize:vertical}input[type=file]{padding:10px}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 16px}.checks{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:12px}.check{display:flex;gap:8px;align-items:center;background:var(--panel2);border:1px solid var(--border);border-radius:8px;padding:11px;font-size:13px;font-weight:500}.check input{width:auto}.buttons{display:flex;gap:10px;flex-wrap:wrap;margin-top:18px}button.primary,button.secondary{border-radius:8px;padding:12px 17px;font:inherit;font-weight:700;cursor:pointer}button.primary{background:var(--accent);border:1px solid var(--accent);color:white}button.secondary{background:transparent;border:1px solid var(--border);color:var(--text)}button:disabled{opacity:.55;cursor:wait}button:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible,summary:focus-visible{outline:2px solid var(--teal);outline-offset:2px}.examples{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}.examples button{font-size:12px;padding:8px 11px}.badge{display:inline-block;padding:7px 11px;border-radius:7px;font-size:12px;font-weight:750}.badge.good{color:var(--good);background:#15372c}.badge.warn{color:var(--warn);background:#3d2d16}.badge.bad{color:var(--bad);background:#402222}.finding{border:1px solid var(--border);border-left:3px solid var(--warn);border-radius:8px;padding:15px;margin-top:11px;background:var(--panel2)}.finding.no{border-left-color:var(--teal)}.finding h3{font-size:15px;margin:0 0 6px}.finding p{margin:5px 0;color:var(--muted);font-size:13px}.finding code,.fact code{background:#17243a;border-radius:4px;padding:2px 5px}.fact{padding:9px 0;border-bottom:1px solid var(--border);font-size:13px}.fact:last-child{border-bottom:0}.small{font-size:12px;color:var(--muted)}.error{color:var(--bad);margin-top:12px}.review{margin-top:16px;border:1px solid #806331;background:#302817;padding:15px;border-radius:8px}.hidden{display:none}footer{text-align:center;color:var(--muted);font-size:12px;padding:25px 0 50px;border-top:1px solid var(--border)}@media(max-width:620px){.grid,.checks{grid-template-columns:1fr}.hero{padding-top:38px}.card{padding:19px}}
.approval-card{border:1px solid #477d83;background:#102733}.approval-card h3{margin:6px 0}.approval-card .decision{color:#b9f1e8;font-weight:650}
</style>
</head>
<body>
<header><div class="nav"><button type="button" id="brandBtn" class="brand">▣ BillWatch</button><span class="tagline">All Things Agentic Hackathon</span></div></header>
<main class="wrap">
<section class="hero"><div class="eyebrow">Evidence-grounded bill review</div><h1>Understand a bill<br><em>before you pay.</em></h1><p>Paste or upload bill text. BillWatch extracts the facts it can prove, checks every code pair, asks for missing context, and reports potential issues for human review.</p></section>
<section class="card" id="investigation"><div class="kicker">1 · Submit a bill</div><h2>Analyze your bill</h2><div class="notice" id="sessionNotice"><strong>Active browser tab only.</strong> Investigation progress stays in this page's temporary memory. Closing or refreshing this tab clears the investigation. Raw bill text is processed transiently and is not stored or logged by BillWatch's server.</div><p class="muted">Use pasted text or choose a TXT, CSV, or JSON file. BillWatch provides evidence-grounded review support, not medical, legal, insurance, coding, or payment advice.</p><form id="analysisForm"><label for="billText">Bill text</label><textarea id="billText" name="bill_text" required placeholder="Example: Itemized bill\nCPT 99213 — Office visit — $180.00\nCPT 45378 — Procedure — $400.00"></textarea><label for="fileInput">Or choose a file</label><input id="fileInput" type="file" accept=".txt,.csv,.json,text/plain,application/json,text/csv"><div class="examples"><button type="button" class="secondary" data-action="example" data-example="multi">Load multi-code example</button><button type="button" class="secondary" data-action="example" data-example="context">Load missing-context example</button><button type="button" class="secondary" data-action="example" data-example="clean">Load no-match example</button></div><div id="initialContextControls"><div class="grid"><div><label for="payerScope">Payer/program</label><select id="payerScope"><option value="unknown">Not sure yet</option><option value="medicare">Medicare</option><option value="medicaid">Medicaid</option><option value="private_commercial">Private/commercial plan</option></select></div><div><label for="serviceDate">Service date, if known</label><input id="serviceDate" type="date"></div><div><label for="modifiers">Modifiers, if shown</label><input id="modifiers" placeholder="Example: 25, 59"></div><div><label for="claimStatus">Claim/EOB status, if known</label><input id="claimStatus" placeholder="Example: denied, paid, pending"></div></div><div class="checks"><label class="check"><input id="sameDate" type="checkbox"> Same date of service confirmed</label><label class="check"><input id="sameBeneficiary" type="checkbox"> Same beneficiary/claim confirmed</label></div></div><div class="buttons"><button type="submit" class="primary" id="runDemoBtn">Analyze Bill</button><button type="button" class="secondary" id="howBtn">How this works</button></div><div id="formError" class="error hidden" role="alert"></div></form></section>
<section class="card demo-card" id="hackathonDemoCard"><span class="demo-label">Hackathon Demo · synthetic</span><h2>Try the guided pause-and-resume example</h2><p class="muted">This example and its single rule are author-written and synthetic. <strong>BW-DEMO-001</strong> and <strong>BW-DEMO-002</strong> are demonstration identifiers, not CPT or HCPCS codes and not CMS, AMA, insurer, payer, or clinical data.</p><button type="button" class="secondary" id="loadDemoBtn">Load synthetic guided example</button></section>
<section class="card hidden" id="resultsCard"><div class="kicker">2 · Evidence report</div><h2 id="resultHeading">Investigation result</h2><p class="processing hidden" id="processingStatus" role="status">Investigation in progress. No unfinished stage is marked complete.</p><div class="timeline hidden" id="timelinePanel"><h3>Investigation timeline</h3><ol id="timelineList"></ol></div><div id="attemptHistory"></div><div id="resultBody" aria-live="polite"></div><div class="pause-card hidden" id="pauseCard"><h3>BillWatch paused instead of guessing</h3><p class="muted">Confirm only the missing context below. The original source is locked so the first attempt remains auditable.</p><div id="resumeFields"></div><p class="source-lock">If a code or source fact is wrong, start a new investigation and correct the original bill text.</p><div class="buttons"><button type="button" class="primary" id="resumeBtn">Resume investigation</button></div><div id="resumeError" class="error hidden" role="alert"></div></div><div class="buttons"><button type="button" class="primary hidden" id="retryBtn">Retry</button><button type="button" class="secondary" id="startNewBtn">Start new investigation</button></div></section>
<section class="card approval-card hidden" id="approvalCard"><span class="demo-label">Simulated approval · browser only</span><h3>Proposed next step: prepare a question for human review</h3><p class="muted">This finding is not proof that the bill is incorrect. Choose whether this simulated next step should be approved or rejected.</p><div class="buttons" id="approvalButtons"><button type="button" class="primary" id="approveBtn">Approve simulated step</button><button type="button" class="secondary" id="rejectBtn">Reject simulated step</button></div><p class="decision hidden" id="approvalMessage" role="status"></p><p class="small">Nothing is transmitted, downloaded, copied, published, or sent by either choice.</p></section>
<section class="card" id="how"><div class="kicker">How BillWatch works</div><h2>AI assists; evidence controls the result</h2><p class="muted">Gemini may help extract literal bill facts. Deterministic code validates source spans, evaluates every unique code pair, separates payer programs, records missing context, and prevents an unsupported appeal from being presented as fact.</p></section>
</main><footer>BillWatch · results are for human review and are not medical, legal, or insurance advice.</footer>
<script>
(function(){"use strict";
var examples={
  multi:"Itemized bill\\nCPT 45378 — Diagnostic procedure — $400.00\\nCPT 45380 — Procedure with biopsy — $600.00\\nCPT 99213 — Office visit — $180.00\\nService date: 2026-08-01",
  context:"Itemized bill\\nCPT 45378 — Procedure — $400.00\\nCPT 45380 — Procedure with biopsy — $600.00",
  clean:"Itemized bill\\nCPT 99213 — Office visit — $180.00\\nCPT 93000 — Test — $75.00"
};
var HACKATHON_DEMO_MODE="hackathon_synthetic_v1";
var MAX_BILL_TEXT_CHARS=100000;
var RESUMABLE_FIELDS=["payer_scope","service_date","modifiers","same_date_confirmed","same_beneficiary_confirmed","claim_status"];
var syntheticDemoText="BILLWATCH HACKATHON DEMO - AUTHOR-WRITTEN SYNTHETIC CONTENT\\nDemo identifier BW-DEMO-001 - synthetic review item - $40.00\\nDemo identifier BW-DEMO-002 - synthetic review item - $25.00\\nThese are demonstration identifiers, not medical billing codes.";
var investigation=null;
var selectedMode="standard";
var processing=false;
var form=document.getElementById("analysisForm"), text=document.getElementById("billText"), file=document.getElementById("fileInput"), results=document.getElementById("resultsCard"), body=document.getElementById("resultBody"), attemptHistory=document.getElementById("attemptHistory"), heading=document.getElementById("resultHeading"), error=document.getElementById("formError"), pauseCard=document.getElementById("pauseCard"), resumeFields=document.getElementById("resumeFields"), resumeBtn=document.getElementById("resumeBtn"), resumeError=document.getElementById("resumeError"), timelinePanel=document.getElementById("timelinePanel"), timelineList=document.getElementById("timelineList"), processingStatus=document.getElementById("processingStatus"), retryBtn=document.getElementById("retryBtn"), approvalCard=document.getElementById("approvalCard"), approvalButtons=document.getElementById("approvalButtons"), approvalMessage=document.getElementById("approvalMessage"), approveBtn=document.getElementById("approveBtn"), rejectBtn=document.getElementById("rejectBtn");
function readInitialContext(){return{payer_scope:document.getElementById("payerScope").value,service_date:document.getElementById("serviceDate").value||null,modifiers:document.getElementById("modifiers").value,same_date_confirmed:document.getElementById("sameDate").checked?true:null,same_beneficiary_confirmed:document.getElementById("sameBeneficiary").checked?true:null,claim_status:document.getElementById("claimStatus").value||null};}
function copyContext(value){return JSON.parse(JSON.stringify(value));}
function emptyInvestigation(){var context=readInitialContext();return{id:null,mode:selectedMode,billText:text.value,initialContext:copyContext(context),currentContext:copyContext(context),attempts:[],timeline:[],state:"running",approvalDecision:null};}
var STAGE_LABELS={bill_received:"Bill received",facts_extracted:"Facts extracted with source evidence",pairs_generated:"Unique code pairs generated",references_checked:"Bounded references checked",context_evaluated:"Applicability context evaluated"};
function renderTimeline(){if(!investigation||!investigation.timeline.length){timelinePanel.classList.add("hidden");timelineList.innerHTML="";return;}timelineList.innerHTML=investigation.timeline.map(function(event){var actor=event.actor==="human"?"human":"automatic";return'<li class="timeline-item '+actor+'"><strong>'+(actor==="human"?"Human":"BillWatch")+':</strong> '+esc(event.label)+'</li>';}).join("");timelinePanel.classList.remove("hidden");}
function appendTimeline(actor,type,label){if(!investigation)return;investigation.timeline.push({actor:actor,type:type,label:label});renderTimeline();}
function appendCompletedStages(data,attemptNumber){(data.completed_stages||[]).forEach(function(stage){appendTimeline("automatic","stage_completed",(STAGE_LABELS[stage]||stage)+" · attempt "+attemptNumber);});}
function confirmClearInvestigation(){return !investigation||window.confirm("Clear the current active-tab investigation and its timeline?");}
function setSourceLocked(locked){text.disabled=locked;file.disabled=locked;document.querySelectorAll("#initialContextControls input,#initialContextControls select,.examples button").forEach(function(control){control.disabled=locked;});}
function resetInvestigation(){investigation=null;selectedMode="standard";processing=false;text.value="";file.value="";document.getElementById("payerScope").value="unknown";document.getElementById("serviceDate").value="";document.getElementById("modifiers").value="";document.getElementById("claimStatus").value="";document.getElementById("sameDate").checked=false;document.getElementById("sameBeneficiary").checked=false;setSourceLocked(false);pauseCard.classList.add("hidden");resumeFields.innerHTML="";results.classList.add("hidden");attemptHistory.innerHTML="";timelineList.innerHTML="";timelinePanel.classList.add("hidden");processingStatus.classList.add("hidden");retryBtn.classList.add("hidden");approvalCard.classList.add("hidden");approvalButtons.classList.remove("hidden");approvalMessage.classList.add("hidden");approvalMessage.textContent="";body.innerHTML="";clearError();clearResumeError();}
function esc(value){return String(value==null?"":value).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/\"/g,"&quot;");}
function showError(message){error.textContent=message;error.classList.remove("hidden");}
function clearError(){error.textContent="";error.classList.add("hidden");}
function showResumeError(message){resumeError.textContent=message;resumeError.classList.remove("hidden");}
function clearResumeError(){resumeError.textContent="";resumeError.classList.add("hidden");}
function statusClass(status){return status.indexOf("POTENTIAL")>=0?"warn":(status.indexOf("INSUFFICIENT")>=0||status.indexOf("CONFLICT")>=0?"bad":"good");}
function render(data){
  results.classList.remove("hidden");
  heading.textContent=data.success?"Evidence-grounded result":"Investigation could not be completed";
  if(!data.success){body.innerHTML='<div class="badge bad">Unable to complete</div><p><strong>The investigation did not finish.</strong> No unfinished stage is presented as complete.</p><p class="error">'+esc(data.failure_reason||data.error||"Please check the bill and try again.")+'</p>';return;}
  var html='<div class="badge '+statusClass(data.status)+'">'+esc(data.status.replaceAll("_"," "))+'</div>';
  html+='<p class="small">Mode: '+esc(data.gemini_mode)+' · Request: '+esc(data.request_id||"")+'</p>';
  var facts=data.facts||[];
  html+='<h3>Extracted facts</h3>';
  if(!facts.length){html+='<p class="muted">No supported facts were extracted.</p>';}else{facts.forEach(function(f){html+='<div class="fact"><strong>'+esc(f.fact_type)+'</strong>: <code>'+esc(f.value)+'</code> <span class="small">source: '+esc(f.source_span||"")+'</span></div>';});}
  html+='<h3>Code-pair findings</h3>';
  var findings=data.findings||[];
  if(!findings.length){html+='<p class="muted">No code pair was available to evaluate.</p>';}else{findings.forEach(function(f){var cls=f.status==="NO_MATCHING_RULE"?"finding no":"finding";html+='<div class="'+cls+'"><h3><code>'+esc(f.code_a)+'</code> + <code>'+esc(f.code_b)+'</code> · '+esc(f.status.replaceAll("_"," "))+'</h3><p>'+esc(f.summary)+'</p>';if(f.missing_context&&f.missing_context.length){html+='<p><strong>Still needed:</strong> '+esc(f.missing_context.join("; "))+'</p>';}if(f.reference){html+='<p class="small">Reference: '+esc(f.reference.dataset||"")+' / '+esc(f.reference.version||"unavailable")+' · effective '+esc(f.reference.effective_date||"unknown")+' · verification '+esc(String(f.reference.relationship_verified))+'</p>'; }html+='</div>';});}
  if(data.missing_context&&data.missing_context.length){html+='<div class="review"><strong>Missing context</strong><p>'+esc(data.missing_context.join("; "))+'</p></div>';}
  if(data.review_note&&data.analysis_mode!==HACKATHON_DEMO_MODE){html+='<div class="review"><strong>Human-review draft</strong><p id="reviewNote">'+esc(data.review_note)+'</p><div class="buttons"><button type="button" class="secondary" data-action="copy">Copy summary</button><button type="button" class="secondary" data-action="download">Download summary</button></div></div>';}
  body.innerHTML=html;
}
function latestResponse(){if(!investigation||!investigation.attempts.length)return null;return investigation.attempts[investigation.attempts.length-1].response;}
function renderApproval(data){var eligible=!!(data&&data.success&&data.status==="POTENTIAL_DISCREPANCY");approvalCard.classList.toggle("hidden",!eligible);if(!eligible){approvalButtons.classList.remove("hidden");approvalMessage.classList.add("hidden");approvalMessage.textContent="";return;}var decision=investigation&&investigation.approvalDecision;if(!decision){approvalButtons.classList.remove("hidden");approvalMessage.classList.add("hidden");approvalMessage.textContent="";return;}approvalButtons.classList.add("hidden");approvalMessage.textContent=(decision==="approved"?"Approved":"Rejected")+" in this browser tab. Nothing was sent.";approvalMessage.classList.remove("hidden");}
function recordApprovalDecision(decision){var data=latestResponse();if(!investigation||investigation.approvalDecision||!data||!data.success||data.status!=="POTENTIAL_DISCREPANCY")return;investigation.approvalDecision=decision;appendTimeline("human","approval_decision","Human "+(decision==="approved"?"approved":"rejected")+" the simulated next step; nothing was sent");renderApproval(data);}
function attemptMissingContext(data){var items=(data.missing_context||[]).slice();(data.findings||[]).forEach(function(finding){(finding.missing_context||[]).forEach(function(item){if(items.indexOf(item)<0)items.push(item);});});return items;}
function renderAttemptHistory(){var prior=investigation.attempts.slice(0,-1);if(!prior.length){attemptHistory.innerHTML="";return;}var html='<h3>Earlier attempts</h3>';prior.forEach(function(attempt,index){var data=attempt.response||{},status=data.status||"DID_NOT_FINISH",requestId=data.request_id||"no request ID",missing=attemptMissingContext(data).join("; ");html+='<details><summary>Attempt '+(index+1)+' · '+esc(status.replaceAll("_"," "))+'</summary><p class="small">Request: '+esc(requestId)+'</p>';if(missing)html+='<p><strong>Why BillWatch paused:</strong> '+esc(missing)+'</p>';if(attempt.error)html+='<p><strong>Failure:</strong> '+esc(attempt.error.message)+'</p>';html+='</details>';});attemptHistory.innerHTML=html;}
function resumeControl(item){
  var field=item.field,id="resume_"+field,label='<label for="'+id+'">'+esc(item.label)+'</label><p class="small">'+esc(item.reason)+'</p>';
  if(field==="payer_scope")return'<div class="resume-field" data-resume-field="'+field+'">'+label+'<select id="'+id+'"><option value="unknown">Select payer/program</option><option value="medicare">Medicare</option><option value="medicaid">Medicaid</option><option value="private_commercial">Private/commercial plan</option></select></div>';
  if(field==="service_date")return'<div class="resume-field" data-resume-field="'+field+'">'+label+'<input id="'+id+'" type="date"></div>';
  if(field==="same_date_confirmed"||field==="same_beneficiary_confirmed")return'<div class="resume-field" data-resume-field="'+field+'"><label class="check"><input id="'+id+'" type="checkbox"> '+esc(item.label)+'</label><p class="small">'+esc(item.reason)+'</p></div>';
  return'<div class="resume-field" data-resume-field="'+field+'">'+label+'<input id="'+id+'" type="text"></div>';
}
function renderResume(data){
  var fields=(data.missing_context_fields||[]).filter(function(item){return RESUMABLE_FIELDS.indexOf(item.field)>=0;});
  if(!data.can_resume||!fields.length){pauseCard.classList.add("hidden");return;}
  resumeFields.innerHTML=fields.map(resumeControl).join("");
  pauseCard.classList.remove("hidden");
  setSourceLocked(true);
  resumeBtn.disabled=false;
}
function collectResumeContext(){
  var next=copyContext(investigation.currentContext),confirmed=[];
  var rows=resumeFields.querySelectorAll("[data-resume-field]");
  for(var i=0;i<rows.length;i+=1){
    var field=rows[i].getAttribute("data-resume-field"),control=document.getElementById("resume_"+field),value;
    if(field==="same_date_confirmed"||field==="same_beneficiary_confirmed"){if(!control.checked)return{error:"Please confirm each requested relationship before resuming."};value=true;}
    else{value=control.value.trim();if(!value||field==="payer_scope"&&value==="unknown")return{error:"Please complete each requested item before resuming."};}
    next[field]=value;confirmed.push(field);
  }
  return{context:next,confirmed:confirmed};
}
function payloadForInvestigation(){var context=investigation.currentContext;var payload={bill_text:investigation.billText,payer_scope:context.payer_scope,service_date:context.service_date,modifiers:context.modifiers,same_date_confirmed:context.same_date_confirmed,same_beneficiary_confirmed:context.same_beneficiary_confirmed,claim_status:context.claim_status};if(investigation.mode===HACKATHON_DEMO_MODE)payload.demo_mode=HACKATHON_DEMO_MODE;return payload;}
async function postInvestigation(payload){var response=await fetch("/investigate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});var data=await response.json();if(!response.ok){var failure=new Error(data.message||"The investigation could not be completed.");failure.payload=data;throw failure;}return data;}
function setProcessing(active){processing=active;var runButton=document.getElementById("runDemoBtn");runButton.disabled=active;runButton.textContent=active?"Analyzing...":"Analyze Bill";resumeBtn.disabled=active;retryBtn.disabled=active;processingStatus.classList.toggle("hidden",!active);}
async function runAttempt(kind){
  if(processing)return;
  results.classList.remove("hidden");retryBtn.classList.add("hidden");approvalCard.classList.add("hidden");setProcessing(true);clearError();clearResumeError();
  var payload=payloadForInvestigation(),attemptNumber=investigation.attempts.length+1,attempt={kind:kind,context:copyContext(investigation.currentContext),response:null,error:null};appendTimeline("automatic","attempt_started","Attempt "+attemptNumber+" started");
  try{
    var data=await postInvestigation(payload);attempt.response=data;investigation.attempts.push(attempt);if(!investigation.id)investigation.id=data.request_id;appendCompletedStages(data,attemptNumber);
    if(!data.success){investigation.state="failed";appendTimeline("automatic","attempt_failed","Attempt "+attemptNumber+" did not finish");pauseCard.classList.add("hidden");renderAttemptHistory();render(data);retryBtn.classList.remove("hidden");results.scrollIntoView({behavior:"smooth",block:"start"});return;}
    investigation.state=data.can_resume?"paused":"completed";appendTimeline("automatic",data.can_resume?"investigation_paused":"final_result",data.can_resume?"Investigation paused for human context":"Final bounded result produced");renderAttemptHistory();render(data);renderResume(data);renderApproval(data);if(!data.can_resume)setSourceLocked(true);results.scrollIntoView({behavior:"smooth",block:"start"});
  }catch(failure){var failureData=failure.payload||{};attempt.error={message:failure.message,payload:failure.payload||null};investigation.attempts.push(attempt);appendCompletedStages(failureData,attemptNumber);investigation.state="failed";appendTimeline("automatic","attempt_failed","Attempt "+attemptNumber+" did not finish");pauseCard.classList.add("hidden");renderAttemptHistory();render({success:false,error:"investigation_failed",failure_reason:failure.message});retryBtn.classList.remove("hidden");results.scrollIntoView({behavior:"smooth",block:"start"});}
  finally{setProcessing(false);}
}
file.addEventListener("change",function(){var selected=file.files&&file.files[0];if(!selected)return;if(!/\\.(txt|csv|json)$/i.test(selected.name)){showError("Supported file types are TXT, CSV, and JSON.");file.value="";return;}if(selected.size>200000){showError("That file is too large. Please use a file under 200 KB.");file.value="";return;}selectedMode="standard";var reader=new FileReader();reader.onload=function(){var content=String(reader.result||"");if(content.length>MAX_BILL_TEXT_CHARS){showError("That file contains too much text. Please use no more than 100,000 characters.");text.value="";file.value="";return;}text.value=content;clearError();};reader.onerror=function(){showError("The file could not be read.");};reader.readAsText(selected);});
form.addEventListener("submit",function(event){event.preventDefault();if(processing)return;clearError();if(!text.value.trim()){showError("Please paste bill text or choose a file first.");return;}if(text.value.length>MAX_BILL_TEXT_CHARS){showError("That bill contains too much text. Please use no more than 100,000 characters.");return;}if(!investigation)investigation=emptyInvestigation();runAttempt("initial");});
resumeBtn.addEventListener("click",function(){if(processing)return;if(!investigation||investigation.state!=="paused")return;clearResumeError();var update=collectResumeContext();if(update.error){showResumeError(update.error);return;}investigation.currentContext=update.context;appendTimeline("human","context_supplied","Human confirmed: "+update.confirmed.join(", "));appendTimeline("automatic","analysis_resumed","Analysis resumed with human-confirmed context");runAttempt("resume");});
retryBtn.addEventListener("click",function(){if(processing)return;if(!investigation||investigation.state!=="failed")return;appendTimeline("human","retry_requested","Human requested a retry");runAttempt("retry");});
approveBtn.addEventListener("click",function(){recordApprovalDecision("approved");});
rejectBtn.addEventListener("click",function(){recordApprovalDecision("rejected");});
document.addEventListener("click",function(event){var target=event.target.closest?event.target.closest("[data-action]"):null;if(!target)return;var action=target.getAttribute("data-action");if(action==="example"){text.value=examples[target.getAttribute("data-example")]||"";document.getElementById("payerScope").value="unknown";document.getElementById("serviceDate").value="";document.getElementById("sameDate").checked=false;document.getElementById("sameBeneficiary").checked=false;clearError();text.focus();}if(action==="copy"){var note=document.getElementById("reviewNote");if(note&&navigator.clipboard)navigator.clipboard.writeText(note.innerText);}if(action==="download"){var note=document.getElementById("reviewNote");if(note){var link=document.createElement("a");link.href=URL.createObjectURL(new Blob([note.innerText],{type:"text/plain"}));link.download="billwatch-human-review-summary.txt";link.click();URL.revokeObjectURL(link.href);}}});
document.getElementById("loadDemoBtn").addEventListener("click",function(){if(!confirmClearInvestigation())return;resetInvestigation();selectedMode=HACKATHON_DEMO_MODE;text.value=syntheticDemoText;clearError();text.focus();});
document.getElementById("startNewBtn").addEventListener("click",function(){if(!confirmClearInvestigation())return;resetInvestigation();text.focus();});
document.getElementById("brandBtn").addEventListener("click",function(){window.scrollTo({top:0,behavior:"smooth"});});document.getElementById("howBtn").addEventListener("click",function(){document.getElementById("how").scrollIntoView({behavior:"smooth"});});
})();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _write_body(self, body):
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            # Browsers may cancel an in-flight response while navigating or
            # refreshing. That is a normal client disconnect, not an app crash.
            self.close_connection = True

    def _send_json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self._write_body(body)

    def _send_html(self, code, html):
        body = html.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'self'")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self._write_body(body)

    def do_GET(self):
        path = route_path(self.path)
        if path == "/":
            self._send_html(200, INDEX_HTML)
        elif path == "/health":
            self._send_json(200, {"status": "ok", "service": "billwatch", "mode": "live" if os.environ.get("GEMINI_API_KEY") else "offline_mock"})
        elif path == "/investigate":
            self.send_response(405)
            self.send_header("Allow", "POST")
            self.send_header("Content-Length", "0")
            self.end_headers()
        else:
            self._send_json(404, {"error": "not_found"})

    def do_POST(self):
        if route_path(self.path) != "/investigate":
            self._send_json(404, {"error": "not_found"})
            return
        client_ip = self.client_address[0]
        if not _allow_request(client_ip):
            self._send_json(429, {"error": "rate_limited", "message": "Too many investigations. Please wait and try again."})
            return
        try:
            content_length = int(self.headers.get("Content-Length", "-1"))
        except ValueError:
            content_length = -1
        if content_length < 0:
            self._send_json(411, {"error": "content_length_required"})
            return
        if content_length > MAX_REQUEST_BYTES:
            # Consume a bounded prefix before replying so local clients do not
            # see a reset connection while the request body is still arriving.
            self.rfile.read(MAX_REQUEST_BYTES + 1)
            self._send_json(413, {"error": "request_too_large", "message": "The request is too large."})
            return
        body = self.rfile.read(content_length)
        try:
            result = _run_analysis(_request_payload(body))
        except ValueError as exc:
            self._send_json(400, {"error": "invalid_request", "message": str(exc)})
            return
        except Exception:
            self._send_json(500, {"error": "investigation_unavailable", "message": "The investigation could not be completed."})
            return
        self._send_json(200, result)

    def log_message(self, format, *args):
        # Bill contents and request headers are intentionally never logged.
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"BillWatch serving on port {port}")
    server.serve_forever()
