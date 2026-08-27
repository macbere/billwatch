"""
BillWatch Cloud Run entrypoint. Stdlib-only HTTP wrapper -- no new
dependency, no reasoning of its own. Calls the existing, unmodified
pipeline.run_investigation() and serializes its result. Uses
GenAISDKProvider if GEMINI_API_KEY is set, otherwise MockLLMProvider,
exactly like demo.py. Supports an optional ?scenario= query parameter
on /investigate ("discrepancy" [default, unchanged existing behavior]
or "clean") reusing the exact fixtures already proven in
demo_scenarios.py -- no new adjudication logic, no new FinalStatus.
"""
import json
import os
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlsplit, parse_qs

from billwatch import Document, Investigation
from billwatch.case_scope import establish_from_user_selection
from billwatch.llm_provider import MockLLMProvider
from billwatch.reference_bootstrap import load_bootstrap_data
from billwatch.reference_data import ReferenceStore
from billwatch.pipeline import run_investigation


def _mock_dispatch_provider(doc):
    def dispatch(system_prompt, user_content):
        if "document-extraction component" in system_prompt:
            facts = [
                {"fact_type": "code", "value": "45378", "source_span": "45378"},
                {"fact_type": "code", "value": "45380", "source_span": "45380"},
            ]
            return json.dumps({"document_id": doc.id, "extracted_facts": facts})
        if "hypothesis-proposal component" in system_prompt:
            fact_ids = re.findall(r"fact_id=([0-9a-fA-F-]+)", user_content)
            return json.dumps({
                "claim_statement": "Possible improper unbundling",
                "explanation_text": "Codes 45378/45380 billed together; NCCI treats these as bundled.",
                "referenced_fact_ids": fact_ids,
            })
        if "verification-planning component" in system_prompt:
            m = re.search(r"hypothesis_id:\s*(\S+)", user_content)
            return json.dumps({
                "hypothesis_id": m.group(1) if m else "",
                "proposed_source_types": ["CMS_NCCI"],
                "verification_rationale": "Check CMS NCCI PTP bundling status.",
            })
        if "appeal-drafting component" in system_prompt:
            m = re.search(r"claim_id:\s*(\S+)", user_content)
            fact_ids = re.findall(r"fact_id=([0-9a-fA-F-]+)", user_content)
            return json.dumps({
                "draft_text": "This is a request for human review of the billing for claim " + (m.group(1) if m else "") + ". Codes 45378 and 45380 were billed together on the same date of service, totaling $500.00. Please review this claim to ensure billing accuracy.",
                "cited_fact_ids": fact_ids,
                "cited_claim_ids": [m.group(1)] if m else [],
            })
        return "{}"
    return MockLLMProvider(response_fn=dispatch)


def _build_document_and_scope(scenario):
    """Reuses the exact fixtures already proven in demo_scenarios.py.
    'discrepancy' is byte-identical to the pre-existing app.py demo bill
    (unchanged default). 'clean' reuses demo_scenarios.py's Scenario 2
    fixture verbatim: a real NCCI-matching bill where case scope was
    never established, so the deterministic Scope gate withholds
    SUPPORTED_DISCREPANCY -- no new status, no new adjudication logic."""
    if scenario == "clean":
        doc = Document(
            doc_type="bill",
            raw_text="Itemized bill: CPT/HCPCS codes 45378 and 45380 billed together. Governing plan/payer type not yet confirmed.",
        )
        case_scope = None
    else:
        doc = Document(
            doc_type="bill",
            raw_text="Itemized bill: CPT/HCPCS codes 45378 and 45380 billed together, same date of service, $500.00 total.",
        )
        case_scope = establish_from_user_selection("medicare")
    return doc, case_scope


def _run_demo_investigation(scenario="discrepancy"):
    doc, case_scope = _build_document_and_scope(scenario)

    if os.environ.get("GEMINI_API_KEY"):
        from billwatch.genai_sdk_provider import GenAISDKProvider
        provider = GenAISDKProvider()
    else:
        provider = _mock_dispatch_provider(doc)

    investigation = Investigation()
    store = ReferenceStore()
    load_bootstrap_data(store)

    result = run_investigation(investigation, [doc], case_scope, provider, store)
    payload = {
        "success": result.success,
        "final_status": result.final_status.value if result.final_status else None,
        "failed_stage": result.failed_stage,
        "appeal_generated": result.appeal.success if result.appeal else False,
        "appeal_draft": result.appeal.draft_text if result.appeal and result.appeal.success else None,
        "gemini_mode": "live" if os.environ.get("GEMINI_API_KEY") else "offline_mock",
    }
    return payload


def route_path(raw_path):
    """Return only the path component of a request target, discarding any
    query string or fragment. '/?utm_source=x' and '/' both route to '/'.
    """
    return urlsplit(raw_path).path


def _scenario_param(raw_path):
    """Extract ?scenario= from the request target. Defaults to
    'discrepancy' (the original, unchanged behavior) for any value other
    than the two explicitly supported demo scenarios."""
    qs = urlsplit(raw_path).query
    values = parse_qs(qs).get("scenario")
    value = values[0] if values else "discrepancy"
    return value if value in ("discrepancy", "clean") else "discrepancy"


INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>BillWatch -- Find billing errors before you pay.</title>
<style>
  :root{
    --bg:#0a0f1a; --panel:#111826; --panel2:#0d1420; --border:#1f2937;
    --border-soft:#182233;
    --text:#e8ecf3; --muted:#8b95a8; --heading:#f4f6fa;
    --accent:#3b6fd6; --accent-soft:#2a4d8f; --teal:#4a9d95;
    --good:#2f9e6e; --good-bg:rgba(47,158,110,.10); --good-border:rgba(47,158,110,.35);
    --bad:#c85a5a; --bad-bg:rgba(200,90,90,.10); --bad-border:rgba(200,90,90,.35);
    --radius:10px; --radius-sm:7px;
  }
  *{box-sizing:border-box;}
  body{margin:0;background:var(--bg);
    color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    line-height:1.6;-webkit-font-smoothing:antialiased;overflow-x:hidden;}
  .wrap{max-width:820px;margin:0 auto;padding:0 20px;}
  header{position:sticky;top:0;z-index:10;background:rgba(10,15,26,.94);backdrop-filter:blur(6px);
    border-bottom:1px solid var(--border-soft);}
  .nav{display:flex;align-items:center;justify-content:space-between;padding:16px 20px;max-width:820px;margin:0 auto;}
  .brand{display:flex;align-items:center;gap:9px;font-weight:600;font-size:16px;letter-spacing:-.01em;
    background:none;border:none;padding:0;font-family:inherit;color:var(--heading);cursor:pointer;}
  .brand .mark{width:22px;height:22px;border-radius:6px;background:var(--accent);display:flex;
    align-items:center;justify-content:center;color:#fff;font-size:12px;font-weight:700;flex-shrink:0;}
  .tagline{color:var(--muted);font-size:12px;font-weight:500;letter-spacing:.02em;}
  .hero{padding:64px 0 36px;text-align:center;}
  .eyebrow{color:var(--teal);font-size:12px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;margin-bottom:16px;}
  .hero h1{font-size:clamp(30px,5.5vw,42px);line-height:1.18;margin:0 0 16px;letter-spacing:-.02em;color:var(--heading);
    font-weight:700;}
  .hero h1 em{color:var(--accent);font-style:normal;}
  .hero p{color:var(--muted);font-size:16px;max-width:480px;margin:0 auto 30px;line-height:1.65;}
  .cta-row{display:flex;gap:12px;justify-content:center;flex-wrap:wrap;}
  button.primary{background:var(--accent);color:#fff;border:1px solid var(--accent);padding:13px 22px;border-radius:var(--radius-sm);
    font-size:14.5px;font-weight:600;cursor:pointer;transition:background .15s,border-color .15s;min-height:48px;}
  button.primary:hover{background:#4d7fe0;}
  button.primary:disabled{opacity:.55;cursor:default;}
  button.ghost{background:transparent;color:var(--text);border:1px solid var(--border);padding:13px 22px;
    border-radius:var(--radius-sm);font-size:14.5px;font-weight:600;cursor:pointer;min-height:48px;transition:border-color .15s;}
  button.ghost:hover{border-color:var(--muted);}
  button.ghost:disabled{opacity:.55;cursor:default;}
  button:focus-visible{outline:2px solid var(--teal);outline-offset:2px;}
  section{margin:32px 0;}
  section[id]{scroll-margin-top:76px;}
  .card{background:var(--panel);border:1px solid var(--border-soft);border-radius:var(--radius);padding:26px 24px;}
  .card h2{margin:0 0 10px;}
  .kicker{font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--teal);margin-bottom:8px;}
  h2{font-size:19px;margin:0 0 6px;color:var(--heading);font-weight:650;letter-spacing:-.01em;}
  .muted{color:var(--muted);font-size:14.5px;line-height:1.65;}
  .pipeline{display:flex;flex-wrap:wrap;gap:6px;justify-content:center;margin-top:20px;}
  .pipeline .step{background:var(--panel2);border:1px solid var(--border);color:var(--text);
    border-radius:6px;padding:9px 15px;font-size:13px;font-weight:600;white-space:nowrap;}
  .pipeline .arrow{align-self:center;color:var(--border);font-size:13px;}
  #stages{list-style:none;padding:0;margin:20px 0 0;display:flex;flex-direction:column;gap:8px;}
  #stages li{display:flex;align-items:center;gap:13px;padding:13px 16px;border-radius:var(--radius-sm);background:var(--panel2);
    border:1px solid var(--border);opacity:.4;transition:opacity .25s,border-color .25s;font-size:14px;font-weight:500;}
  #stages li.active{opacity:1;border-color:var(--accent);}
  #stages li.done{opacity:1;border-color:var(--good-border);}
  #stages li .num{width:24px;height:24px;border-radius:6px;background:var(--border);display:flex;align-items:center;
    justify-content:center;font-size:11px;font-weight:700;flex-shrink:0;color:var(--muted);}
  #stages li.done .num{background:var(--good);color:#fff;}
  #stages li.active .num{background:var(--accent);color:#fff;}
  #result{margin-top:22px;display:none;}
  .badge{display:inline-flex;align-items:center;gap:6px;padding:7px 14px;border-radius:6px;font-size:13px;font-weight:700;
    letter-spacing:-.01em;}
  .badge.good{background:var(--good-bg);color:var(--good);border:1px solid var(--good-border);}
  .badge.bad{background:var(--bad-bg);color:var(--bad);border:1px solid var(--bad-border);}
  .badge.neutral{background:rgba(139,149,168,.12);color:var(--muted);border:1px solid rgba(139,149,168,.35);}
  .badge.gemini{background:rgba(74,157,149,.10);color:var(--teal);border:1px solid rgba(74,157,149,.35);}
  .result-grid{display:flex;flex-direction:column;gap:12px;margin-top:18px;}
  .result-block{padding:15px 16px;background:var(--panel2);border-radius:var(--radius-sm);border:1px solid var(--border);
    border-left:3px solid var(--border);font-size:14.5px;line-height:1.6;}
  .result-block.detection{border-left-color:var(--accent);}
  .result-block.evidence{border-left-color:var(--teal);}
  .result-block.decision{border-left-color:var(--good);}
  .result-block .label{font-size:10.5px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);
    margin-bottom:7px;font-weight:700;}
  .result-block code{background:rgba(255,255,255,.05);padding:2px 6px;border-radius:4px;word-break:break-word;
    font-size:13px;}
  .report-card{background:var(--panel2);border:1px solid var(--good-border);border-radius:var(--radius-sm);
    padding:20px;margin-top:8px;}
  .report-title{font-size:15.5px;font-weight:700;color:var(--heading);margin-bottom:4px;}
  .report-sub{font-size:13px;color:var(--good);font-weight:600;margin-bottom:14px;}
  .report-row{display:flex;justify-content:space-between;gap:12px;padding:9px 0;border-top:1px solid var(--border);
    font-size:14px;}
  .report-row:first-of-type{border-top:none;}
  .report-row .k{color:var(--muted);font-weight:600;flex-shrink:0;}
  .report-row .v{color:var(--text);text-align:right;}
  .appeal-card{margin-top:8px;background:#f7f5f0;color:#1c1c1c;border-radius:var(--radius-sm);overflow:hidden;
    border:1px solid #d8d3c5;}
  .appeal-head{padding:14px 20px;border-bottom:1px solid #d8d3c5;background:#efece3;
    font-size:11px;letter-spacing:.08em;text-transform:uppercase;font-weight:700;color:#6b6355;}
  .appeal-body{padding:22px;font-family:Georgia,"Times New Roman",serif;font-size:15px;line-height:1.7;
    white-space:pre-wrap;word-break:break-word;}
  .actions{display:flex;gap:10px;margin-top:14px;flex-wrap:wrap;}
  button.small{background:var(--panel2);color:var(--text);border:1px solid var(--border);padding:10px 18px;
    border-radius:var(--radius-sm);font-size:13.5px;font-weight:600;cursor:pointer;min-height:44px;transition:border-color .15s;}
  button.small:hover{border-color:var(--accent);}
  footer{padding:44px 0 56px;text-align:center;color:var(--muted);font-size:12.5px;border-top:1px solid var(--border-soft);
    margin-top:12px;}
  @media (max-width:480px){ .cta-row{flex-direction:column;} button.primary,button.ghost{width:100%;}
    .card{padding:22px 18px;} .hero{padding:48px 0 28px;} .report-row{flex-direction:column;gap:2px;}
    .report-row .v{text-align:left;} }
</style>
</head>
<body>
<header><div class="nav">
  <button type="button" id="brandBtn" class="brand" aria-label="Scroll to top of page">
    <span class="mark">B</span> BillWatch
  </button>
  <div class="tagline">All Things Agentic Hackathon</div>
</div></header>

<div class="wrap">
  <section class="hero">
    <div class="eyebrow">Medical Billing Investigation</div>
    <h1>Find <em>billing errors</em><br>before you pay.</h1>
    <p>BillWatch investigates your medical bill against real coding and billing rules -- and only drafts an appeal when the evidence genuinely supports one.</p>
    <div class="cta-row">
      <button type="button" class="primary" id="runDemoBtn" aria-label="Run a live BillWatch investigation using the discrepancy bill mock">Run Live Investigation (Discrepancy Bill Mock)</button>
      <button type="button" class="ghost" id="runCleanBtn" aria-label="Run a live BillWatch investigation using the clean bill mock">Run Live Investigation (Clean Bill Mock)</button>
    </div>
    <div class="cta-row" style="margin-top:10px;">
      <button type="button" class="ghost" id="howBtn" aria-label="Jump to how BillWatch works">How BillWatch Works</button>
    </div>
  </section>

  <section id="how" class="card">
    <div class="kicker">Architecture</div>
    <h2>AI doesn't decide alone</h2>
    <p class="muted">BillWatch never just asks an AI "is this bill wrong?" It moves through a controlled pipeline where every consequential decision -- is a source authoritative, is evidence sufficient, is an appeal eligible -- is made by deterministic code, not the model. An appeal is only drafted after the pipeline itself reaches a supported-discrepancy state. When the evidence doesn't support a discrepancy, BillWatch says so instead of manufacturing one.</p>
    <div class="pipeline">
      <span class="step">Scope</span><span class="arrow">&rarr;</span>
      <span class="step">Evidence</span><span class="arrow">&rarr;</span>
      <span class="step">Verification</span><span class="arrow">&rarr;</span>
      <span class="step">Decision</span><span class="arrow">&rarr;</span>
      <span class="step">Appeal</span>
    </div>
  </section>

  <section id="investigation" class="card">
    <div class="kicker">Live Demo</div>
    <h2>Live investigation</h2>
    <p class="muted">Both buttons run the real BillWatch pipeline against a real bill -- the same backend deployed to production. The discrepancy mock uses a bill with an established case scope and a real NCCI bundling issue. The clean mock uses a bill where scope was never established, so BillWatch will not manufacture a discrepancy just because a rule happens to match.</p>
    <ul id="stages" aria-live="polite">
      <li data-stage="0"><span class="num">1</span><span class="stage-label">Bill Received</span></li>
      <li data-stage="1"><span class="num">2</span><span class="stage-label">Scope Checked</span></li>
      <li data-stage="2"><span class="num">3</span><span class="stage-label">Evidence Analysed</span></li>
      <li data-stage="3"><span class="num">4</span><span class="stage-label">Discrepancy Verified</span></li>
      <li data-stage="4"><span class="num">5</span><span class="stage-label">Appeal Prepared</span></li>
    </ul>

    <div id="result" aria-live="polite"></div>
  </section>

  <footer>
    BillWatch &middot; agentic medical-bill investigation &middot; built for the All Things Agentic Hackathon
  </footer>
</div>

<script>
(function(){
  "use strict";

  var DISCREPANCY_STEPS = ["Bill Received", "Scope Checked", "Evidence Analysed", "Discrepancy Verified", "Appeal Prepared"];
  var CLEAN_STEPS = ["Bill Received", "Scope Checked", "Evidence Analysed", "Clean Bill Verified", "Detailed Report"];

  function prefersReducedMotion(){
    return !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  }

  function escapeHtml(s){
    return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
  }

  function applyStageLabels(scenario){
    var labels = (scenario === "clean") ? CLEAN_STEPS : DISCREPANCY_STEPS;
    var stageEls = document.querySelectorAll("#stages li .stage-label");
    stageEls.forEach(function(el, i){
      if (labels[i]) el.textContent = labels[i];
    });
  }

  async function runDemo(scenario){
    scenario = (scenario === "clean") ? "clean" : "discrepancy";
    var runBtn = document.getElementById("runDemoBtn");
    var cleanBtn = document.getElementById("runCleanBtn");
    var stages = document.querySelectorAll("#stages li");
    var resultEl = document.getElementById("result");
    if (!runBtn || !cleanBtn || runBtn.disabled || cleanBtn.disabled) return;

    applyStageLabels(scenario);

    runBtn.disabled = true;
    cleanBtn.disabled = true;
    var activeBtn = scenario === "clean" ? cleanBtn : runBtn;
    var activeLabel = activeBtn.textContent;
    activeBtn.textContent = "Investigating...";

    resultEl.style.display = "none";
    resultEl.innerHTML = "";
    stages.forEach(function(li){ li.classList.remove("active","done"); });

    function reveal(i){
      return new Promise(function(res){
        setTimeout(function(){
          if (i > 0){ stages[i-1].classList.remove("active"); stages[i-1].classList.add("done"); }
          if (i < stages.length){ stages[i].classList.add("active"); }
          res();
        }, 380);
      });
    }

    var data = null, errored = false;
    var fetchPromise = fetch("/investigate?scenario=" + encodeURIComponent(scenario)).then(function(r){
      if (!r.ok) throw new Error("bad status");
      return r.json();
    }).then(function(j){ data = j; }).catch(function(){ errored = true; });

    for (var i = 0; i < stages.length; i++){ await reveal(i); }
    await fetchPromise;
    if (stages.length){
      stages[stages.length-1].classList.remove("active");
      stages[stages.length-1].classList.add("done");
    }

    runBtn.disabled = false;
    cleanBtn.disabled = false;
    activeBtn.textContent = activeLabel;
    resultEl.style.display = "block";

    if (errored || !data){
      resultEl.innerHTML = '<div class="badge bad">Investigation temporarily unavailable</div>'
        + '<p class="muted" style="margin-top:10px;">We could not reach the investigation service just now.</p>'
        + '<div class="actions"><button type="button" class="small" data-action="retry" data-scenario="' + scenario + '">Retry</button></div>';
      return;
    }

    if (data.success && data.final_status === "supported_discrepancy"){
      var html = '<div class="badge good">&#10003; Supported discrepancy</div>';
      if (data.gemini_mode === "live"){
        html += ' <span class="badge gemini">Gemini &mdash; LIVE</span>';
      }
      html += '<div class="result-grid">';
      html += '<div class="result-block detection"><div class="label">Detection</div>Codes <code>45378</code> and <code>45380</code> were billed together for the same date of service.</div>';
      html += '<div class="result-block evidence"><div class="label">Evidence</div>Under CMS NCCI Procedure-to-Procedure edits, this code pair is treated as bundled -- billing them separately is a possible discrepancy.</div>';
      html += '<div class="result-block decision"><div class="label">Decision</div>SUPPORTED_DISCREPANCY, reached through the guarded Scope &rarr; Evidence &rarr; Verification pipeline.</div>';
      if (data.appeal_generated && data.appeal_draft){
        html += '<div>'
          + '<div class="appeal-card">'
          + '<div class="appeal-head">Draft Appeal &middot; For Human Review</div>'
          + '<div class="appeal-body" id="appealText">' + escapeHtml(data.appeal_draft) + '</div>'
          + '</div>'
          + '<div class="actions"><button type="button" class="small" data-action="copy">Copy Appeal</button><button type="button" class="small" data-action="download">Download Appeal</button></div>'
          + '</div>';
      }
      html += '</div>';
      resultEl.innerHTML = html;
    } else if (data.success) {
      var html3 = '<div class="badge good">&#10003; Investigation Complete</div> <span class="badge neutral">Clean Bill Verified</span>';
      html3 += '<div class="report-card">';
      html3 += '<div class="report-title">Detailed Report</div>';
      html3 += '<div class="report-sub">No Appeal Recommended</div>';
      html3 += '<div class="report-row"><span class="k">Status</span><span class="v">Clean Bill Verified</span></div>';
      html3 += '<div class="report-row"><span class="k">Finding</span><span class="v">No supported billing discrepancy established.</span></div>';
      html3 += '<div class="report-row"><span class="k">Appeal</span><span class="v">Not recommended.</span></div>';
      html3 += '<div class="report-row"><span class="k">Reason</span><span class="v">The evidence and deterministic verification gates did not establish a supported discrepancy.</span></div>';
      if (data.final_status) {
        html3 += '<div class="report-row"><span class="k">Backend status</span><span class="v"><code>' + escapeHtml(data.final_status) + '</code></span></div>';
      }
      html3 += '</div>';
      html3 += '<p class="muted" style="margin-top:12px;">BillWatch completed its Scope &rarr; Evidence &rarr; Verification process. This means no supported billing discrepancy was established by the current evidence and verification process -- not that the bill is guaranteed error-free.</p>';
      resultEl.innerHTML = html3;
    } else {
      var html2 = '<div class="badge bad">Investigation incomplete</div>';
      html2 += '<p class="muted" style="margin-top:10px;">BillWatch did not generate an appeal because the evidence and state required to support one were not established';
      if (data.failed_stage){ html2 += " (stopped at: <code>" + escapeHtml(String(data.failed_stage)) + "</code>)"; }
      html2 += '.</p><div class="actions"><button type="button" class="small" data-action="retry" data-scenario="' + scenario + '">Retry</button></div>';
      resultEl.innerHTML = html2;
    }
  }

  function copyAppeal(){
    var el = document.getElementById("appealText");
    if (!el) return;
    var text = el.innerText;
    if (navigator.clipboard && navigator.clipboard.writeText){
      navigator.clipboard.writeText(text).then(function(){
        var btns = document.querySelectorAll('.actions [data-action="copy"]');
        if (btns[0]){ var orig = btns[0].textContent; btns[0].textContent = "Copied!"; setTimeout(function(){ btns[0].textContent = orig; }, 1500); }
      });
    }
  }

  function downloadAppeal(){
    var el = document.getElementById("appealText");
    if (!el) return;
    var text = el.innerText;
    var blob = new Blob([text], {type:"text/plain"});
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url; a.download = "billwatch-appeal.txt";
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  document.addEventListener("DOMContentLoaded", function(){
    var brandBtn = document.getElementById("brandBtn");
    var runBtn = document.getElementById("runDemoBtn");
    var cleanBtn = document.getElementById("runCleanBtn");
    var howBtn = document.getElementById("howBtn");
    var resultEl = document.getElementById("result");

    if (brandBtn){
      brandBtn.addEventListener("click", function(){
        window.scrollTo({top:0, behavior: prefersReducedMotion() ? "auto" : "smooth"});
      });
    }
    if (howBtn){
      howBtn.addEventListener("click", function(){
        var target = document.getElementById("how");
        if (target){
          target.scrollIntoView({behavior: prefersReducedMotion() ? "auto" : "smooth", block:"start"});
        }
      });
    }
    if (runBtn){
      runBtn.addEventListener("click", function(){ runDemo("discrepancy"); });
    }
    if (cleanBtn){
      cleanBtn.addEventListener("click", function(){ runDemo("clean"); });
    }
    if (resultEl){
      resultEl.addEventListener("click", function(e){
        var actionEl = e.target.closest ? e.target.closest("[data-action]") : null;
        if (!actionEl) return;
        var action = actionEl.getAttribute("data-action");
        if (action === "copy") copyAppeal();
        if (action === "download") downloadAppeal();
        if (action === "retry") runDemo(actionEl.getAttribute("data-scenario") || "discrepancy");
      });
    }
  });
})();
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, code, obj):
        body = json.dumps(obj, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, code, html):
        body = html.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = route_path(self.path)
        if path == "/":
            self._send_html(200, INDEX_HTML)
        elif path == "/health":
            self._send_json(200, {"status": "ok", "service": "billwatch"})
        elif path == "/investigate":
            try:
                scenario = _scenario_param(self.path)
                self._send_json(200, _run_demo_investigation(scenario))
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})
        else:
            self._send_json(404, {"error": "not found"})

    def log_message(self, format, *args):
        # Never log request bodies/headers that could contain secrets.
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"BillWatch serving on port {port}")
    server.serve_forever()
