import re
import os

readme_file_path = "README.md"

# --- Content for the new ADK System Architecture section ---
mermaid_diagram_code = """
```mermaid
graph TD
    A[User Query] --> B(QueryCoordinatorAgent);
    B --> C{QueryUnderstandingAgent};
    C --> D{RAGContextAgent};
    D --> E{SQLGeneratorAgent};
    E --> F{SQLValidatorAgent};
    F -- Valid SQL --> G{DataExecutionAgent};
    G --> H{ResponseGeneratorAgent};
    H --> I[Natural Language Response];

    subgraph "Core ADK Agents"
        B; C; D; E; F; G; H;
    end

    J[Vector Store (Simulated)] <--> D;
    K[Database (BigQuery/PostgreSQL - Simulated)] <--> G;
    L[Persistent Memory (Firestore - Simulated)] <--> B;
```
"""

adk_architecture_section_content = f"""
## 🧬 System Architecture (ADK-based Refactor)

This section outlines the architecture of the Open Data QnA system after its ongoing refactoring towards the Google Agent Development Kit (ADK). The goal is to create a modular, scalable, and robust solution for natural language querying of BigQuery and PostgreSQL data, deployable on Vertex AI Agent Engine.

The system processes a user's natural language query through a pipeline of specialized ADK agents:
{mermaid_diagram_code}
### Query Flow Overview

1.  **Input**: The user submits a natural language query.
2.  **Coordination**: The `QueryCoordinatorAgent` receives the query and orchestrates the entire process. It manages the flow of data between other agents and interacts with persistent memory.
3.  **Understanding**: The `QueryUnderstandingAgent` processes the raw query. It leverages an LLM to:
    *   Rewrite the query for clarity and to incorporate context from chat history (if available).
    *   Determine the user's intent (e.g., SQL generation, greeting).
4.  **Context Retrieval (RAG)**: If the intent is SQL generation, the `RAGContextAgent` is invoked. It uses a (currently simulated) `VectorStoreRetrieverTool` to:
    *   Fetch relevant table schemas and column descriptions.
    *   Retrieve known good SQL queries (KGQs) that are similar to the user's query.
    *   Determine the `data_source_type` (BigQuery/PostgreSQL) based on the user's selected data grouping.
5.  **SQL Generation**: The `SQLGeneratorAgent` takes the (rewritten) query, the RAG context, and chat history. It uses an LLM with a specialized prompt (currently a simplified placeholder) to generate the SQL query specific to the target database type.
6.  **SQL Validation**: The `SQLValidatorAgent` receives the generated SQL and RAG context. It uses an LLM to:
    *   Check the SQL for syntax and semantic errors against the provided schemas.
    *   (Future) Potentially suggest corrections. For now, it returns validity status and notes.
7.  **Data Execution**: If the SQL is deemed valid, the `DataExecutionAgent` is called. It uses a (currently simulated) database-specific tool (`BigQueryExecutionTool` or `CloudSqlPgExecutionTool`) to:
    *   Execute the SQL query against the target database.
    *   Return the query results or any execution errors.
8.  **Response Generation**: The `ResponseGeneratorAgent` takes the original query, the executed SQL, the query results, and chat history. It uses an LLM to:
    *   Formulate a user-friendly, natural language answer based on the retrieved data.
    *   Handle cases where the query returned no results or an error.
9.  **Output**: The `QueryCoordinatorAgent` returns the final natural language response, generated SQL, and potentially the raw query results.

### Core ADK Agent Roles

*   `QueryCoordinatorAgent(BaseAgent)`: The central orchestrator. It initializes and calls all other agents in sequence, manages chat history loading and saving via the `FirestoreMemoryTool`, and formats the final output.
*   `QueryUnderstandingAgent(LlmAgent)`: Responsible for initial query analysis, rewriting for clarity (using chat history), and basic intent detection.
*   `RAGContextAgent(BaseAgent)`: Uses `VectorStoreRetrieverTool` (simulated) to fetch database schemas, column descriptions, and known good queries (KGQs) to provide context for SQL generation. It also helps determine the `data_source_type`.
*   `SQLGeneratorAgent(LlmAgent)`: Generates the SQL query using an LLM, guided by the user's query, RAG context, chat history, and (placeholder) database-specific prompts.
*   `SQLValidatorAgent(LlmAgent)`: Validates the generated SQL for correctness using an LLM and schema information.
*   `DataExecutionAgent(BaseAgent)`: Uses database-specific tools (simulated `BigQueryExecutionTool`, `CloudSqlPgExecutionTool`) to execute the validated SQL query.
*   `ResponseGeneratorAgent(LlmAgent)`: Generates a natural language response from the SQL query results, considering the original user query and chat history.

### Persistent Memory

*   The `QueryCoordinatorAgent` integrates with a `FirestoreMemoryTool` (currently simulated with an in-memory dictionary).
*   This tool is responsible for saving and loading conversation turns, including user queries, intermediate agent outputs (summarized), generated SQL, query results (summarized), and final agent responses.
*   This persisted history is used by agents like `QueryUnderstandingAgent` and `SQLGeneratorAgent` to maintain context in multi-turn conversations.

### UI Support Features (Backend)

*   **Streaming Responses**: The `ResponseGeneratorAgent` is designed to support streaming output from the LLM. The `QueryCoordinatorAgent` can request this stream but currently accumulates it into a full response before returning. This lays the groundwork for future end-to-end streaming to a UI.
*   **Agent Request Interruption**: Conceptual notes have been added to placeholder tool implementations (e.g., `VectorStoreRetrieverTool`, `BigQueryExecutionTool`) to mark where logic for checking interruption flags could be added for long-running operations. Actual interruption mechanisms would depend on the serving framework.
"""

# --- Content for the "Running the Example (ADK-based)" section ---
adk_running_example_section_content = """
## 🚀 Running the Example (ADK-based Refactor)

This section provides instructions on how to set up and run the current ADK-based refactored version of the Open Data QnA system. Please note that many components are currently using **simulated/placeholder logic** (e.g., for LLM calls, vector store interactions, database execution, and Firestore memory).

### Prerequisites

*   **Python**: Python 3.10 or higher is recommended.
*   **pip**: Python package installer, usually comes with Python.
*   **Git**: For cloning the repository.
*   **Google Cloud SDK (Optional for current simulated run)**: While not strictly required to run the current version with simulated components, it will be necessary for future integrations with actual Google Cloud services (like Vertex AI, BigQuery, Firestore, Vector Search). You can install it from [here](https://cloud.google.com/sdk/docs/install).
*   **ADK CLI (Google Agent Development Kit CLI)**: This is essential for running local tests and evaluations. Installation instructions for ADK are typically provided as part of its internal documentation or setup guide. For now, assume it's installed and available in your PATH.

### Environment Variables

For the current simulated version, no specific environment variables are strictly required to run the basic agent flow if you are executing it via a Python script that correctly sets up paths. However, for real cloud service integration, you would typically need to set:
*   `GOOGLE_APPLICATION_CREDENTIALS`: Path to your service account key JSON file.
*   `PROJECT_ID`: Your Google Cloud Project ID.
*   Other service-specific variables (e.g., database connection strings, vector store IDs).

If you intend to run the ADK CLI commands, ensure your environment is authenticated with Google Cloud (`gcloud auth application-default login`).

### Installation

1.  **Clone the Repository (if you haven't already):**
    ```bash
    git clone https://github.com/GoogleCloudPlatform/Open_Data_QnA.git
    cd Open_Data_QnA
    ```

2.  **Navigate to the ADK application directory:**
    ```bash
    cd adk_open_data_qna
    ```

3.  **Create a Virtual Environment (Recommended):**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate  # On Windows use: .venv\\Scripts\\activate
    ```

4.  **Install Dependencies:**
    The required Python packages for the ADK application are listed in `adk_open_data_qna/requirements.txt`.
    ```bash
    pip install -r requirements.txt
    ```

### Configuration

The current version uses placeholder logic and configurations:
*   **LLM Prompts**: Simplified prompts for various agents (query understanding, SQL generation, validation, response generation) are currently hardcoded as dictionaries (`DUMMY_PROMPTS`, `DUMMY_VALIDATION_PROMPTS`, etc.) directly within `adk_open_data_qna/agents/core_agents.py`. In a production system, these would be externalized (e.g., to YAML files).
*   **Tool Logic**: Tools like `VectorStoreRetrieverTool`, `BigQueryExecutionTool`, `CloudSqlPgExecutionTool`, and `FirestoreMemoryTool` use in-memory simulations and return dummy data.
*   **LLM Models**: Agents are currently configured to use a default (placeholder) Gemini model (`gemini-1.5-flash-001`) via `DEFAULT_LLM_CONFIG` in `adk_open_data_qna/agents/core_agents.py`.

No specific configuration files need to be modified to run the simulated version. When integrating with actual cloud services, configuration for API keys, project IDs, database names, vector store endpoints, etc., would typically be managed via environment variables or dedicated configuration files loaded by the application.

### Running the Main Agent (Conceptual Example)

Since there isn't a deployed ADK server endpoint yet, you can run the main `QueryCoordinatorAgent` programmatically from a Python script.

1.  Create a Python script (e.g., `run_adk_agent.py`) in the root of the repository (i.e., alongside the `adk_open_data_qna` directory, so imports work easily or ensure `adk_open_data_qna` is in `PYTHONPATH`).

    ```python
    # run_adk_agent.py
    import asyncio
    import uuid
    import os
    import sys

    # Ensure the adk_open_data_qna directory is in the Python path
    # This might be needed if running from the root of the Open_Data_QnA repo
    current_dir = os.path.dirname(os.path.abspath(__file__))
    adk_app_dir = os.path.join(current_dir, "adk_open_data_qna")
    if adk_app_dir not in sys.path:
        sys.path.insert(0, adk_app_dir)

    from agents.core_agents import QueryCoordinatorAgent

    def main_runner():
        coordinator = QueryCoordinatorAgent(name="MyOpenDataQnACoordinator")
        session_id = str(uuid.uuid4())
        print(f"Starting conversation with session_id: {session_id}")

        queries = [
            "How many customers are there in the 'sales_europe' dataset?",
            "What were the total sales last month for product X?",
            "Hello there!"
        ]

        for user_query in queries:
            print(f"\n--- User Query: {user_query} ---")
            response_data = coordinator.call(
                query=user_query,
                session_id=session_id,
                user_grouping="sales_europe",
                data_source_type="bigquery",
                enable_streaming=False
            )
            print(f"Agent Response Text: {response_data.get('response_text')}")
            if response_data.get('generated_sql'):
                print(f"Generated SQL: \n{response_data.get('generated_sql')}")
            if response_data.get('query_results'):
                print(f"Query Results (simulated): {response_data.get('query_results')}")
        print(f"\nConversation with session_id: {session_id} ended.")

    if __name__ == "__main__":
        try:
            main_runner()
        except KeyboardInterrupt:
            print("Exiting...")
    ```

2.  Run this script from the main `Open_Data_QnA` directory:
    ```bash
    python run_adk_agent.py
    ```
    (Ensure your virtual environment is activated if you created one, and `adk_open_data_qna` is in `PYTHONPATH` or the script handles `sys.path` as above).

### Running ADK Local Tests and Evaluations

The ADK CLI provides tools for testing agent methods and evaluating end-to-end agent behavior.

*   **Prerequisites for ADK CLI:**
    *   Ensure the ADK CLI is installed and configured.
    *   Your current working directory should typically be where the `adk_open_data_qna` module can be found (e.g., the root `Open_Data_QnA` directory, or `adk_open_data_qna` itself if `PYTHONPATH` is set up).
    *   The agent path provided to the CLI should correctly point to the Python file containing the agent class, and you must specify the class name.

*   **Running `.test.json` files (Unit/Method Tests):**
    Use the `adk test` command. For example, to test the `QueryUnderstandingAgent` (which is a sub-agent of `QueryCoordinatorAgent` and named accordingly):
    ```bash
    adk test adk_open_data_qna/tests/test_query_understanding_agent.test.json --agent-path adk_open_data_qna/agents/core_agents.py QueryCoordinatorAgent_QueryUnderstandingAgent
    ```
    To test the `SQLGeneratorAgent`:
    ```bash
    adk test adk_open_data_qna/tests/test_sql_generator_agent.test.json --agent-path adk_open_data_qna/agents/core_agents.py QueryCoordinatorAgent_SQLGeneratorAgent
    ```
    *(Note: The `--agent-path` and agent class name should correspond to how the ADK CLI loads and instantiates agents. If sub-agents are not directly instantiable or testable this way, tests might need to target the `QueryCoordinatorAgent` and check intermediate outputs, or test utility functions directly.)*

*   **Running `.evalset.json` files (End-to-End Evaluation):**
    Use the `adk eval` command. This typically targets your main orchestrator agent.
    ```bash
    adk eval adk_open_data_qna/tests/test_full_flow.evalset.json --agent-path adk_open_data_qna/agents/core_agents.py QueryCoordinatorAgent
    ```

    The ADK CLI will execute the defined test cases or evaluation examples and report on their success or failure based on the specified `expected_output` and `output_matcher`.

### Expected Output (Current Simulated Version)

When running the `run_adk_agent.py` script or ADK evaluations:
*   You will see **console logs** from the agents, indicating the flow of execution.
*   **Generated SQL**: For SQL-intended queries, you'll see a (placeholder) SQL query.
*   **Query Results**: These will be dummy/simulated results (e.g., `[{"total_count": 123}]`).
*   **Agent Response Text**: A natural language response based on (simulated) results.
*   **Memory Tool Logs**: Logs from `FirestoreMemoryTool` (simulated).
*   **ADK Test/Eval Output**: Summary of tests/evaluations. Current tests in `.evalset.json` are designed for dummy outputs.

This setup allows for iterative development and testing of the agentic logic even before full integration with live backend services.
"""

def main():
    try:
        with open(readme_file_path, "r", encoding="utf-8") as f:
            readme_content = f.read()
    except FileNotFoundError:
        print(f"WARNING: {readme_file_path} not found. Creating a new one with default content.")
        readme_content = f"# Open Data QnA\n\n✨ Overview\n-------------\nThis project enables conversational interaction with databases.\n\nIt is built on a modular design and currently supports the following components:\n"

    # --- 1. Ensure ADK Architecture Section exists and insert Mermaid if missing ---
    arch_section_header = "## 🧬 System Architecture (ADK-based Refactor)"
    arch_section_pos = readme_content.find(arch_section_header)

    if arch_section_pos == -1:
        insertion_marker_initial = "It is built on a modular design and currently supports the following components:"
        position_initial = readme_content.find(insertion_marker_initial)
        if position_initial != -1:
            end_of_marker_line = readme_content.find("\n", position_initial)
            insertion_point_initial = end_of_marker_line + 1 if end_of_marker_line != -1 else len(readme_content)
            readme_content = (
                readme_content[:insertion_point_initial] +
                "\n" + adk_architecture_section_content.strip() + "\n" +
                readme_content[insertion_point_initial:]
            )
            print("ADK Architecture section was missing and has been added.")
            arch_section_pos = readme_content.find(arch_section_header)
        else:
            readme_content = readme_content.strip() + "\n\n" + adk_architecture_section_content.strip() + "\n"
            print("ADK Architecture section added to end (initial marker missing).")
            arch_section_pos = readme_content.find(arch_section_header)

    if arch_section_pos != -1:
        query_flow_header = "### Query Flow Overview"
        query_flow_pos = readme_content.find(query_flow_header, arch_section_pos)
        # Determine search area for existing mermaid diagram carefully
        if query_flow_pos != -1:
            search_area_for_mermaid = readme_content[arch_section_pos : query_flow_pos]
        else: # If Query Flow Overview is not found, search till next major header or end of section
            next_major_header_match = re.search(r"\n## ", readme_content[arch_section_pos + len(arch_section_header):])
            if next_major_header_match:
                search_area_for_mermaid = readme_content[arch_section_pos : arch_section_pos + len(arch_section_header) + next_major_header_match.start()]
            else:
                search_area_for_mermaid = readme_content[arch_section_pos:]


        if "```mermaid" not in search_area_for_mermaid:
            insertion_marker_mermaid = "The system processes a user's natural language query through a pipeline of specialized ADK agents:"
            position_mermaid = readme_content.find(insertion_marker_mermaid, arch_section_pos)
            if position_mermaid != -1 and position_mermaid < (query_flow_pos if query_flow_pos != -1 else len(readme_content)): # Ensure marker is within arch section
                insert_at = position_mermaid + len(insertion_marker_mermaid)
                # Check if diagram is already immediately after this line (with 2 newlines)
                check_existing_diagram = readme_content[insert_at:insert_at+len(mermaid_diagram_code)+20]
                if "```mermaid" not in check_existing_diagram:
                    readme_content = readme_content[:insert_at] + "\n\n" + mermaid_diagram_code.strip() + "\n" + readme_content[insert_at:]
                    print("Mermaid diagram inserted into ADK Architecture section.")
                else:
                    print("Mermaid diagram likely already present immediately after marker.")
            else:
                print("Warning: Specific text for Mermaid diagram insertion not found or misplaced within ADK Arch section. Diagram may not be added as intended.")
        else:
            print("Mermaid diagram likely already present in ADK Architecture section (found in search_area).")

    # --- 2. Insert the "Running the Example" section ---
    running_example_header = "## 🚀 Running the Example (ADK-based Refactor)"
    if running_example_header not in readme_content:
        insertion_marker_running_ex = arch_section_header # Should be after this section
        position_running_ex = readme_content.rfind(insertion_marker_running_ex) # Find the last occurrence in case of issues

        if position_running_ex != -1:
            # Find the end of the entire ADK architecture section before inserting the new one
            # This means finding where adk_architecture_section_content *actually* ends.
            # A simple way is to find the last distinctive line of that section.
            last_line_of_arch_section = "Actual interruption mechanisms would depend on the serving framework."
            end_of_arch_section_actual = readme_content.find(last_line_of_arch_section, position_running_ex)

            if end_of_arch_section_actual != -1:
                insertion_point_running_ex = end_of_arch_section_actual + len(last_line_of_arch_section)
            else: # Fallback: find the next major header or end of file
                next_major_section_pattern = r"\n## (?!🚀)"
                end_of_arch_section_match = re.search(next_major_section_pattern, readme_content[position_running_ex:])
                if end_of_arch_section_match:
                    insertion_point_running_ex = position_running_ex + end_of_arch_section_match.start()
                else:
                    insertion_point_running_ex = len(readme_content)

            readme_content = (
                readme_content[:insertion_point_running_ex].rstrip() +
                "\n\n" + adk_running_example_section_content.strip() + "\n\n" +
                readme_content[insertion_point_running_ex:].lstrip()
            )
            print(f"'{running_example_header}' section inserted.")
        else:
            readme_content = readme_content.strip() + "\n\n" + adk_running_example_section_content.strip() + "\n"
            print(f"Warning: ADK Arch section marker not found. '{running_example_header}' appended to end.")
    else:
        print(f"'{running_example_header}' section likely already present.")

    with open(readme_file_path, "w", encoding="utf-8") as f:
        f.write(readme_content)

    print(f"README.md update script completed.")

if __name__ == "__main__":
    main()
