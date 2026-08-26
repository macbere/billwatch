"""
BillWatch Cloud Run entrypoint. Stdlib-only HTTP wrapper -- no new
dependency, no reasoning of its own. Calls the existing, unmodified
pipeline.run_investigation() and serializes its result. Uses
GenAISDKProvider if GEMINI_API_KEY is set, otherwise MockLLMProvider,
exactly like demo.py.
"""
import json
import os
import re
from http.server import BaseHTTPRequestHandler, HTTPServer

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
                "draft_text": "I am appealing the billing of codes 45378 and 45380 together, which CMS NCCI treats as bundled.",
                "cited_fact_ids": fact_ids,
                "cited_claim_ids": [m.group(1)] if m else [],
            })
        return "{}"
    return MockLLMProvider(response_fn=dispatch)


def _run_demo_investigation():
    doc = Document(
        doc_type="bill",
        raw_text="Itemized bill: CPT/HCPCS codes 45378 and 45380 billed together, same date of service, $500.00 total.",
    )
    if os.environ.get("GEMINI_API_KEY"):
        from billwatch.genai_sdk_provider import GenAISDKProvider
        provider = GenAISDKProvider()
    else:
        provider = _mock_dispatch_provider(doc)

    investigation = Investigation()
    case_scope = establish_from_user_selection("medicare")
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


INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>BillWatch -- Find billing errors before you pay.</title>
<style>
  :root{
    --bg:#0b1220; --panel:#111a2e; --panel2:#0f1830; --border:#22304d;
    --text:#eaf0ff; --muted:#93a2c4; --brand:#4f8dff; --brand2:#7ad0c4;
    --good:#2ecc8f; --bad:#ff6767; --warn:#f5b942;
    --radius:16px;
  }
  *{box-sizing:border-box;}
  body{margin:0;background:linear-gradient(180deg,#0b1220,#0d1526 60%,#0b1220);
    color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    line-height:1.5;-webkit-font-smoothing:antialiased;}
  .wrap{max-width:860px;margin:0 auto;padding:0 20px;}
  header{position:sticky;top:0;z-index:10;background:rgba(11,18,32,.85);backdrop-filter:blur(8px);
    border-bottom:1px solid var(--border);}
  .nav{display:flex;align-items:center;justify-content:space-between;padding:14px 20px;max-width:860px;margin:0 auto;}
  .brand{display:flex;align-items:center;gap:8px;font-weight:700;font-size:18px;letter-spacing:-.02em;}
  .brand .dot{width:10px;height:10px;border-radius:50%;background:var(--brand);box-shadow:0 0 12px var(--brand);}
  .hero{padding:56px 0 28px;text-align:center;}
  .hero h1{font-size:clamp(28px,6vw,44px);line-height:1.1;margin:0 0 14px;letter-spacing:-.02em;}
  .hero h1 span{background:linear-gradient(90deg,var(--brand),var(--brand2));-webkit-background-clip:text;background-clip:text;color:transparent;}
  .hero p{color:var(--muted);font-size:17px;max-width:520px;margin:0 auto 26px;}
  .cta-row{display:flex;gap:12px;justify-content:center;flex-wrap:wrap;}
  button.primary,a.primary{background:var(--brand);color:#fff;border:none;padding:14px 24px;border-radius:12px;
    font-size:16px;font-weight:600;cursor:pointer;box-shadow:0 8px 24px rgba(79,141,255,.35);transition:transform .15s;}
  button.primary:hover{transform:translateY(-1px);}
  button.primary:disabled{opacity:.6;cursor:default;transform:none;}
  button.ghost{background:transparent;color:var(--text);border:1px solid var(--border);padding:14px 24px;
    border-radius:12px;font-size:16px;font-weight:600;cursor:pointer;}
  section{margin:36px 0;}
  .card{background:var(--panel);border:1px solid var(--border);border-radius:var(--radius);padding:22px;}
  .pipeline{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;font-size:13px;color:var(--muted);}
  .pipeline .step{background:var(--panel2);border:1px solid var(--border);border-radius:999px;padding:8px 14px;white-space:nowrap;}
  .pipeline .arrow{align-self:center;color:var(--border);}
  h2{font-size:20px;margin:0 0 6px;}
  .muted{color:var(--muted);font-size:14px;}
  #stages{list-style:none;padding:0;margin:18px 0 0;display:flex;flex-direction:column;gap:10px;}
  #stages li{display:flex;align-items:center;gap:12px;padding:12px 14px;border-radius:10px;background:var(--panel2);
    border:1px solid var(--border);opacity:.35;transition:opacity .25s,background .25s;font-size:14px;}
  #stages li.active{opacity:1;border-color:var(--brand);}
  #stages li.done{opacity:1;}
  #stages li .num{width:22px;height:22px;border-radius:50%;background:var(--border);display:flex;align-items:center;
    justify-content:center;font-size:11px;font-weight:700;flex-shrink:0;}
  #stages li.done .num{background:var(--good);color:#06210f;}
  #stages li.active .num{background:var(--brand);color:#fff;}
  #result{margin-top:20px;display:none;}
  .badge{display:inline-flex;align-items:center;gap:6px;padding:6px 12px;border-radius:999px;font-size:13px;font-weight:700;}
  .badge.good{background:rgba(46,204,143,.15);color:var(--good);border:1px solid rgba(46,204,143,.4);}
  .badge.bad{background:rgba(255,103,103,.15);color:var(--bad);border:1px solid rgba(255,103,103,.4);}
  .badge.gemini{background:rgba(122,208,196,.15);color:var(--brand2);border:1px solid rgba(122,208,196,.4);}
  .evidence{margin:16px 0;padding:14px;background:var(--panel2);border-radius:10px;border:1px solid var(--border);font-size:14px;}
  .evidence code{background:rgba(255,255,255,.06);padding:2px 6px;border-radius:4px;}
  .appeal-box{margin-top:16px;background:#fff;color:#1a1a1a;border-radius:12px;padding:20px;font-family:Georgia,serif;
    font-size:15px;line-height:1.6;white-space:pre-wrap;}
  .actions{display:flex;gap:10px;margin-top:14px;flex-wrap:wrap;}
  button.small{background:var(--panel2);color:var(--text);border:1px solid var(--border);padding:10px 16px;
    border-radius:10px;font-size:14px;cursor:pointer;}
  button.small:hover{border-color:var(--brand);}
  footer{padding:40px 0 60px;text-align:center;color:var(--muted);font-size:13px;}
  footer a{color:var(--brand2);text-decoration:none;}
  @media (max-width:480px){ .cta-row{flex-direction:column;} button.primary,a.primary,button.ghost{width:100%;} }
</style>
</head>
<body>
<header><div class="nav">
  <div class="brand"><span class="dot"></span> BillWatch</div>
  <div class="muted" style="font-size:13px;">All Things Agentic Hackathon</div>
</div></header>

<div class="wrap">
  <section class="hero">
    <h1>Find <span>billing errors</span><br>before you pay.</h1>
    <p>BillWatch investigates your medical bill against real coding and billing rules -- and only drafts an appeal when the evidence genuinely supports one.</p>
    <div class="cta-row">
      <button class="primary" id="runDemoBtn" onclick="runDemo()">Run Live Demo</button>
      <button class="ghost" onclick="document.getElementById('how').scrollIntoView({behavior:'smooth'})">How it works</button>
    </div>
  </section>

  <section id="how" class="card">
    <h2>An agentic system with guardrails</h2>
    <p class="muted">BillWatch never just asks an AI "is this bill wrong?" It moves through a controlled pipeline where every consequential decision is made by deterministic code -- not the model.</p>
    <div class="pipeline">
      <span class="step">Scope</span><span class="arrow">&rarr;</span>
      <span class="step">Evidence</span><span class="arrow">&rarr;</span>
      <span class="step">Verification</span><span class="arrow">&rarr;</span>
      <span class="step">Decision</span><span class="arrow">&rarr;</span>
      <span class="step">Appeal</span>
    </div>
  </section>

  <section class="card">
    <h2>Live investigation</h2>
    <p class="muted">This runs the real BillWatch pipeline against a demo bill (CPT codes 45378 + 45380 billed same date of service) -- the same backend that is deployed to production.</p>
    <ul id="stages">
      <li data-stage="0"><span class="num">1</span> Bill received</li>
      <li data-stage="1"><span class="num">2</span> Scope checked</li>
      <li data-stage="2"><span class="num">3</span> Evidence analyzed</li>
      <li data-stage="3"><span class="num">4</span> Discrepancy verified</li>
      <li data-stage="4"><span class="num">5</span> Appeal prepared</li>
    </ul>

    <div id="result"></div>
  </section>

  <footer>
    BillWatch &middot; agentic medical-bill investigation &middot; built for the All Things Agentic Hackathon
  </footer>
</div>

<script>
async function runDemo(){
  const btn = document.getElementById('runDemoBtn');
  const stages = document.querySelectorAll('#stages li');
  const resultEl = document.getElementById('result');
  btn.disabled = true;
  btn.textContent = 'Investigating...';
  resultEl.style.display = 'none';
  resultEl.innerHTML = '';
  stages.forEach(li => li.classList.remove('active','done'));

  const reveal = (i) => new Promise(res => {
    setTimeout(() => {
      if (i > 0) stages[i-1].classList.remove('active');
      if (i > 0) stages[i-1].classList.add('done');
      if (i < stages.length) stages[i].classList.add('active');
      res();
    }, 380);
  });

  let data, errored = false;
  const fetchPromise = fetch('/investigate').then(r => r.json()).then(j => data = j).catch(() => errored = true);

  for (let i = 0; i < stages.length; i++){ await reveal(i); }
  await fetchPromise;
  stages[stages.length-1].classList.remove('active');
  stages[stages.length-1].classList.add('done');

  btn.disabled = false;
  btn.textContent = 'Run Live Demo';
  resultEl.style.display = 'block';

  if (errored || !data){
    resultEl.innerHTML = '<div class="badge bad">Request failed</div><p class="muted" style="margin-top:10px;">Could not reach the investigation service. Please try again.</p>';
    return;
  }

  if (data.success && data.final_status === 'supported_discrepancy'){
    let html = '<div class="badge good">&#10003; Supported discrepancy</div>';
    if (data.gemini_mode === 'live'){
      html += ' <span class="badge gemini">Gemini &mdash; LIVE</span>';
    }
    html += '<div class="evidence">Codes <code>45378</code> and <code>45380</code> were billed together for the same date of service. Under CMS NCCI Procedure-to-Procedure edits, this code pair is treated as bundled -- billing them separately is a possible discrepancy.</div>';
    if (data.appeal_generated && data.appeal_draft){
      html += '<h2 style="margin-top:22px;">Generated appeal</h2>';
      html += '<div class="appeal-box" id="appealText">' + data.appeal_draft.replace(/</g,'&lt;') + '</div>';
      html += '<div class="actions"><button class="small" onclick="copyAppeal()">Copy Appeal</button><button class="small" onclick="downloadAppeal()">Download Appeal</button></div>';
    }
    resultEl.innerHTML = html;
  } else {
    let html = '<div class="badge bad">No supported discrepancy</div>';
    html += '<p class="muted" style="margin-top:10px;">BillWatch did not generate an appeal because the evidence and state required to support one were not established';
    if (data.failed_stage){ html += ' (stopped at: <code>' + data.failed_stage + '</code>)'; }
    html += '.</p>';
    resultEl.innerHTML = html;
  }
}

function copyAppeal(){
  const text = document.getElementById('appealText').innerText;
  navigator.clipboard.writeText(text).then(() => {
    const btns = document.querySelectorAll('.actions .small');
    if (btns[0]){ const orig = btns[0].textContent; btns[0].textContent = 'Copied!'; setTimeout(()=>btns[0].textContent = orig, 1500); }
  });
}

function downloadAppeal(){
  const text = document.getElementById('appealText').innerText;
  const blob = new Blob([text], {type:'text/plain'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = 'billwatch-appeal.txt';
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
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
        if self.path == "/":
            self._send_html(200, INDEX_HTML)
        elif self.path == "/health":
            self._send_json(200, {"status": "ok", "service": "billwatch"})
        elif self.path == "/investigate":
            try:
                self._send_json(200, _run_demo_investigation())
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
