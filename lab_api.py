# SPDX-FileCopyrightText: 2026 Beomjoon Kim
# SPDX-License-Identifier: AGPL-3.0-only
"""POSCHAT Lab(1.16) 화면 API: main.Bridge가 상속한다. 화면은 web/lab.js.

Lab은 실험 관리 + 재현성 기록 + AI 분석이다.
- 실험(Experiment)과 실행 기록(Run): lab_store(SQLite). 지워도 사용자 원본 파일은 그대로 둔다.
- 실행: POSCHAT Code의 RunManager와 같은 승인(한 번 쓰는 토큰, 명령의 SHA-256에 묶임)을 거친다. 자동으로 실행하지 않는다.
- 재현성: 실행 직전에 Git 커밋·가지·바뀐 파일·커밋하지 않은 변경(패치 사본), 실행 환경(OS·Python·패키지·GPU·CUDA,
  비밀이 아닌 환경 변수)을 남긴다. 설치하지 않고 있는 것만 찾는다.
- 결과: 원본 파일을 옮기지 않고 경로·크기·해시로 가리킨다. 지표는 사용자가 고른 열·값만 뽑는다(lab_results).
- AI 분석: 고른 실험·Run 기록만 채팅 첨부로 보낸다(외부 데이터로 감쌈). 실험을 직접 실행하지 않는다.
"""
import base64
import fnmatch
import hashlib
import json
import os
import platform
import re
import secrets
import shlex
import shutil
import subprocess
import sys
import threading
import time

import code_runner
import code_workspace as cw
import connectors
import lab_results
import lab_store
import remote_fs
import storage

KINDS = ("command", "python", "notebook")
PARAM_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]{0,40}$")
ENV_KEEP = re.compile(r"^(CUDA_|NVIDIA_|OMP_|MKL_|OPENBLAS_|TF_|TORCH_|XLA_|PYTHONHASHSEED$|PYTHONPATH$|VIRTUAL_ENV$|"
                      r"CONDA_DEFAULT_ENV$|CONDA_PREFIX$|LANG$|LC_ALL$|TZ$|POSCHAT_)")
MAX_PATCH = 2 * 1024 * 1024
MAX_IMAGE = 8 * 1024 * 1024
MAX_SCAN = 300
WALK_EXCLUDES = {"node_modules", "__pycache__", "venv", "env", "site-packages"}
SCAN_EXT = set(lab_results.TABLE_EXT) | set(lab_results.IMAGE_EXT)
ANALYSIS_RULES = (
    "아래 규칙을 지켜 답해 줘.\n"
    "1. 첨부한 실험·Run 기록에 있는 값만 쓰고, 없는 값은 지어내지 말고 '기록에 없음'이라고 말해.\n"
    "2. '관찰'(기록된 사실)과 '해석'(가능한 설명)을 나눠 써.\n"
    "3. 상관관계를 인과관계로 단정하지 마. 여러 조건이 함께 바뀐 비교라면 그 점을 짚어.\n"
    "4. 근거를 말할 때 Run ID(run-…)를 붙여.\n"
    "5. 단위가 다르거나 빠진 지표, 커밋하지 않은 변경, 실패·중단된 Run은 따로 짚어.\n"
    "6. 실험을 직접 실행하지 마. 다음 실험은 '제안'으로만 쓰고, 사용자가 확인한 뒤 Lab에서 실행한다고 적어.\n"
)
ASK_PRESETS = {
    "summary": "이 실험의 결과를 요약해 줘. 가장 좋은 Run과 그 조건, 눈에 띄는 차이를 짚어 줘.",
    "compare": "고른 Run들을 비교해 줘. 파라미터·코드 버전·환경 차이와 지표 차이를 나란히 정리해 줘.",
    "anomaly": "실패했거나 이상한 Run이 있는지 찾아 줘. 로그·지표에서 근거를 들어 가능한 원인을 알려 줘.",
    "next": "다음에 해 볼 만한 실험을 2~3개 제안해 줘. 무엇을 확인하려는지와 바꿀 파라미터를 적어 줘(실행은 내가 정한다).",
}
STATUS_MAP = {"done": "completed", "failed": "failed", "stopped": "cancelled", "timeout": "failed", "error": "failed"}


def _quote(arg, path=False):
    arg = str(arg)
    if os.name == "nt":
        return _quote_cmd(arg, path)
    return shlex.quote(arg)


def _quote_cmd(arg, path=False):
    """Windows cmd.exe용: 늘 큰따옴표로 감싸 & | < > ^ 를 글자로 둔다(list2cmdline은 빈칸이 없으면 감싸지 않아
    'a&calc'가 명령 두 개가 된다). 따옴표 안에서도 펼쳐지는 %·!와 따옴표 자체는 파라미터 값에 받지 않는다.
    path=True(이 PC의 Python·스크립트 경로): 사용자가 고른 경로라 %·!는 그대로 두고 따옴표만 막는다."""
    if any(c in arg for c in ('"' if path else '"%!')):
        raise lab_store.LabError("Windows에서는 파라미터·경로에 \" % ! 를 쓸 수 없습니다.")
    return '"' + re.sub(r"(\\+)$", r"\1\1", arg) + '"'   # 닫는 따옴표 앞의 \는 두 배로(프로그램이 \"로 읽지 않게)


_PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_.-]*)\}")


def _fill_template(template, params):
    """명령 틀의 {이름}에 값을 넣는다. 틀의 따옴표 상태를 따라가며 자리마다 그 문맥에 맞게 넣는다:
    따옴표 밖이면 _quote로 감싸고, "…" 안이면 감싸지 않고 그 안에서 특별한 글자만 막거나 이스케이프한다
    (따옴표 안에 따옴표를 또 넣으면 따옴표가 닫혀 &·$( )가 다시 명령 연결·치환이 된다)."""
    nt = os.name == "nt"
    out, quote, i = [], None, 0
    while i < len(template):
        m = _PLACEHOLDER.match(template, i)
        if m:
            value = _param_text(params[m.group(1)])
            nxt = template[m.end():m.end() + 1]
            if quote is None:
                out.append(_quote(value))
            elif nt:   # cmd "…" 안: & | < > ^는 글자. %·!·"만 막고, 닫는 따옴표 앞의 \는 두 배로
                if any(c in value for c in '"%!'):
                    raise lab_store.LabError("Windows에서는 파라미터 값에 \" % ! 를 쓸 수 없습니다.")
                out.append(re.sub(r"(\\+)$", r"\1\1", value) if nxt == '"' else value)
            elif quote == '"':   # sh "…" 안: \ " $ `만 이스케이프
                out.append(re.sub(r'([\\"$`])', r"\\\1", value))
            else:   # sh '…' 안: '만 '\''로
                out.append(value.replace("'", "'\\''"))
            i = m.end()
            continue
        c = template[i]
        if quote is None and (c == '"' or (c == "'" and not nt)):
            quote = c
        elif c == quote:
            quote = None
        elif c == "\\" and not nt and quote != "'" and i + 1 < len(template):
            out.append(c)   # sh의 \x는 다음 글자를 글자로 둔다(따옴표 상태를 바꾸지 않음)
            i += 1
            c = template[i]
        out.append(c)
        i += 1
    return "".join(out)


def _clean_params(params):
    out = {}
    for k, v in (params or {}).items():
        k = str(k).strip()
        if not PARAM_NAME.match(k):
            raise lab_store.LabError(f"파라미터 이름은 영문·숫자·_ . -로 씁니다: {k[:40]}")
        if isinstance(v, bool) or v is None or isinstance(v, (int, float)):
            out[k] = v
            continue
        v = str(v)
        if len(v) > 500 or any(c in v for c in "\x00\r\n"):
            raise lab_store.LabError(f"파라미터 '{k}' 값이 너무 길거나 줄 바꿈이 있습니다.")
        out[k] = v
    if len(out) > 60:
        raise lab_store.LabError("파라미터가 너무 많습니다(60개까지).")
    return out


def _param_text(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    return "" if v is None else str(v)


def build_command(spec, python=""):
    """실행 설정 → (실제 명령, 명령 틀). 명령 틀은 파라미터를 {이름}으로 둔 것(다시 실행·비교용)."""
    kind = spec.get("kind") or "command"
    if kind not in KINDS:
        raise lab_store.LabError("실행 방식은 명령·Python 스크립트·Jupyter 노트북 중 하나입니다.")
    params = _clean_params(spec.get("params"))
    if kind == "command":
        template = str(spec.get("command") or "").strip()
        if not template:
            raise lab_store.LabError("실행할 명령을 입력하세요.")
        missing = [m for m in re.findall(r"\{([A-Za-z_][A-Za-z0-9_.-]*)\}", template) if m not in params]
        if missing:
            raise lab_store.LabError(f"명령의 {{{missing[0]}}}에 넣을 파라미터가 없습니다.")
        command = _fill_template(template, params)
        return command, template
    script = cw.clean_rel(str(spec.get("script") or ""))
    if not script:
        raise lab_store.LabError("작업 폴더 안의 파일을 고르세요.")
    if not python:
        raise lab_store.LabError("이 PC에서 Python을 찾지 못했습니다.")
    if kind == "python":
        if not script.endswith(".py"):
            raise lab_store.LabError("Python 스크립트(.py)를 고르세요.")
        args = " ".join(f"--{k} {_quote(_param_text(v))}" for k, v in params.items())
        template_args = " ".join(f"--{k} {{{k}}}" for k in params)
        base = f"{_quote(python, True)} {_quote(script, True)}"
        return (base + (" " + args if args else "")), (base + (" " + template_args if template_args else ""))
    if not script.endswith(".ipynb"):
        raise lab_store.LabError("Jupyter 노트북(.ipynb)을 고르세요.")
    out_dir = str(spec.get("_out_dir") or "")
    base = (f"{_quote(python, True)} -m nbconvert --to notebook --execute --output executed.ipynb "
            + (f"--output-dir {_quote(out_dir, True)} " if out_dir else "") + _quote(script, True))
    return base, base


def _inside(root, path):
    try:
        return os.path.commonpath([root, path]) == root
    except ValueError:  # Windows: 다른 드라이브
        return False


def strip_credentials(url):
    return re.sub(r"(?i)^(\w+://)[^/@\s]+@", r"\1", str(url or ""))


def capture_code(workspace, patch_dir=None):
    """실행 직전의 코드 버전: 커밋·가지·커밋하지 않은 변경(바뀐 파일 목록, 패치 사본과 해시)."""
    import code_git

    out = {"repo": False}
    try:
        info = code_git.repo_info(workspace)
    except Exception as e:  # git 오류는 기록만
        return {"repo": False, "reason": str(e)[:200]}
    if not info.get("repo"):
        return {"repo": False, "reason": info.get("reason", "")}
    root = cw.root_of(workspace)
    try:
        def git(*args, strip=True):
            r = code_git._git(root, list(args), check=False)
            text = r.stdout.decode("utf-8", errors="replace") if r.returncode == 0 else ""
            return text.strip() if strip else text

        out = {"repo": True, "top": info.get("top", ""), "commit": git("rev-parse", "HEAD"),
               "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
               "remote": strip_credentials(git("config", "--get", "remote.origin.url"))}
        status = git("status", "--porcelain=v1", "--untracked-files=normal", strip=False)
        changed = [line[3:] for line in status.splitlines() if len(line) > 3]
        out["changed"] = changed[:200]
        out["changed_count"] = len(changed)
        out["dirty"] = bool(changed)
        if changed and out["commit"]:
            r = code_git._git(root, ["diff", "--no-color", "--no-ext-diff", "--no-textconv", "--binary", "HEAD", "--", "."],
                              check=False)
            patch = r.stdout if r.returncode == 0 else b""
            out["diff_sha256"] = hashlib.sha256(patch).hexdigest()
            out["diff_bytes"] = len(patch)
            untracked = [c for c, line in zip(changed, status.splitlines()) if line.startswith("??")]
            out["untracked"] = untracked[:100]
            if patch_dir is not None and 0 < len(patch) <= MAX_PATCH:
                path = os.path.join(str(patch_dir), "uncommitted.diff")
                with open(path, "wb") as f:
                    f.write(patch)
                out["patch_file"] = path
            elif len(patch) > MAX_PATCH:
                out["patch_note"] = "변경이 2MB를 넘어 패치 사본을 남기지 않았습니다(해시만)."
    except Exception as e:
        out["error"] = str(e)[:200]
    return out


def _run_quiet(args, timeout=20):
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        r = subprocess.run(args, capture_output=True, timeout=timeout, stdin=subprocess.DEVNULL, creationflags=flags,
                           env=code_runner.clean_env())
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return r.stdout.decode("utf-8", errors="replace")


def capture_env(python="", extra_env=None, packages=True):
    """실행 환경. 설치·변경하지 않고 있는 정보만 읽는다. 비밀 이름의 환경 변수는 남기지 않는다."""
    env = {"os": f"{platform.system()} {platform.release()}", "machine": platform.machine(),
           "host_python": platform.python_version(), "captured": time.time()}
    variables = {k: v for k, v in os.environ.items() if ENV_KEEP.match(k) and not code_runner.SECRET_ENV.search(k)}
    for k, v in (extra_env or {}).items():
        if not code_runner.SECRET_ENV.search(k):
            variables[k] = v
    env["variables"] = {k: str(v)[:300] for k, v in sorted(variables.items())[:80]}
    if python:
        text = _run_quiet([python, "-c", "import sys, platform; print(platform.python_version()); print(sys.executable)"], 15)
        if text:
            lines = text.splitlines()
            env["python"] = lines[0].strip() if lines else ""
            env["python_path"] = lines[1].strip() if len(lines) > 1 else python
        if packages:
            text = _run_quiet([python, "-m", "pip", "freeze", "--disable-pip-version-check"], 30)
            if text is not None:
                pkgs = [p.strip() for p in text.splitlines() if p.strip() and not p.startswith("#")]
                env["packages"] = pkgs[:800]
                env["packages_sha256"] = hashlib.sha256("\n".join(sorted(pkgs)).encode("utf-8")).hexdigest()
    if shutil.which("nvidia-smi"):
        text = _run_quiet(["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"], 10)
        if text:
            env["gpus"] = [g.strip() for g in text.splitlines() if g.strip()][:8]
        head = _run_quiet(["nvidia-smi"], 10) or ""
        m = re.search(r"CUDA Version:\s*([\d.]+)", head)
        if m:
            env["cuda"] = m.group(1)
    else:
        env["gpus"] = []
    return env


class LabApi:
    _lab_picked = None
    _lab_env_cache = None

    # ---- 도우미 ----

    def _lab_call(self, fn):
        try:
            return {"ok": True, **(fn() or {})}
        except (lab_store.LabError, lab_results.ResultError, cw.WorkspaceError, code_runner.RunnerError) as e:
            return {"ok": False, "error": str(e)}
        except (TypeError, ValueError, KeyError) as e:
            return {"ok": False, "error": f"잘못된 요청입니다: {e}"}
        except OSError as e:
            return {"ok": False, "error": f"파일을 다루지 못했습니다: {e.strerror or e}"}

    def _lab_ready(self):
        lab_store.recover_once()

    def _lab_ws(self):
        """2.0: Lab은 이 PC에서만 실행한다(ssh_api: 'Lab의 작업 폴더는 그대로 로컬'). Code 화면이 원격(SSH) 폴더를 열었어도
        로컬 작업 폴더를 쓰고, 로컬 폴더가 없으면 원격 경로로 로컬 명령을 만들지 않고 거절한다."""
        if self._code_android():
            raise code_runner.RunnerError("안드로이드에서는 명령을 실행할 수 없습니다(PC 앱에서 쓰세요).")
        ws = self._workspace()
        if ws and not remote_fs.is_remote(ws):
            return ws
        if getattr(self, "_code_remote", lambda: None)():
            raise code_runner.RunnerError("Lab은 이 PC에서만 실행합니다. 지금은 원격(SSH) 작업 폴더만 열려 있어 실행할 수 없습니다. "
                                          "사이드바 아래의 '작업 폴더'에서 이 PC의 폴더를 고르세요.")
        raise cw.WorkspaceError("작업 폴더가 지정되지 않았습니다. 사이드바 아래의 '작업 폴더'에서 폴더를 고르세요.")

    def _lab_python(self):
        import runner_mcp

        try:
            return runner_mcp.interpreter()
        except Exception:
            return ""

    def _lab_emit(self, run):
        self._push({"type": "lab", "kind": "run", "run": run})

    def _lab_ref_ok(self, path, ws):
        """가져올 수 있는 파일: 작업 폴더 안이거나, 이번에 파일 고르기 창에서 사용자가 고른 것."""
        p = os.path.realpath(str(path))
        if p in (self._lab_picked or set()):
            return p
        if ws and _inside(os.path.realpath(ws), p):
            return p
        raise lab_store.LabError("작업 폴더 안의 파일이거나 '파일 고르기'로 고른 파일만 가져올 수 있습니다.")

    def _lab_rel(self, path, ws):
        if ws and _inside(os.path.realpath(ws), os.path.realpath(path)):
            return os.path.relpath(os.path.realpath(path), os.path.realpath(ws)).replace(os.sep, "/")
        return str(path)

    # ---- 상태·환경 ----

    def lab_state(self):
        def go():
            self._lab_ready()
            ws = self._workspace()
            return {"experiments": lab_store.list_experiments(), "workspace": ws, "project": self._project_key(),
                    "android": self._code_android(), "statuses": lab_store.STATUS_LABEL}
        return self._lab_call(go)

    def lab_env(self, refresh=False):
        """실행 도구가 있는지(설치하지 않는다): Python·nbconvert(Jupyter)·git·nvidia-smi."""
        def go():
            if self._lab_env_cache and not refresh:
                return self._lab_env_cache
            import code_git

            python = self._lab_python() if not self._code_android() else ""
            version = ""
            notebook = False
            if python:
                text = _run_quiet([python, "-c", "import platform; print(platform.python_version())"], 15)
                version = (text or "").strip()
                notebook = _run_quiet([python, "-c", "import nbconvert, nbformat"], 20) is not None
            out = {"python": python, "python_version": version, "notebook": notebook, "git": code_git.available(),
                   "nvidia_smi": bool(shutil.which("nvidia-smi")), "can_run": bool(python) and not self._code_android()}
            self._lab_env_cache = out
            return out
        return self._lab_call(go)

    # ---- 실험 ----

    def lab_experiment(self, experiment_id):
        def go():
            self._lab_ready()
            return {"experiment": lab_store.get_experiment(str(experiment_id))}
        return self._lab_call(go)

    def lab_experiment_save(self, data):
        def go():
            self._lab_ready()
            data_ = dict(data or {})
            settings = data_.get("settings")
            if settings is not None:
                settings = self._lab_clean_settings(settings)
            if data_.get("id"):
                fields = {k: data_[k] for k in ("name", "project", "description", "tags") if k in data_}
                if settings is not None:
                    fields["settings"] = settings
                exp = lab_store.update_experiment(str(data_["id"]), **fields)
            else:
                exp = lab_store.create_experiment(data_.get("name"), project=data_.get("project") or self._project_key(),
                                                  description=data_.get("description", ""), workspace=self._workspace(),
                                                  tags=data_.get("tags") or [], settings=settings or {})
            return {"experiment": exp}
        return self._lab_call(go)

    def _lab_clean_settings(self, s):
        s = dict(s or {})
        kind = s.get("kind") if s.get("kind") in KINDS else "command"
        out = {"kind": kind, "command": str(s.get("command") or "")[:code_runner.MAX_COMMAND],
               "script": cw.clean_rel(str(s.get("script") or "")) if s.get("script") else "",
               "params": _clean_params(s.get("params")),
               "outputs": [str(g).strip()[:200] for g in (s.get("outputs") or []) if str(g).strip()][:20],
               "timeout": max(10, min(code_runner.MAX_TIMEOUT, int(s.get("timeout") or code_runner.DEFAULT_TIMEOUT)))}
        spec = []
        for item in s.get("metric_spec") or []:
            item = {k: str(item.get(k) or "").strip()[:200] for k in ("file", "column", "key", "how", "name", "unit")}
            if item["file"] and (item["column"] or item["key"]):
                spec.append(item)
        out["metric_spec"] = spec[:50]
        return out

    def lab_experiment_delete(self, experiment_id):
        """기록만 지운다. 작업 폴더의 코드·결과 파일은 그대로 둔다."""
        def go():
            exp = lab_store.get_experiment(str(experiment_id))
            if any(r["status"] == "running" for r in exp["runs"]):
                raise lab_store.LabError("실행 중인 Run이 있습니다. 멈춘 뒤 지우세요.")
            return lab_store.delete_experiment(exp["id"])
        return self._lab_call(go)

    # ---- 실행 ----

    def _lab_spec(self, experiment_id, spec):
        exp = lab_store.get_experiment(str(experiment_id), runs=False)
        base = dict(exp.get("settings") or {})
        spec = {**base, **dict(spec or {})}
        spec["params"] = _clean_params(spec.get("params"))
        return exp, spec

    def _lab_extra_env(self, params, run_id=""):
        env = {"POSCHAT_PARAMS_JSON": json.dumps(params, ensure_ascii=False)}
        for k, v in params.items():
            env["POSCHAT_PARAM_" + re.sub(r"[^A-Za-z0-9]", "_", k).upper()] = _param_text(v)
        if run_id:
            env["POSCHAT_RUN_ID"] = run_id
        return env

    def lab_run_check(self, experiment_id, spec):
        """승인 창에 보일 정보와 한 번 쓰는 승인 토큰. 실제 명령(파라미터를 넣은 것)의 SHA-256에 묶인다."""
        def go():
            ws = self._lab_ws()
            exp, s = self._lab_spec(experiment_id, spec)
            if s.get("kind") == "notebook" and not (self.lab_env().get("notebook")):
                raise lab_store.LabError("이 PC의 Python에 Jupyter(nbconvert)가 없습니다. 설치한 뒤 다시 시도하세요"
                                         "(POSCHAT은 설치하지 않습니다).")
            command, template = build_command({**s, "_out_dir": "<Lab 기록 폴더>"} if s.get("kind") == "notebook" else s,
                                              self._lab_python())
            info = code_runner.analyze(command)
            token = secrets.token_hex(16)
            if self._code_tokens is None:
                self._code_tokens = {}
            now = time.time()
            for t, (_, at) in list(self._code_tokens.items()):
                if now - at > 300:
                    self._code_tokens.pop(t, None)
            self._code_tokens[token] = (hashlib.sha256(("lab\n" + command).encode("utf-8")).hexdigest(), now)
            return {"token": token, "command": command, "template": template, "cwd": ws, "params": s["params"],
                    "inputs": code_runner.input_files(ws, command), "timeout": s.get("timeout") or code_runner.DEFAULT_TIMEOUT,
                    "outputs": s.get("outputs") or [], "experiment": exp["name"], **info}
        return self._lab_call(go)

    def lab_run_start(self, experiment_id, spec, token, name="", notes=""):
        def go():
            ws = self._lab_ws()
            exp, s = self._lab_spec(experiment_id, spec)
            preview, _ = build_command({**s, "_out_dir": "<Lab 기록 폴더>"} if s.get("kind") == "notebook" else s,
                                       self._lab_python())
            entry = (self._code_tokens or {}).pop(str(token or ""), None)
            if not entry or entry[0] != hashlib.sha256(("lab\n" + preview).encode("utf-8")).hexdigest() or \
                    time.time() - entry[1] > 300:
                raise code_runner.RunnerError("승인한 명령과 다르거나 승인이 만료되었습니다. 다시 실행을 누르세요.")
            run = lab_store.create_run(exp["id"], status="queued", source="poschat", name=str(name or "")[:200],
                                       notes=str(notes or "")[:5000], params=s["params"], cwd=ws)
            rid = run["id"]
            out_dir = lab_store.files_dir(rid)
            command, template = build_command({**s, "_out_dir": str(out_dir)} if s.get("kind") == "notebook" else s,
                                              self._lab_python())
            code = capture_code(ws, out_dir)
            extra = self._lab_extra_env(s["params"], rid)
            started = time.time()
            masker = code_runner.Masker(self._code_secrets())
            lab_store.update_run(rid, code=code, command=masker._mask(command), command_template=masker._mask(template),
                                 started=started, env=capture_env("", extra, packages=False), status="running")

            def on_exit(rec):
                self._lab_finish(rid, rec, ws, s, started, out_dir)

            try:
                rec = self._code_runner().start(ws, command, int(s.get("timeout") or code_runner.DEFAULT_TIMEOUT),
                                                f"Lab {exp['name']}", extra_env=extra, on_exit=on_exit)
            except code_runner.RunnerError as e:
                run = lab_store.update_run(rid, status="failed", ended=time.time(), notes=f"시작하지 못했습니다: {e}")
                self._lab_emit(run)
                raise
            run = lab_store.update_run(rid, code_run_id=rec.id)  # 아주 짧은 명령이면 이미 끝난 상태일 수 있다
            self._lab_emit(run)
            python = self._lab_python()
            threading.Thread(target=self._lab_capture_env, args=(rid, python, extra), daemon=True,
                             name=f"lab-env-{rid}").start()
            return {"run": run}
        return self._lab_call(go)

    def _lab_capture_env(self, rid, python, extra):
        try:
            env = capture_env(python, extra)
            lab_store.update_run(rid, env=env)
        except Exception:
            pass

    def _lab_finish(self, rid, rec, ws, spec, started, out_dir):
        status = STATUS_MAP.get(rec.status, "failed")
        notes = []
        if rec.status == "timeout":
            notes.append("제한 시간이 지나 멈췄습니다.")
        if rec.truncated:
            notes.append("출력이 커서 화면에 다 보이지 않았습니다.")
        outputs = self._lab_collect(ws, spec.get("outputs") or [], started)
        for name in sorted(os.listdir(out_dir)) if os.path.isdir(out_dir) else []:
            p = os.path.join(out_dir, name)
            if os.path.isfile(p) and name != "uncommitted.diff":
                ref = lab_results.file_ref(p, f"(Lab 기록) {name}")
                ref["copy"] = True
                outputs.append(ref)
        metrics, warns = self._lab_apply_spec(outputs, spec.get("metric_spec") or [])
        notes += warns
        run = lab_store.get_run(rid)
        fields = dict(status=status, exit_code=rec.code, seconds=rec.seconds, ended=time.time(), log_tail=rec.output_tail[-20000:],
                      locations=rec.locations, outputs=outputs, metrics={**(run.get("metrics") or {}), **metrics})
        if notes:
            fields["notes"] = "\n".join(x for x in [run.get("notes", "")] + notes if x)
        self._lab_emit(lab_store.update_run(rid, **fields))

    def _lab_collect(self, ws, globs, since):
        """실행 뒤 결과 파일 찾기: 실험 설정의 출력 패턴에 맞고 실행 중에 바뀐 작업 폴더 안 파일(원본은 옮기지 않는다)."""
        if not globs or not ws:
            return []
        root = os.path.realpath(ws)
        out = []
        for rel, full in self._lab_walk(root):
            if any(fnmatch.fnmatch(rel, g) or fnmatch.fnmatch(os.path.basename(rel), g) for g in globs):
                try:
                    if os.path.getmtime(full) >= since - 1:
                        out.append(lab_results.file_ref(full, rel))
                except OSError:
                    continue
            if len(out) >= 50:
                break
        return out

    def _lab_walk(self, root, limit=20000):
        excludes = WALK_EXCLUDES  # Code의 제외 목록(build·out 등)은 쓰지 않는다: 결과가 흔히 거기 있다
        seen = 0
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in excludes and not d.startswith(".")]
            for name in filenames:
                seen += 1
                if seen > limit:
                    return
                full = os.path.join(dirpath, name)
                if os.path.islink(full):
                    continue
                yield os.path.relpath(full, root).replace(os.sep, "/"), full

    def _lab_apply_spec(self, outputs, spec):
        metrics, warnings = {}, []
        for item in spec:
            ref = next((o for o in outputs if fnmatch.fnmatch(o["path"], item["file"])
                        or fnmatch.fnmatch(os.path.basename(o["path"]), item["file"])), None)
            if ref is None:
                warnings.append(f"지표 '{item.get('name') or item.get('column') or item.get('key')}': "
                                f"'{item['file']}'에 맞는 결과 파일이 없습니다.")
                continue
            try:
                res = lab_results.extract(ref["abs"], [item], ref)
            except lab_results.ResultError as e:
                warnings.append(f"{ref['path']}: {e}")
                continue
            metrics.update(res["metrics"])
            warnings += res["warnings"]
        return metrics, warnings

    def lab_run_stop(self, run_id):
        def go():
            run = lab_store.get_run(str(run_id))
            if run["status"] != "running" or not run.get("code_run_id"):
                return {"run": run}
            try:
                self._code_runner().stop(run["code_run_id"])
            except code_runner.RunnerError:  # 앱을 다시 켜서 이미 없는 실행
                run = lab_store.update_run(run["id"], status="interrupted", ended=time.time())
            return {"run": run}
        return self._lab_call(go)

    def lab_run_rerun(self, run_id):
        """다시 실행할 설정(같은 명령 방식·파라미터)을 돌려준다. 실행은 화면에서 다시 승인한다."""
        def go():
            run = lab_store.get_run(str(run_id))
            exp = lab_store.get_experiment(run["experiment_id"], runs=False)
            settings = dict(exp.get("settings") or {})
            return {"spec": {**settings, "params": run.get("params") or {}}, "code": run.get("code") or {},
                    "experiment_id": exp["id"]}
        return self._lab_call(go)

    # ---- 기록 고치기·지우기 ----

    def lab_run_update(self, run_id, data):
        def go():
            data_ = dict(data or {})
            fields = {}
            if "name" in data_:
                fields["name"] = str(data_["name"] or "")[:200]
            if "notes" in data_:
                fields["notes"] = str(data_["notes"] or "")[:20000]
            if "params" in data_:
                fields["params"] = _clean_params(data_["params"])
            return {"run": lab_store.update_run(str(run_id), **fields)}
        return self._lab_call(go)

    def lab_run_delete(self, run_id):
        def go():
            run = lab_store.get_run(str(run_id))
            if run["status"] == "running":
                raise lab_store.LabError("실행 중인 Run은 지울 수 없습니다. 먼저 멈추세요.")
            return lab_store.delete_run(run["id"])
        return self._lab_call(go)

    # ---- 외부 결과 가져오기 ----

    def lab_pick_files(self):
        """파일 고르기 창. 고른 파일만 가져올 수 있게 기억한다(원본은 옮기지 않는다)."""
        def go():
            import webview

            if self._window is None or not hasattr(self._window, "create_file_dialog"):
                raise lab_store.LabError("이 화면에서는 파일 고르기 창을 열 수 없습니다.")
            kinds = "결과 파일 (*.csv;*.tsv;*.json;*.jsonl;*.txt;*.log;*.png;*.svg;*.jpg)"
            result = self._window.create_file_dialog(getattr(webview, "OPEN_DIALOG", 10), allow_multiple=True,
                                                     directory=self._workspace() or os.path.expanduser("~"),
                                                     file_types=(kinds, "모든 파일 (*.*)"))
            paths = [os.path.realpath(p) for p in (result or []) if os.path.isfile(p)]
            if self._lab_picked is None:
                self._lab_picked = set()
            self._lab_picked.update(paths)
            return {"files": [{"path": p, "name": os.path.basename(p), "kind": lab_results.kind_of(p),
                               "size": os.path.getsize(p)} for p in paths]}
        return self._lab_call(go)

    def lab_scan(self):
        """작업 폴더의 결과 파일 후보(표·그림, 최근에 바뀐 순)."""
        def go():
            ws = self._workspace()
            if not ws:
                return {"files": []}
            root = os.path.realpath(ws)
            files = []
            for rel, full in self._lab_walk(root):
                if os.path.splitext(rel)[1].lower() in SCAN_EXT:
                    try:
                        st = os.stat(full)
                    except OSError:
                        continue
                    files.append({"path": full, "rel": rel, "name": os.path.basename(rel),
                                  "kind": lab_results.kind_of(rel), "size": st.st_size, "mtime": st.st_mtime})
            files.sort(key=lambda f: f["mtime"], reverse=True)
            return {"files": files[:MAX_SCAN]}
        return self._lab_call(go)

    def lab_import(self, experiment_id, data):
        """밖에서 만든 결과(파일)나 Code 실행 기록을 Run으로 남긴다. 파일은 옮기지 않고 가리킨다."""
        def go():
            self._lab_ready()
            exp = lab_store.get_experiment(str(experiment_id), runs=False)
            data_ = dict(data or {})
            ws = self._workspace()
            outputs = []
            for p in data_.get("files") or []:
                path = self._lab_ref_ok(p, ws)
                if not os.path.isfile(path):
                    raise lab_store.LabError(f"파일이 없습니다: {p}")
                outputs.append(lab_results.file_ref(path, self._lab_rel(path, ws)))
            fields = dict(name=str(data_.get("name") or "")[:200], notes=str(data_.get("notes") or "")[:5000],
                          params=_clean_params(data_.get("params")), outputs=outputs[:50], cwd=ws)
            status, source = "imported", "import"
            if data_.get("code_run_id"):
                rec = self._code_runner().get(str(data_["code_run_id"]))
                if rec.status in ("running", "stopping"):
                    raise lab_store.LabError("아직 실행 중입니다. 끝난 뒤 가져오세요.")
                fields.update(command=rec.command, exit_code=rec.code, seconds=rec.seconds, started=rec.started,
                              ended=rec.ended or None, log_tail=rec.output_tail[-20000:], locations=rec.locations,
                              cwd=rec.cwd, code_run_id=rec.id, inputs=rec.inputs)
                status, source = STATUS_MAP.get(rec.status, "failed"), "code"
                fields["notes"] = (fields["notes"] + "\n" if fields["notes"] else "") + \
                    "Code 실행 패널의 기록에서 가져왔습니다(코드 버전·환경은 가져온 시점의 것입니다)."
            if data_.get("capture", True) and ws:
                fields["code"] = capture_code(ws)
                fields["env"] = capture_env("", {}, packages=False)
            if not outputs and not data_.get("code_run_id"):
                raise lab_store.LabError("가져올 파일을 고르세요.")
            run = lab_store.create_run(exp["id"], status=status, source=source, **fields)
            metrics, warnings = self._lab_apply_spec(outputs, (exp.get("settings") or {}).get("metric_spec") or [])
            if metrics:
                run = lab_store.update_run(run["id"], metrics=metrics)
            return {"run": run, "warnings": [w for w in warnings if "맞는 결과 파일이 없습니다" not in w]}
        return self._lab_call(go)

    # ---- 결과 보기·지표 ----

    def _lab_output(self, run_id, index):
        run = lab_store.get_run(str(run_id))
        outs = run.get("outputs") or []
        i = int(index)
        if not 0 <= i < len(outs):
            raise lab_store.LabError("결과 파일을 찾지 못했습니다.")
        ref = outs[i]
        state = lab_results.check_ref(ref)
        if state == "missing":
            raise lab_store.LabError(f"원본 파일이 없어졌습니다: {ref.get('abs') or ref.get('path')}")
        return run, ref, state

    def lab_file(self, run_id, index, offset=0, limit=100):
        def go():
            run, ref, state = self._lab_output(run_id, index)
            warn = ["가져온 뒤 파일 내용이 바뀌었습니다. 기록의 지표와 다를 수 있습니다."] if state == "changed" else []
            if ref["kind"] == "image":
                size = os.path.getsize(ref["abs"])
                if size > MAX_IMAGE:
                    raise lab_store.LabError("그림 파일이 너무 커서 미리 보지 않습니다(8MB까지).")
                with open(ref["abs"], "rb") as f:
                    data = base64.b64encode(f.read()).decode("ascii")
                mime = lab_results.IMAGE_EXT.get(os.path.splitext(ref["abs"])[1].lower(), "image/png")
                return {"kind": "image", "ref": ref, "src": f"data:{mime};base64,{data}", "warnings": warn}
            table = lab_results.read_table(ref["abs"])
            sugg = lab_results.suggest(ref["abs"])
            return {"kind": table["kind"], "ref": ref, "table": lab_results.page(table, offset, limit),
                    "numeric": sugg["columns"], "keys": sugg["keys"], "warnings": warn + sugg["warnings"]
                    + ([f"읽지 못한 줄 {table['bad_lines']}개"] if table.get("bad_lines") else [])}
        return self._lab_call(go)

    def lab_series(self, items):
        """그래프 점. items: [{run_id, index, x, y: [열...]}] — 여러 Run을 겹쳐 그린다. 통계는 전체, 점은 표본."""
        def go():
            out = []
            for item in list(items or [])[:12]:
                run, ref, _ = self._lab_output(item.get("run_id"), item.get("index", 0))
                table = lab_results.read_table(ref["abs"])
                ys = [str(y) for y in item.get("y") or []][:6]
                if not ys:
                    raise lab_store.LabError("Y축 열을 고르세요.")
                s = lab_results.series(table, str(item.get("x") or ""), ys)
                s.update(run_id=run["id"], seq=run["seq"], label=f"#{run['seq']} {run.get('name') or ''}".strip(),
                         file=ref["path"])
                out.append(s)
            return {"series": out}
        return self._lab_call(go)

    def lab_extract(self, run_id, index, spec, remember=False):
        """사용자가 고른 열·값만 지표로 남긴다. remember면 실험 설정에 넣어 다음 Run에도 같은 규칙으로 뽑는다."""
        def go():
            run, ref, _ = self._lab_output(run_id, index)
            items = []
            for item in list(spec or [])[:30]:
                items.append({k: str(item.get(k) or "").strip()[:200] for k in ("column", "key", "how", "name", "unit")})
            res = lab_results.extract(ref["abs"], items, ref)
            run = lab_store.update_run(run["id"], metrics={**(run.get("metrics") or {}), **res["metrics"]})
            if remember and res["metrics"]:
                exp = lab_store.get_experiment(run["experiment_id"], runs=False)
                settings = dict(exp.get("settings") or {})
                pattern = os.path.basename(ref["path"])
                keep = [m for m in settings.get("metric_spec") or []
                        if not (m.get("file") == pattern and (m.get("column"), m.get("key")) in
                                {(i["column"], i["key"]) for i in items})]
                settings["metric_spec"] = keep + [{**i, "file": pattern} for i in items]
                lab_store.update_experiment(exp["id"], settings=self._lab_clean_settings(settings))
            self._lab_emit(run)
            return {"run": run, "metrics": res["metrics"], "warnings": res["warnings"]}
        return self._lab_call(go)

    def lab_metric_set(self, run_id, name, value, unit=""):
        """손으로 적은 지표(출처: 사용자 입력). 숫자가 아니면 받지 않는다."""
        def go():
            run = lab_store.get_run(str(run_id))
            n, st = lab_results.to_number(value)
            if st != "ok":
                raise lab_store.LabError("지표 값은 숫자로 입력하세요(NaN·무한대는 받지 않습니다).")
            key = str(name or "").strip()[:80]
            if not key:
                raise lab_store.LabError("지표 이름을 입력하세요.")
            metrics = {**(run.get("metrics") or {}),
                       key: {"value": n, "unit": str(unit or "").strip()[:20], "source": {"manual": True, "at": time.time()}}}
            return {"run": lab_store.update_run(run["id"], metrics=metrics)}
        return self._lab_call(go)

    def lab_metric_delete(self, run_id, name):
        def go():
            run = lab_store.get_run(str(run_id))
            metrics = dict(run.get("metrics") or {})
            metrics.pop(str(name), None)
            return {"run": lab_store.update_run(run["id"], metrics=metrics)}
        return self._lab_call(go)

    def lab_compare(self, run_ids):
        def go():
            ids = [str(x) for x in (run_ids or [])][:12]
            return {"compare": lab_results.compare(lab_store.get_runs(ids))}
        return self._lab_call(go)

    # ---- AI 분석·프로젝트 기억 ----

    def _lab_context(self, exp, runs):
        lines = [f"# 실험: {exp['name']} ({exp['id']})"]
        if exp.get("description"):
            lines.append(f"설명: {exp['description']}")
        if exp.get("project"):
            lines.append(f"프로젝트: {exp['project']}")
        for r in runs:
            code = r.get("code") or {}
            env = r.get("env") or {}
            lines += ["", f"## Run #{r['seq']} ({r['id']}) {r.get('name') or ''}".rstrip(),
                      f"- 상태: {lab_store.STATUS_LABEL.get(r['status'], r['status'])}"
                      + (f", 종료 코드 {r['exit_code']}" if r.get("exit_code") is not None else "")
                      + (f", {r['seconds']}초" if r.get("seconds") else ""),
                      f"- 출처: {r.get('source')}"]
            if r.get("command"):
                lines.append(f"- 명령: {r['command'][:500]}")
            if r.get("params"):
                lines.append("- 파라미터: " + ", ".join(f"{k}={_param_text(v)}" for k, v in r["params"].items()))
            if code.get("repo"):
                lines.append(f"- 코드: 커밋 {code.get('commit', '')[:12]} 가지 {code.get('branch', '')}"
                             + (f", 커밋하지 않은 변경 {code.get('changed_count', 0)}개(재현성 제한)" if code.get("dirty") else ""))
            else:
                lines.append("- 코드: Git 기록 없음")
            if env:
                lines.append(f"- 환경: {env.get('os', '')}, Python {env.get('python') or '기록 없음'}"
                             + (f", GPU {'; '.join(env.get('gpus') or [])}" if env.get("gpus") else "")
                             + (f", CUDA {env['cuda']}" if env.get("cuda") else ""))
            metrics = r.get("metrics") or {}
            if metrics:
                lines.append("- 지표:")
                for k, m in metrics.items():
                    src = m.get("source") or {}
                    where = "사용자 입력" if src.get("manual") else \
                        f"{src.get('file', '')} {src.get('column') or src.get('json_path') or ''} {src.get('how', '')}".strip()
                    lines.append(f"  - {k} = {m.get('value')} {m.get('unit') or ''} (출처: {where})".rstrip())
            else:
                lines.append("- 지표: 기록 없음")
            if r.get("outputs"):
                lines.append("- 결과 파일: " + ", ".join(o.get("path", "") for o in r["outputs"][:10]))
            if r.get("notes"):
                lines.append(f"- 메모: {r['notes'][:1000]}")
            if r.get("log_tail"):
                lines.append("- 출력 끝부분:\n```\n" + r["log_tail"][-1500:] + "\n```")
        if len(runs) >= 2:
            cmp = lab_results.compare(runs)
            if cmp["warnings"]:
                lines += ["", "## 비교 주의"] + [f"- {w}" for w in cmp["warnings"]]
        return "\n".join(lines)

    def lab_ask(self, experiment_id, run_ids, preset="summary", question=""):
        """고른 실험·Run 기록만 채팅 첨부로 만든다(외부 데이터로 감쌈). 보내기는 화면에서 사용자가 한다."""
        def go():
            import attachments

            exp = lab_store.get_experiment(str(experiment_id))
            ids = [str(x) for x in (run_ids or [])]
            runs = [r for r in exp["runs"] if r["id"] in ids] if ids else exp["runs"][-8:]
            if not runs:
                raise lab_store.LabError("AI에게 보낼 Run이 없습니다.")
            text = self._lab_context(exp, runs[:12])
            limit = attachments.MAX_TEXT_CHARS - 1000
            if len(text) > limit:
                text = text[:limit] + "\n[길어서 뒤를 잘랐습니다]"
            wrapped = connectors.wrap_untrusted(text, f"Lab 실험 기록 {exp['name'][:40]}")
            name = re.sub(r"[\\/:*?\"<>|]", "_", f"Lab - {exp['name'][:30]}.md")
            ask = str(question or "").strip() or ASK_PRESETS.get(preset, ASK_PRESETS["summary"])
            return {"attachments": [self._code_attach(name, wrapped)], "question": ANALYSIS_RULES + "\n" + ask,
                    "runs": [r["id"] for r in runs[:12]]}
        return self._lab_call(go)

    def lab_remember(self, experiment_id, text, title="", kind="result"):
        """사용자가 고른 요약을 프로젝트 기억에 남긴다(자동으로 남기지 않는다)."""
        def go():
            import memory_store

            exp = lab_store.get_experiment(str(experiment_id), runs=False)
            body = str(text or "").strip()
            if not body:
                raise lab_store.LabError("남길 내용을 입력하세요.")
            project = self._project_key()
            if not project:
                raise lab_store.LabError("프로젝트 기억은 작업 폴더를 고른 뒤 남깁니다.")
            k = kind if kind in ("experiment", "result", "hypothesis", "decision", "note") else "result"
            entry, created = memory_store.write(body[:8000], layer="project", project=project, kind=k,
                                                title=str(title or f"Lab: {exp['name']}")[:120], tags=["lab", exp["id"]],
                                                source="lab")
            return {"entry": entry, "created": created}
        return self._lab_call(go)
