# Moatless Tree Search 

### Code for paper [SWE-Search: Enhancing Software Agents with Monte Carlo Tree Search and Iterative Refinement](https://arxiv.org/html/2410.20285v1)

Note: The original development code can be found at [https://github.com/a-antoniades/swe-planner](https://github.com/a-antoniades/swe-planner). It is only intended for reproducing the results in the paper. This is a clean refactor with a modular design, which will be maintained and extended.

<div align="center">

[![License](https://img.shields.io/badge/LICENSE-APACHE_LICENSE_2.0-yellow?style=flat-square&labelColor=lightgrey)](./LICENSE)
[![arXiv](https://img.shields.io/badge/arXiv-2408.08435-B31B1B?style=flat-square)](https://arxiv.org/html/2410.20285v1)
[![Streamlit](https://img.shields.io/badge/STREAMLIT-7C4DFF?style=flat-square)](https://streamlit.moatless.ai/)
[![Twitter](https://img.shields.io/badge/TWITTER-00ACEE?style=flat-square)](https://twitter.com/your-handle)
[![YouTube](https://img.shields.io/badge/YOUTUBE-FF0000?style=flat-square)](https://www.youtube.com/watch?v=VcEHX_TNDgQ)
</div>

<div align="center">
  <a href="assets/method.pdf" target="_blank">
    <img src="./assets/method.png" alt="Method Diagram" width="90%">
  </a>

  <p>Overview of SWE-Search showing the tree search process, where states (nodes) and actions (edges) are evaluated using contextual information and value function feedback to guide expansion.</p>
</div>

## Installation

1. Clone the repository and create a conda environment:

```bash
git clone https://github.com/aorwall/moatless-tree-search.git
cd moatless-tree-search
conda create -n moatless python=3.11
conda activate moatless
```

2. Install Poetry (if not already installed):

```bash
conda install -c conda-forge poetry
```

3. Install dependencies using Poetry:
    
```bash
poetry install
```

## Environment Setup

Before running the evaluation, you'll need to set up your environment variables. Add these to your `~/.bashrc` (bash) or `~/.zshrc` (zsh):

```bash
# Base URL for custom LLM API service (optional)
export CUSTOM_LLM_API_BASE="<your-base-url>"
export CUSTOM_LLM_API_KEY="<your-key>"

# API keys for various LLM providers (set the ones you need)
export OPENAI_API_KEY="<your-key>"
export ANTHROPIC_API_KEY="<your-key>"
export HUGGINGFACE_API_KEY="<your-key>"
export DEEPSEEK_API_KEY="<your-key>"

# API Keys for Voyage Embeddings
export VOYAGE_API_KEY="<your-key>"
export INDEX_STORE_DIR="<your-index-store-dir>" # default: /tmp/index_store

# Configuration for test environment (if using the testbed)
export TESTBED_API_KEY="<your-key>"
export TESTBED_BASE_URL="<your-base-url>"
```


## Streamlit

To launch the Streamlit app, run:

```bash
streamlit run streamlit_app.py
```

The following badges are used to indicate the status of a node:

| Badge | Shape | Color | Description |
|-------|-------|-------|-------------|
| ⭐ | Star | Green | Node is marked as resolved |
| ❌ | X | Red | Invalid edits or failed tests |
| 🟢 | Circle | Green | Correct code spans present in the context |
| 🟡 | Circle | Yellow | Either:<br>• Found files but not spans<br>• Found spans but in wrong files<br>|

## Evaluation

To run the evaluation script, use the following command:

```bash
python -m moatless.benchmark.run_evaluation \
        --model "gpt-4o-mini-2024-07-18" \
        --repo_base_dir /tmp/repos \ 
        --eval_dir "./evaluations" \
        --eval_name mts \
        --temp 0.7 \
        --num_workers 1 \
        --feedback \
        --max_iterations 100 \
        --max_expansions 5
```

You can optionally set the `--instance_id` to evaluate on a specific instance or a list of instances.

## Description of the Flow
The search algorithm operates in a loop, following these main steps to explore and evaluate possible actions:

1. **Selection:** Choose the next `Node` to expand using a `Selector` strategy. The selector evaluates the available nodes (expandable descendants) and selects the most promising one based on predefined criteria.

2. **Expansion:** Create a new child `Node` or select an existing unexecuted child.

3. **Simulation:**
   * **Action Generation and Execution:** Use the `Agent` to generate and execute an action for the `Node`:
     - Generate possible actions for the node
     - Create a system prompt and messages based on the node's history
     - Use a `CompletionModel` to generate action arguments
     - Execute the chosen action, updating the node's `FileContext` and creating an `Observation`
   * **Reward Evaluation:** If a `ValueFunction` is defined, evaluate the outcome of the action execution, assigning a reward to the `Node`.

4. **Backpropagation:** Propagate the obtained reward back up the tree, updating the value estimates and visit counts of ancestor nodes.

When the search process finishes (based on predefined stopping criteria), the algorithm determines the best solution found using a `Discriminator`, which assesses the nodes based on their rewards and other factors.

## Example: Basic Flow
Basic setup similar to the moatless-tools agent.

```python
from moatless.benchmark.swebench import load_instance, create_repository
from moatless.completion.completion import CompletionModel
from moatless.index import CodeIndex
from moatless.search_tree import SearchTree
from moatless.templates import create_basic_coding_tree
from moatless.actions import FindClass, FindFunction, FindCodeSnippet, SemanticSearch, RequestMoreContext, RequestCodeChange, Finish, Reject

index_store_dir = "/tmp/index_store"

completion_model = CompletionModel(model="gpt-4o", temperature=0.0)

repository = create_repository(instance)

code_index = CodeIndex.from_index_name(
    instance["instance_id"], index_store_dir=index_store_dir, file_repo=repository
)

actions = [
    find_class = FindClass(code_index=code_index, repository=repository)
    find_function = FindFunction(code_index=code_index, repository=repository)
    find_code_snippet = FindCodeSnippet(code_index=code_index, repository=repository)
    semantic_search = SemanticSearch(code_index=code_index, repository=repository)
    request_context = RequestMoreContext(repository=repository)
    request_code_change = RequestCodeChange(
        repository=repository, completion_model=completion_model
    )
    finish = Finish()
    reject = Reject()
]

file_context = FileContext(repo=repository)
agent = CodingAgent(actions=actions, completion=completion_model, system_prompt=SIMPLE_CODE_PROMPT)

instance = load_instance("django__django-16379")

search_tree = SearchTree.create(
    message=instance["problem_statement"],
    agent=agent,
    file_context=file_context,
    max_expansions=1,
    max_iterations=50
)

node = search_tree.run_search()
print(node.observation.message)
```

### Example: MCTS Flow

Evaluation flow with MCTS and testbeds.


```python
from moatless.benchmark.swebench import load_instance, create_repository
from moatless.completion.completion import CompletionModel
from moatless.index import CodeIndex
from moatless.search_tree import SearchTree
from moatless.templates import create_basic_coding_tree
from moatless.actions import FindClass, FindFunction, FindCodeSnippet, SemanticSearch, RequestMoreContext, RequestCodeChange, Finish, Reject
from testbeds.sdk import TestbedSDK
from moatless.runtime.testbed import TestbedEnvironment

index_store_dir = "/tmp/index_store"

completion_model = CompletionModel(model="gpt-4o-mini", temperature=0.0)

repository = create_repository(instance)

code_index = CodeIndex.from_index_name(
    instance["instance_id"], index_store_dir=index_store_dir, file_repo=repository
)


file_context = FileContext(repo=repository)


selector = BestFirstSelector()

value_function = ValueFunction(completion=completion_model)

discriminator = AgentDiscriminator(
    create_completion=self._create_completion_model(),
    debate_settings=DebateSettings(
        n_agents=self.settings.debate_n_agents,
        n_rounds=self.settings.debate_n_rounds,
    )
)

feedback = FeedbackGenerator()

instance = load_instance("django__django-16379")

runtime = TestbedEnvironment(
    testbed_sdk=TestbedSDK(),
    repository=repository,
    instance=instance
)

actions = [
    find_class = FindClass(code_index=code_index, repository=repository)
    find_function = FindFunction(code_index=code_index, repository=repository)
    find_code_snippet = FindCodeSnippet(code_index=code_index, repository=repository)
    semantic_search = SemanticSearch(code_index=code_index, repository=repository)
    request_context = RequestMoreContext(repository=repository)
    request_code_change = RequestCodeChange(
        repository=repository, completion_model=completion_model
    )
    run_tests = RunTests(code_index=code_index, repository=repository, runtime=runtime)
    finish = Finish()
    reject = Reject()
]

agent = CodingAgent(actions=actions, completion=completion_model)

search_tree = SearchTree.create(
    message=instance["problem_statement"],
    agent=agent,
    file_context=file_context,
    selector=selector,
    value_function=value_function,
    discriminator=discriminator,
    feedback_generator=feedback,
    max_iterations=100,
    max_expansions=5,
    max_depth=25,
)

node = search_tree.run_search()
print(node.observation.message)
```
