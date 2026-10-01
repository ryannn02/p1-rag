"""最小演示界面：一个页面 + 一个 `/api/ask`。

    python -m scripts.serve          # 打开 http://127.0.0.1:8000
    python -m scripts.serve 9000     # 换端口

只用标准库 http.server，不为一个演示页面引 Web 框架进来。只在 127.0.0.1 上监听，
不暴露到局域网。要产品化（多用户、流式输出、鉴权）再说，那时换 FastAPI 也不亏。
"""

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, ".")
from p1.generator import answer  # noqa: E402
from p1.retriever import Retriever  # noqa: E402

MAX_QUESTION = 200
RETRIEVER = None


def parse_question(body):
    """把请求体解析成问题，返回 (question, error)。

    空问题和超长问题在这里挡掉——模型调用是要花钱的，别把原始输入直接喂过去。
    """
    try:
        data = json.loads(body or b"{}")
        question = str(data.get("question") or "").strip()
    except (json.JSONDecodeError, AttributeError, TypeError):
        return None, "请求体不是合法 JSON"
    if not question:
        return None, "问题不能为空"
    if len(question) > MAX_QUESTION:
        return None, f"问题太长了，最多 {MAX_QUESTION} 字"
    return question, None


PAGE = """<!doctype html>
<html lang="zh-CN">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>校园制度问答助手</title>
<style>
  body { font: 16px/1.7 -apple-system, "PingFang SC", sans-serif; color: #1a1a1a;
         max-width: 720px; margin: 0 auto; padding: 2rem 1rem; }
  h1 { font-size: 1.35rem; margin: 0 0 .2rem; }
  .sub { color: #718096; font-size: .85rem; margin: 0 0 1.5rem; }
  form { display: flex; gap: .5rem; }
  input { flex: 1; padding: .7rem .9rem; font-size: 1rem; border: 1px solid #cbd5e0; border-radius: 8px; }
  input:focus { outline: 2px solid #90cdf4; border-color: transparent; }
  button { padding: .7rem 1.3rem; font-size: 1rem; border: 0; border-radius: 8px;
           background: #2b6cb0; color: #fff; cursor: pointer; }
  button:disabled { background: #a0aec0; cursor: default; }
  .examples { font-size: .88rem; color: #718096; margin: .7rem 0 1.8rem; }
  .examples button { background: none; border: 0; padding: 0 .4rem; color: #2b6cb0;
                     text-decoration: underline; cursor: pointer; font-size: .88rem; }
  .answer { background: #f7fafc; border-left: 3px solid #2b6cb0; padding: .8rem 1rem;
            border-radius: 0 8px 8px 0; white-space: pre-wrap; }
  .answer.refused { background: #fffaf0; border-left-color: #dd6b20; }
  .cite { border-top: 1px solid #e2e8f0; padding: .6rem 0; font-size: .88rem; color: #4a5568; }
  .cite b { color: #2d3748; }
  .meta { color: #718096; font-size: .82rem; }
</style>
<h1>上海第二工业大学 · 校园制度问答</h1>
<p class="sub">回答只依据学校现行有效的规章制度，每条结论都附出处。库里没有依据的会明确拒答。</p>
<form id="f">
  <input id="q" placeholder="例：图书馆一次能借几本书？" autocomplete="off" maxlength="200">
  <button id="go">提问</button>
</form>
<p class="examples">试一下：
  <button data-q="图书馆一次能借几本书，能借多久">图书馆借书</button>
  <button data-q="转专业需要什么条件">转专业</button>
  <button data-q="在宿舍里使用违规电器被查到会怎么处理">宿舍违规电器</button>
  <button data-q="学校对师生结婚有什么规定">库里没有的问题</button>
</p>
<div id="out"></div>
<script>
const f = document.getElementById('f'), q = document.getElementById('q'),
      go = document.getElementById('go'), out = document.getElementById('out');
document.querySelectorAll('.examples button').forEach(b => b.onclick = () => {
  q.value = b.dataset.q; f.requestSubmit();
});
f.onsubmit = async e => {
  e.preventDefault();
  const question = q.value.trim();
  if (!question) return;
  go.disabled = true; go.textContent = '…';
  out.innerHTML = '<p class="meta">检索与生成中…</p>';
  try {
    const r = await fetch('/api/ask', { method: 'POST',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question }) });
    const d = await r.json();
    out.innerHTML = r.ok ? render(d)
      : '<div class="answer refused">' + esc(d.error || '出错了') + '</div>';
  } catch (err) {
    out.innerHTML = '<div class="answer refused">请求失败：' + esc(String(err)) + '</div>';
  }
  go.disabled = false; go.textContent = '提问';
};
const esc = s => String(s).replace(/[&<>"]/g,
  c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
function render(d) {
  if (d.refused) {
    return '<div class="answer refused"><b>拒绝回答</b><br>' + esc(d.refuse_reason || '')
      + (d.suggested_contact ? '<br><span class="meta">建议咨询：' + esc(d.suggested_contact) + '</span>' : '')
      + '</div>';
  }
  const cites = d.citations.map((c, i) =>
    '<div class="cite">[' + (i + 1) + '] <b>《' + esc(c.file) + '》</b>'
    + (c.section ? ' ' + esc(c.section) : '') + (c.page ? ' 第 ' + c.page + ' 页' : '')
    + ' <span class="meta">匹配度 ' + c.score.toFixed(3) + '</span><br>' + esc(c.snippet) + '…</div>').join('');
  return '<div class="answer">' + esc(d.answer) + '</div>'
    + '<p class="meta">置信度 ' + d.confidence.toFixed(2) + '</p>' + cites;
}
</script>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False), "application/json; charset=utf-8")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self._send(200, PAGE, "text/html; charset=utf-8")
        self._send(404, "not found", "text/plain; charset=utf-8")

    def do_POST(self):
        if self.path != "/api/ask":
            return self._send(404, "not found", "text/plain; charset=utf-8")
        length = int(self.headers.get("Content-Length") or 0)
        question, error = parse_question(self.rfile.read(length))
        if error:
            return self._json(400, {"error": error})
        try:
            res = answer(question, retriever=RETRIEVER)
        except Exception as exc:  # 模型超时/网络错不该把服务打挂
            return self._json(502, {"error": f"生成失败：{exc}"})
        self._send(200, res.model_dump_json(), "application/json; charset=utf-8")

    def log_message(self, fmt, *args):
        print(f"  {fmt % args}")


def main():
    global RETRIEVER
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print("加载向量索引与模型…")
    RETRIEVER = Retriever()
    print(f"就绪：http://127.0.0.1:{port}  （Ctrl+C 停止）")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
