import json
import logging
from typing import List, Type

from moatless.actions import (
    FindClass,
    FindFunction,
    FindCodeSnippet,
    SemanticSearch,
    ViewCode,
)
from moatless.actions.action import Action
from moatless.actions.append_string import AppendString
from moatless.actions.apply_change_and_test import ApplyCodeChangeAndTest
from moatless.actions.code_change import RequestCodeChange
from moatless.actions.create_file import CreateFile
from moatless.actions.edit import ClaudeEditTool
from moatless.actions.finish import Finish
from moatless.actions.insert_line import InsertLine
from moatless.actions.list_files import ListFiles
from moatless.actions.reject import Reject
from moatless.actions.run_tests import RunTests
from moatless.actions.string_replace import StringReplace
from moatless.agent.agent import ActionAgent
from moatless.agent.code_prompts import (
    CLAUDE_REACT_PROMPT,
    REACT_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    SIMPLE_CODE_PROMPT,
)
from moatless.completion.completion import (
    LLMResponseFormat,
    CompletionModel,
)
from moatless.index import CodeIndex
from moatless.message_history import MessageHistoryGenerator
from moatless.node import Node
from moatless.repository.repository import Repository
from moatless.runtime.runtime import RuntimeEnvironment
from moatless.schema import MessageHistoryType

logger = logging.getLogger(__name__)


class CodingAgent(ActionAgent):

    @classmethod
    def create(
        cls,
        repository: Repository,
        completion_model: CompletionModel,
        code_index: CodeIndex | None = None,
        runtime: RuntimeEnvironment | None = None,
        edit_completion_model: CompletionModel | None = None,
        message_history_type: MessageHistoryType | None = None,
        **kwargs,
    ):
        if completion_model.supports_anthropic_computer_use:
            actions = create_claude_coding_actions(
                repository=repository,
                code_index=code_index,
                completion_model=completion_model,
            )
            system_prompt = CLAUDE_REACT_PROMPT
            action_type = "Claude actions with computer use capability"
            use_few_shots = False
        else:
            actions = create_edit_code_actions(
                repository=repository,
                code_index=code_index,
                completion_model=completion_model,
            )
            system_prompt = SYSTEM_PROMPT
            action_type = "standard edit code actions"
            use_few_shots = True

        if message_history_type is None:
            if completion_model.response_format == LLMResponseFormat.TOOLS:
                message_history_type = MessageHistoryType.MESSAGES
            else:
                message_history_type = MessageHistoryType.REACT

        message_generator = MessageHistoryGenerator(
            message_history_type=message_history_type,
            include_file_context=True
        )

        config = {
            "completion_model": completion_model.__class__.__name__,
            "code_index_enabled": code_index is not None,
            "runtime_enabled": runtime is not None,
            "edit_completion_model": edit_completion_model.__class__.__name__ if edit_completion_model else None,
            "action_type": action_type,
            "actions": [a.__class__.__name__ for a in actions],
            "message_history_type": message_history_type.value,
            "file_context_enabled": True
        }
        
        logger.info(f"Created CodingAgent with configuration: {json.dumps(config, indent=2)}")

        return cls(
            completion=completion_model,
            actions=actions,
            system_prompt=system_prompt,
            message_generator=message_generator,
            use_few_shots=use_few_shots,
            **kwargs,
        )


def create_base_actions(
    repository: Repository,
    code_index: CodeIndex | None = None,
    completion_model: CompletionModel | None = None,
) -> List[Action]:
    """Create the common base actions used across all action creators."""
    return [
        SemanticSearch(
            code_index=code_index,
            repository=repository,
            completion_model=completion_model,
        ),
        FindClass(
            code_index=code_index,
            repository=repository,
            completion_model=completion_model,
        ),
        FindFunction(
            code_index=code_index,
            repository=repository,
            completion_model=completion_model,
        ),
        FindCodeSnippet(
            code_index=code_index,
            repository=repository,
            completion_model=completion_model,
        ),
        ViewCode(repository=repository),
    ]


def create_coding_actions(
    repository: Repository,
    code_index: CodeIndex | None = None,
    runtime: RuntimeEnvironment | None = None,
    identify_completion_model: CompletionModel | None = None,
    edit_completion_model: CompletionModel | None = None,
) -> List[Action]:
    actions = create_base_actions(repository, code_index, identify_completion_model)

    if runtime:
        actions.append(
            ApplyCodeChangeAndTest(
                code_index=code_index,
                repository=repository,
                runtime=runtime,
                completion_model=edit_completion_model,
            )
        )
        actions.append(
            RunTests(repository=repository, runtime=runtime, code_index=code_index)
        )
    else:
        actions.append(
            RequestCodeChange(
                repository=repository, completion_model=edit_completion_model
            )
        )

    actions.extend([Finish(), Reject()])
    return actions


def create_edit_code_actions(
    repository: Repository,
    code_index: CodeIndex | None = None,
    completion_model: CompletionModel | None = None,
) -> List[Action]:
    """Create a list of simple code modification actions."""
    actions = create_base_actions(repository, code_index, completion_model)

    edit_actions = [
        StringReplace(repository=repository, code_index=code_index),
        # InsertLine(repository=repository,  code_index=code_index),
        CreateFile(repository=repository, code_index=code_index),
        AppendString(repository=repository, code_index=code_index),
        RunTests(repository=repository, code_index=code_index),
    ]

    actions.extend(edit_actions)
    actions.extend([Finish(), Reject()])
    return actions


def create_claude_coding_actions(
    repository: Repository,
    code_index: CodeIndex | None = None,
    completion_model: CompletionModel | None = None,
) -> List[Action]:
    actions = create_base_actions(repository, code_index, completion_model)
    actions.append(
        ClaudeEditTool(code_index=code_index, repository=repository),

    )
    actions.append(ListFiles())
    actions.append(RunTests(repository=repository, code_index=code_index))
    actions.extend([Finish(), Reject()])
    return actions


def create_all_actions(repository: Repository, code_index: CodeIndex | None = None, completion_model: CompletionModel | None = None) -> List[Action]:
    actions = create_base_actions(repository, code_index, completion_model)
    actions.extend(create_edit_code_actions(repository, code_index, completion_model))
    actions.append(ClaudeEditTool(code_index=code_index, repository=repository))
    return actions