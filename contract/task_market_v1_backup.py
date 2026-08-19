# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *

class MultiAgentPro(gl.Contract):
    task_count: u256

    # Flat storage — key format: "{task_id}:{field}"
    # Fields: desc, status, worker, reward, result
    tasks: TreeMap[str, str]

    # worker_address -> "completed:total" e.g. "7:9"
    reputation: TreeMap[str, str]

    def __init__(self):
        self.task_count = u256(0)
        self.tasks = TreeMap()
        self.reputation = TreeMap()

    @gl.public.write
    def post_task(self, description: str, reward: str, worker: str) -> None:
        tid = str(self.task_count)
        self.tasks[f"{tid}:desc"] = str(description)[:200]
        self.tasks[f"{tid}:status"] = "open"
        self.tasks[f"{tid}:worker"] = str(worker)
        self.tasks[f"{tid}:reward"] = str(reward)
        self.tasks[f"{tid}:result"] = ""
        self.task_count = self.task_count + u256(1)

    @gl.public.write
    def submit_result(self, task_id: str, result: str) -> None:
        tid = str(task_id)
        status = self.tasks.get(f"{tid}:status", "")
        if status != "open":
            return
        desc = self.tasks.get(f"{tid}:desc", "")
        worker = self.tasks.get(f"{tid}:worker", "")

        result_trunc = str(result)[:400]

        def leader_fn() -> str:
            prompt = (
                f"You are judging whether submitted work satisfies the task requirements.\n"
                f"Task: {desc}\n"
                f"Submitted result: {result_trunc}\n"
                f"Judge strictly against the task requirements. "
                f"Reply ONLY: APPROVED or REJECTED"
            )
            raw = gl.nondet.exec_prompt(prompt)
            cleaned = raw.replace('\x00', '').strip().upper()
            if 'APPROVED' in cleaned:
                return 'APPROVED'
            return 'REJECTED'

        def validator_fn(leaders_res) -> bool:
            if not isinstance(leaders_res, gl.vm.Return):
                return False
            leader_verdict = leaders_res.calldata
            if not isinstance(leader_verdict, str):
                return False
            leader_verdict = leader_verdict.replace('\x00', '').strip().upper()
            if leader_verdict not in ("APPROVED", "REJECTED"):
                return False

            # Validator independently re-judges the same task/result
            prompt = (
                f"You are judging whether submitted work satisfies the task requirements.\n"
                f"Task: {desc}\n"
                f"Submitted result: {result_trunc}\n"
                f"Judge strictly against the task requirements. "
                f"Reply ONLY: APPROVED or REJECTED"
            )
            raw = gl.nondet.exec_prompt(prompt)
            validator_verdict = raw.replace('\x00', '').strip().upper()
            if 'APPROVED' in validator_verdict:
                validator_verdict = 'APPROVED'
            else:
                validator_verdict = 'REJECTED'

            return validator_verdict == leader_verdict

        verdict = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)
        verdict = verdict.replace('\x00', '').strip()

        new_status = "completed" if verdict == "APPROVED" else "failed"
        self.tasks[f"{tid}:status"] = new_status
        self.tasks[f"{tid}:result"] = result_trunc[:150]

        # Update worker reputation
        rep = self.reputation.get(worker, "0:0")
        try:
            completed_str, total_str = rep.split(":")
            completed = int(completed_str)
            total = int(total_str)
        except ValueError:
            completed = 0
            total = 0

        total += 1
        if new_status == "completed":
            completed += 1

        self.reputation[worker] = f"{completed}:{total}"

    @gl.public.view
    def get_task(self, task_id: str) -> str:
        tid = str(task_id)
        desc = self.tasks.get(f"{tid}:desc", "")
        if not desc:
            return "not found"
        status = self.tasks.get(f"{tid}:status", "")
        worker = self.tasks.get(f"{tid}:worker", "")
        reward = self.tasks.get(f"{tid}:reward", "")
        return f"Task: {desc} | Status: {status} | Worker: {worker} | Reward: {reward}"

    @gl.public.view
    def get_count(self) -> str:
        return str(self.task_count)

    @gl.public.view
    def get_status(self, task_id: str) -> str:
        return self.tasks.get(f"{str(task_id)}:status", "not found")

    @gl.public.view
    def get_result(self, task_id: str) -> str:
        result = self.tasks.get(f"{str(task_id)}:result", "")
        return result if result else "not found"

    @gl.public.view
    def get_reputation(self, worker_address: str) -> str:
        rep = self.reputation.get(str(worker_address), "")
        if not rep:
            return "no reputation"
        try:
            completed_str, total_str = rep.split(":")
            completed = int(completed_str)
            total = int(total_str)
            rate = (completed * 100) // total if total > 0 else 0
            return f"{completed}/{total} tasks completed ({rate}% success rate)"
        except ValueError:
            return "no reputation"

    @gl.public.view
    def get_all(self) -> str:
        n = int(self.task_count)
        parts = []
        for i in range(n):
            tid = str(i)
            desc = self.tasks.get(f"{tid}:desc", "")
            if desc:
                status = self.tasks.get(f"{tid}:status", "")
                reward = self.tasks.get(f"{tid}:reward", "")
                parts.append(f"{desc}|{status}|{reward}")
        return ";;".join(parts)
