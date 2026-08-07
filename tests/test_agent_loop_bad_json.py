import unittest
from types import SimpleNamespace

from agent_loop import BaseHandler, exhaust, agent_runner_loop


class StubClient:
    def __init__(self, arguments):
        self.arguments = arguments
        self.last_tools = ""

    def chat(self, messages, tools):
        response = SimpleNamespace(
            content="",
            tool_calls=[SimpleNamespace(
                id="call-1",
                function=SimpleNamespace(name="file_read", arguments=self.arguments),
            )],
        )

        def gen():
            if False:
                yield None
            return response

        return gen()


class StubHandler(BaseHandler):
    def __init__(self):
        self.parent = SimpleNamespace(task_dir=None)
        self._done_hooks = []
        self.next_prompts = []

    def turn_end_callback(self, response, tool_calls, tool_results, turn, next_prompt, exit_reason):
        self.next_prompts.append(next_prompt)
        return next_prompt


class AgentLoopBadJsonTests(unittest.TestCase):
    def test_malformed_tool_arguments_are_returned_to_model_for_retry(self):
        handler = StubHandler()
        result = exhaust(agent_runner_loop(
            StubClient('{"path":'),
            "system",
            "user",
            handler,
            tools_schema=[],
            max_turns=1,
            verbose=False,
        ))

        self.assertEqual(result, {"result": "MAX_TURNS_EXCEEDED"})
        self.assertEqual(len(handler.next_prompts), 1)
        self.assertIn("file_read", handler.next_prompts[0])
        self.assertIn("invalid JSON", handler.next_prompts[0])


if __name__ == "__main__":
    unittest.main()
