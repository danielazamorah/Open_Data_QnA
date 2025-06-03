class QueryCoordinatorAgent(BaseAgent):
    """Orchestrates the entire query process from user question to final response."""
    def __init__(self, llm_config: GcpVertexAiLlm = DEFAULT_LLM_CONFIG, **kwargs):
        super().__init__(**kwargs)
        # Initialize child agents
        agent_name_prefix = kwargs.get("name", "QueryCoordinator")
        self.query_understanding_agent = QueryUnderstandingAgent(llm=llm_config, name=f"{agent_name_prefix}_QueryUnderstandingAgent")
        self.rag_context_agent = RAGContextAgent(name=f"{agent_name_prefix}_RAGContextAgent")
        self.sql_generator_agent = SQLGeneratorAgent(llm=llm_config, name=f"{agent_name_prefix}_SQLGeneratorAgent")
        self.sql_validator_agent = SQLValidatorAgent(llm=llm_config, name=f"{agent_name_prefix}_SQLValidatorAgent")
        self.data_execution_agent = DataExecutionAgent(name=f"{agent_name_prefix}_DataExecutionAgent")
        self.response_generator_agent = ResponseGeneratorAgent(llm=llm_config, name=f"{agent_name_prefix}_ResponseGeneratorAgent")

        # Initialize memory tool
        self.memory_tool = FirestoreMemoryTool()

def call(self, query: str, session_id: str = None, user_grouping: str = "default_grouping", data_source_type: str = "bigquery", enable_streaming: bool = False, **kwargs) -> dict:
        """
        Main orchestration logic including memory interaction and handling streaming for response.
        Args:
            query (str): The user's natural language query.
            session_id (str, optional): The current session ID. If None, memory will not be used.
            user_grouping (str, optional): The database/schema grouping.
            data_source_type (str, optional): Type of the data source.
            enable_streaming (bool, optional): If true, requests streaming from response generator.
                                             Coordinator currently accumulates this stream.
            **kwargs: Additional arguments
        Returns:
            dict: A dictionary containing the final response and intermediate results.
        """
        print(f"{self.name}: Received query='{query[:100]}' for session='{session_id}', grouping='{user_grouping}', streaming: {enable_streaming}")

        chat_history = []
        if session_id:
            chat_history = self.memory_tool.load_session_history(session_id=session_id, limit=10)

        understanding_result = self.query_understanding_agent.call(query=query, chat_history=chat_history)
        rewritten_query = understanding_result.get("rewritten_query", query)
        intent = understanding_result.get("intent", "sql_generation")

        if intent != "sql_generation":
            response_text = understanding_result.get("error", "Intent not handled for SQL generation.")
            if session_id: self.memory_tool.save_turn(session_id, {"user_query": query, "intent": intent, "agent_response": response_text, "understanding_result": understanding_result})
            return {"response_text": response_text, "intermediate_results": {}}

        rag_context = self.rag_context_agent.call(rewritten_query=rewritten_query, user_grouping=user_grouping)
        effective_data_source_type = rag_context.get("data_source_type", data_source_type)

        sql_generation_result = self.sql_generator_agent.call(query=rewritten_query, context=rag_context, chat_history=chat_history)
        generated_sql = sql_generation_result.get("sql_query")

        if not generated_sql:
            response_text = sql_generation_result.get("message_from_llm") or sql_generation_result.get("error", "Failed to generate SQL query.")
            if session_id: self.memory_tool.save_turn(session_id, {"user_query": query, "rewritten_query": rewritten_query, "agent_response": response_text, "sql_generation_result": sql_generation_result})
            return {"response_text": response_text, "intermediate_results": {}}

        validation_result = self.sql_validator_agent.call(sql_query=generated_sql, context=rag_context)
        validated_sql = validation_result.get("corrected_sql", generated_sql)

        if not validation_result.get("is_valid", False):
            response_text = f"Generated SQL query is invalid: {validation_result.get('validation_notes', '')}"
            if session_id: self.memory_tool.save_turn(session_id, {"user_query": query, "generated_sql": generated_sql, "agent_response": response_text, "sql_validation_result": validation_result})
            return {"response_text": response_text, "generated_sql": generated_sql, "intermediate_results": {}}

        execution_result = self.data_execution_agent.call(sql_query=validated_sql, data_source_type=effective_data_source_type, user_grouping=user_grouping)
        query_results_data = execution_result.get("results")

        if execution_result.get("error") or query_results_data is None:
            response_text = f"Failed to execute SQL query: {execution_result.get('error', 'No results returned.')}"
            if session_id: self.memory_tool.save_turn(session_id, {"user_query": query, "generated_sql": validated_sql, "agent_response": response_text, "data_execution_result": execution_result})
            return {"response_text": response_text, "generated_sql": validated_sql, "intermediate_results": {}}

        final_response_obj = self.response_generator_agent.call(
            original_query=query, sql_query=validated_sql, results=execution_result,
            chat_history=chat_history, stream=enable_streaming
        )

        final_response_text = ""
        if final_response_obj.get("error"):
            final_response_text = final_response_obj.get("response_text", f"Error in response generation: {final_response_obj['error']}")
        elif enable_streaming and final_response_obj.get("response_stream"):
            print(f"{self.name}: Accumulating stream from ResponseGeneratorAgent...")
            accumulated_response = [str(chunk) for chunk in final_response_obj["response_stream"]] # Ensure chunks are strings
            final_response_text = "".join(accumulated_response)
            print(f"{self.name}: Stream accumulated. Total length: {len(final_response_text)}")
        elif final_response_obj.get("response_text"):
            final_response_text = final_response_obj["response_text"]
        else:
            final_response_text = "Could not generate a final response (empty)."

        if session_id:
            # Simplified turn data for brevity in this example
            turn_data_success = {
                "user_query": query, "rewritten_query": rewritten_query, "generated_sql": validated_sql,
                "agent_response": final_response_text, "row_count": execution_result.get('row_count',0)
            }
            self.memory_tool.save_turn(session_id, turn_data_success)

        return {
            "response_text": final_response_text,
            "generated_sql": validated_sql,
            "query_results": query_results_data,
        }

class QueryUnderstandingAgent(LlmAgent):
    """Analyzes the user query, rewrites it for clarity, and determines intent/routing."""
    DEFAULT_PROMPT_TEMPLATE = """
You are an expert at understanding user queries and conversation history.
Your tasks are:
1. Rewrite the 'Current User Query' to be a standalone question that incorporates relevant context from the 'Chat History'.
   If the query is already standalone, or if there's no chat history, use the original query.
   The rewritten query should be optimized for generating a SQL query against a database.
2. Determine the intent of the 'Current User Query'. Possible intents are: 'sql_generation', 'greeting', 'farewell', 'general_knowledge', 'unclear'.

Chat History (recent turns first):
{chat_history}

Current User Query:
{query}

Provide your response as a JSON object with two keys: 'rewritten_query' and 'intent'.
Example:
{
  "rewritten_query": "Show me the total sales for product X in the last quarter, including regional breakdown.",
  "intent": "sql_generation"
}
"""

    def __init__(self, llm: GcpVertexAiLlm = DEFAULT_LLM_CONFIG, prompt_template: str = None, **kwargs):
        super().__init__(llm=llm, **kwargs)
        self.prompt_template = prompt_template or self.DEFAULT_PROMPT_TEMPLATE

    def _format_chat_history(self, chat_history: list) -> str:
        if not chat_history:
            return "No history available."
        # Assuming chat_history is a list of dicts like {"role": "user/assistant", "content": "..."}
        # Or it might be the format from the original codebase: {"user_question": "...", "bot_response": "..."}
        # For ADK, it's typically adk.Message objects, convert to string.
        formatted_history = []
        for entry in reversed(chat_history[-5:]): # Last 5 turns
            if hasattr(entry, 'role') and hasattr(entry, 'content'): # ADK Message
                 formatted_history.append(f"{entry.role.capitalize()}: {entry.content}")
            elif isinstance(entry, dict) and "user_question" in entry and "bot_response" in entry: # Old format
                formatted_history.append(f"User: {entry['user_question']}")
                if entry['bot_response']:
                    formatted_history.append(f"Assistant: {entry['bot_response']}")
            elif isinstance(entry, dict) and "role" in entry and "content" in entry: # Generic dict format
                 formatted_history.append(f"{entry['role'].capitalize()}: {entry['content']}")
        return "\n".join(formatted_history) if formatted_history else "No history available."

    def call(self, query: str, chat_history: list = None, **kwargs) -> dict:
        """
        Analyzes the query using an LLM.

        Args:
            query (str): The user's current query.
            chat_history (list, optional): A list of previous conversation turns.
                                          Each turn can be an ADK Message or a dict.

        Returns:
            dict: Containing 'rewritten_query' and 'intent'.
        """
        formatted_history_str = self._format_chat_history(chat_history)

        prompt = self.prompt_template.format(
            chat_history=formatted_history_str,
            query=query
        )

        print(f"{self.name}: Calling LLM for query understanding. Prompt: {prompt[:500]}...") # Log snippet

        try:
            llm_response_str = super().call(prompt=prompt) # LlmAgent's call method

            # Attempt to parse the JSON response
            # The LLM is instructed to return JSON, but it might fail.
            # Basic parsing, can be made more robust.
            match = re.search(r"{\s*\"rewritten_query\":\s*\"(.*?)\",\s*\"intent\":\s*\"(.*?)\"\s*}", llm_response_str, re.DOTALL)
            if match:
                rewritten_query = match.group(1).strip()
                intent = match.group(2).strip()
                # Handle potential escape sequences if LLM adds them (e.g., \" -> ")
                rewritten_query = rewritten_query.replace('\\"', '"')
                print(f"{self.name}: LLM response parsed: rewritten='{rewritten_query}', intent='{intent}'")
                return {"rewritten_query": rewritten_query, "intent": intent}
            else:
                print(f"{self.name}: Failed to parse LLM response JSON: {llm_response_str}")
                # Fallback: use original query, assume sql_generation
                return {"rewritten_query": query, "intent": "sql_generation", "error": "llm_response_parsing_failed"}
        except Exception as e:
            print(f"{self.name}: Error during LLM call or processing: {e}")
            return {"rewritten_query": query, "intent": "sql_generation", "error": str(e)}

class RAGContextAgent(BaseAgent):
    """Retrieves relevant context (schemas, KGQs) from vector stores using tools."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.retriever_tool = VectorStoreRetrieverTool()
        # In a real scenario, an embedder agent/tool would also be needed here
        # or embeddings passed into the call method.

    def call(self, rewritten_query: str, user_grouping: str, **kwargs) -> dict:
        """
        Retrieves RAG context.

        Args:
            rewritten_query (str): The (potentially rewritten) user query.
            user_grouping (str): The database/schema grouping.

        Returns:
            dict: Containing table_schemas, column_schemas, and known_good_queries.
        """
        print(f"{self.name}: Retrieving context for query='{rewritten_query[:50]}...', grouping='{user_grouping}'")

        # Placeholder for actual embedding generation for the rewritten_query.
        # For now, the tool itself generates a dummy one based on the string.
        # embedding = self.embedder_agent.embed(rewritten_query)

        table_schema_result = self.retriever_tool.call(
            query=rewritten_query,
            user_grouping=user_grouping,
            retrieval_type="table_schema",
            top_k=5 # Example: make configurable
        )

        column_schema_result = self.retriever_tool.call(
            query=rewritten_query,
            user_grouping=user_grouping,
            retrieval_type="column_schema",
            top_k=10 # Example: make configurable
        )

        kgq_result = self.retriever_tool.call(
            query=rewritten_query,
            user_grouping=user_grouping,
            retrieval_type="known_good_queries",
            top_k=3 # Example: make configurable
        )

        # Also fetch data source type, which might be needed by other agents (e.g. SQLGenerator)
        # This is a simplified way; in a real system, user_grouping might map to a detailed config.
        data_source_info_result = self.retriever_tool.call(
            query="", # Query not really needed for this specific type
            user_grouping=user_grouping,
            retrieval_type="data_source_type"
        )
        data_source_type = "unknown"
        if data_source_info_result["retrieved_items"]:
            data_source_type = data_source_info_result["retrieved_items"][0].get("source_type", "unknown")

        context = {
            "table_schemas": table_schema_result.get("retrieved_items", []),
            "column_schemas": column_schema_result.get("retrieved_items", []),
            "known_good_queries": kgq_result.get("retrieved_items", []),
            "data_source_type": data_source_type, # Add this to the context
            "user_grouping": user_grouping, # Pass along for clarity
            "notes": {
                "table_schema_notes": table_schema_result.get("notes"),
                "column_schema_notes": column_schema_result.get("notes"),
                "kgq_notes": kgq_result.get("notes"),
                "data_source_notes": data_source_info_result.get("notes")
            }
        }

        print(f"{self.name}: Context assembled: { {k: v for k, v in context.items() if k != 'notes'} }") # Print without verbose notes
        return context

class SQLGeneratorAgent(LlmAgent):
    """Generates SQL based on the query and retrieved RAG context."""

    def __init__(self, llm: GcpVertexAiLlm = DEFAULT_LLM_CONFIG, prompts: dict = None, **kwargs):
        super().__init__(llm=llm, **kwargs)
        self.prompts = prompts or DUMMY_PROMPTS # Allow injecting prompts, use dummy for now

    def _format_rag_context_for_prompt(self, context: dict) -> tuple:
        tables_schema_str = "\n".join(context.get("table_schemas", ["No table schemas provided."]))
        columns_schema_str = "\n".join(context.get("column_schemas", ["No column schemas provided."]))
        similar_sql_str = "\n".join(context.get("known_good_queries", ["No similar SQL queries provided."]))
        return tables_schema_str, columns_schema_str, similar_sql_str

    def _format_chat_history_for_prompt(self, chat_history: list) -> str:
        if not chat_history:
            return "No history available."
        formatted_history = []
        for entry in reversed(chat_history[-3:]): # Last 3 turns for brevity in SQL prompt
            if hasattr(entry, 'role') and hasattr(entry, 'content'):
                 formatted_history.append(f"{entry.role.capitalize()}: {entry.content}")
            elif isinstance(entry, dict) and "user_question" in entry and "bot_response" in entry:
                formatted_history.append(f"User: {entry['user_question']}")
                if entry['bot_response']: # bot_response is SQL in current old system
                    formatted_history.append(f"Assistant (Generated SQL): {entry['bot_response']}")
            elif isinstance(entry, dict) and "role" in entry and "content" in entry:
                 formatted_history.append(f"{entry['role'].capitalize()}: {entry['content']}")
        return "\n".join(formatted_history) if formatted_history else "No history available."

    def call(self, query: str, context: dict, chat_history: list = None, **kwargs) -> dict:
        """
        Generates SQL using an LLM.

        Args:
            query (str): The user's (rewritten) query.
            context (dict): The context from RAGContextAgent
                            (must include 'data_source_type', 'user_grouping',
                             'table_schemas', 'column_schemas', 'known_good_queries').
            chat_history (list, optional): Conversation history.

        Returns:
            dict: Containing 'sql_query' or 'error'.
        """
        data_source_type = context.get("data_source_type", "bigquery") # Default to bigquery if not specified
        user_grouping = context.get("user_grouping", "unknown_grouping")

        # Select prompt template based on data_source_type
        # This logic can be expanded for more specific use cases / prompt versions
        prompt_key = f"buildsql_{data_source_type}_default"
        prompt_template = self.prompts.get(prompt_key)

        if not prompt_template:
            print(f"{self.name}: No prompt template found for key: {prompt_key}. Using generic bigquery.")
            prompt_template = self.prompts.get("buildsql_bigquery_default")
            if not prompt_template: # Should not happen with DUMMY_PROMPTS
                 return {"sql_query": None, "error": f"Critical: Default prompt template missing."}


        tables_schema_str, columns_schema_str, similar_sql_str = self._format_rag_context_for_prompt(context)
        chat_history_str = self._format_chat_history_for_prompt(chat_history)

        prompt = prompt_template.format(
            user_question=query,
            chat_history=chat_history_str,
            user_grouping=user_grouping,
            tables_schema=tables_schema_str,
            columns_schema=columns_schema_str,
            similar_sql=similar_sql_str
        )

        print(f"{self.name}: Calling LLM for SQL generation. Data Source: {data_source_type}. Prompt snippet: {prompt[:300]}...")

        try:
            llm_response_str = super().call(prompt=prompt)

            # Extract SQL from ```sql ... ``` or assume raw SQL
            sql_match = re.search(r"```sql\n(.*?)\n```", llm_response_str, re.DOTALL)
            if sql_match:
                generated_sql = sql_match.group(1).strip()
            elif "SELECT" in llm_response_str.upper(): # Fallback if no markdown
                generated_sql = llm_response_str.strip()
            else: # Could be "Cannot answer..." or other non-SQL response
                generated_sql = llm_response_str.strip() # Return it as is, validator can check

            print(f"{self.name}: LLM response received. Extracted SQL (or message): '{generated_sql[:300]}...'")
            # Further check if it's one of the explicit non-answer messages
            if "Cannot answer with provided context" in generated_sql:
                 return {"sql_query": None, "error": "LLM determined question cannot be answered with context.", "message_from_llm": generated_sql}

            return {"sql_query": generated_sql}

        except Exception as e:
            print(f"{self.name}: Error during LLM call or processing: {e}")
            return {"sql_query": None, "error": str(e)}

class SQLValidatorAgent(LlmAgent):
    """Validates the generated SQL for syntax and semantic correctness.
       May also attempt to debug or suggest fixes based on LLM response."""

    def __init__(self, llm: GcpVertexAiLlm = DEFAULT_LLM_CONFIG, prompts: dict = None, **kwargs):
        super().__init__(llm=llm, **kwargs)
        # In a real setup, DUMMY_VALIDATION_PROMPTS would be loaded or passed like DUMMY_PROMPTS
        self.prompts = prompts or DUMMY_VALIDATION_PROMPTS

    def _format_context_for_prompt(self, context: dict) -> tuple:
        tables_schema_str = "\n".join(context.get("table_schemas", ["No table schemas provided."]))
        columns_schema_str = "\n".join(context.get("column_schemas", ["No column schemas provided."]))
        # Known good queries are not typically used for validation directly, but schema is key.
        return tables_schema_str, columns_schema_str

    def call(self, sql_query: str, context: dict, **kwargs) -> dict:
        """
        Validates SQL using an LLM.

        Args:
            sql_query (str): The SQL query to validate.
            context (dict): The context from RAGContextAgent, primarily for schemas.
                            Expected keys: 'data_source_type', 'user_grouping',
                                           'table_schemas', 'column_schemas'.

        Returns:
            dict: Containing 'is_valid' (bool), 'corrected_sql' (str),
                  'validation_notes' (str), and optionally 'error'.
        """
        data_source_type = context.get("data_source_type", "bigquery")
        user_grouping = context.get("user_grouping", "unknown_grouping")

        prompt_template = self.prompts.get("validate_sql_default")
        if not prompt_template:
            return {
                "is_valid": False,
                "corrected_sql": sql_query,
                "validation_notes": "Critical: Validation prompt template missing.",
                "error": "Prompt template missing"
            }

        tables_schema_str, columns_schema_str = self._format_context_for_prompt(context)

        prompt = prompt_template.format(
            data_source_type=data_source_type,
            user_grouping=user_grouping,
            tables_schema=tables_schema_str,
            columns_schema=columns_schema_str,
            sql_query=sql_query
        )

        print(f"{self.name}: Calling LLM for SQL validation. Prompt snippet: {prompt[:300]}...")

        try:
            llm_response_str = super().call(prompt=prompt)
            print(f"{self.name}: LLM validation response raw: {llm_response_str[:500]}")

            # Attempt to parse JSON response (more robust parsing needed for production)
            try:
                # A common way LLMs return JSON is inside ```json ... ```
                json_match = re.search(r"```json\n(.*?)\n```", llm_response_str, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else: # Assume the whole response is JSON or contains it
                    json_str = llm_response_str[llm_response_str.find('{'):llm_response_str.rfind('}')+1]

                parsed_response = json.loads(json_str)
                is_valid = parsed_response.get("is_valid", False)
                validation_notes = parsed_response.get("validation_notes", "No validation notes from LLM.")
                corrected_sql = parsed_response.get("corrected_sql", sql_query)

                # If LLM returns original SQL as corrected, but says it's invalid, ensure notes reflect that.
                if not is_valid and corrected_sql == sql_query and "Query appears valid" in validation_notes:
                    validation_notes = "LLM indicated invalid but did not provide a correction or clear reason."

                print(f"{self.name}: Parsed validation: valid={is_valid}, notes='{validation_notes[:100]}...', corrected_sql='{corrected_sql[:100]}...'")
                return {
                    "is_valid": is_valid,
                    "corrected_sql": corrected_sql,
                    "validation_notes": validation_notes
                }
            except Exception as parse_error: # Includes json.JSONDecodeError
                print(f"{self.name}: Failed to parse JSON from LLM validation response: {parse_error}. Response: {llm_response_str}")
                # Fallback: treat as invalid if parsing fails, as we can't be sure.
                return {
                    "is_valid": False,
                    "corrected_sql": sql_query,
                    "validation_notes": f"Failed to parse LLM validation response. Raw: {llm_response_str[:200]}",
                    "error": "parsing_llm_output_failed"
                }

        except Exception as e:
            print(f"{self.name}: Error during LLM call for validation: {e}")
            return {
                "is_valid": False, # Assume invalid on error
                "corrected_sql": sql_query,
                "validation_notes": f"Error during LLM call: {e}",
                "error": str(e)
            }

class DataExecutionAgent(BaseAgent):
    """Executes the validated SQL query against the appropriate database using tools."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bq_tool = BigQueryExecutionTool()
        self.cloudsql_pg_tool = CloudSqlPgExecutionTool()
        # Configuration for project_id, instance_name etc. would be loaded here in a real app

    def call(self, sql_query: str, data_source_type: str, user_grouping: str, **kwargs) -> dict:
        """
        Executes the SQL query.

        Args:
            sql_query (str): The validated SQL query.
            data_source_type (str): 'bigquery' or 'cloudsql_postgres'.
            user_grouping (str): Database/schema identifier, used by tools.

        Returns:
            dict: Containing 'results', 'row_count', and 'error' (if any).
        """
        print(f"{self.name}: Received SQL='{sql_query[:100]}...' for source='{data_source_type}', grouping='{user_grouping}'")

        if data_source_type == "bigquery":
            execution_output = self.bq_tool.call(
                sql_query=sql_query,
                user_grouping=user_grouping
            )
        elif data_source_type == "cloudsql_postgres":
            execution_output = self.cloudsql_pg_tool.call(
                sql_query=sql_query,
                user_grouping=user_grouping
            )
        else:
            print(f"{self.name}: Unsupported data source type: {data_source_type}")
            return {"results": None, "row_count": 0, "error": f"Unsupported data source type: {data_source_type}"}

        if execution_output.get("error"):
            print(f"{self.name}: Execution failed. Error: {execution_output['error']}")
        else:
            print(f"{self.name}: Execution successful. Rows: {execution_output.get('row_count', 0)}")

        return execution_output

class ResponseGeneratorAgent(LlmAgent):
    """Generates a natural language response based on the query results. Supports streaming."""

    def __init__(self, llm: GcpVertexAiLlm = DEFAULT_LLM_CONFIG, prompts: dict = None, **kwargs):
        super().__init__(llm=llm, **kwargs)
        self.prompts = prompts or DUMMY_RESPONSE_PROMPTS # Assumes DUMMY_RESPONSE_PROMPTS is defined globally in the file

    def _format_query_results_for_prompt(self, results: dict) -> str:
        if results.get("error"):
            return f"An error occurred during query execution: {results['error']}"
        if results.get("results") is None or results.get("row_count", 0) == 0:
            return "The query returned no results."

        actual_results = results.get("results")
        if isinstance(actual_results, str):
            return actual_results

        try:
            MAX_ROWS_FOR_PROMPT = 5
            if isinstance(actual_results, list) and len(actual_results) > MAX_ROWS_FOR_PROMPT:
                return json.dumps(actual_results[:MAX_ROWS_FOR_PROMPT], indent=2) + \
                       f"\n... (and {len(actual_results) - MAX_ROWS_FOR_PROMPT} more rows)"
            return json.dumps(actual_results, indent=2)
        except TypeError: # Handle non-serializable data if any
            return str(actual_results)


    def _format_chat_history_for_prompt(self, chat_history: list) -> str:
        if not chat_history:
            return "No history available."
        formatted_history = []
        for entry in reversed(chat_history[-3:]): # Last 3 turns
            role = "Unknown"
            content = ""
            if hasattr(entry, 'role') and hasattr(entry, 'content'): # ADK Message
                 role = entry.role.capitalize()
                 content = entry.content
            elif isinstance(entry, dict) and "user_question" in entry: # Old format - user part
                role = "User"
                content = entry["user_question"]
                formatted_history.append(f"{role}: {content}")
                if "bot_response" in entry and entry["bot_response"]: # Old format - assistant part
                    # For response generation, bot_response might be natural lang or SQL.
                    # Let's assume it's the natural language response if available.
                    formatted_history.append(f"Assistant: {entry['bot_response']}")
                continue # Skip generic dict processing for this format
            elif isinstance(entry, dict) and "role" in entry and "content" in entry: # Generic dict
                 role = entry["role"].capitalize()
                 content = entry["content"]

            if content: # Add only if content is not empty
                formatted_history.append(f"{role}: {content}")
        return "\n".join(formatted_history) if formatted_history else "No history available."


    def call(self, original_query: str, sql_query: str, results: dict, chat_history: list = None, stream: bool = False, **kwargs) -> dict:
        """
        Generates a natural language response.

        Args:
            original_query (str): The user's original query.
            sql_query (str): The SQL query that was executed.
            results (dict): The results from DataExecutionAgent (contains 'results', 'row_count', 'error').
            chat_history (list, optional): Conversation history.
            stream (bool, optional): Whether to stream the response from the LLM.

        Returns:
            dict: Containing 'response_text' or 'response_stream' or 'error'.
        """
        prompt_template = self.prompts.get("generate_response_default")
        if not prompt_template:
            return {"response_text": "Critical: Response generation prompt template missing.", "error": "Prompt template missing"}

        query_results_str = self._format_query_results_for_prompt(results)
        chat_history_str = self._format_chat_history_for_prompt(chat_history)

        prompt = prompt_template.format(
            original_query=original_query,
            sql_query=sql_query,
            query_results_str=query_results_str,
            chat_history_str=chat_history_str
        )

        print(f"{self.name}: Calling LLM for response generation. Stream: {stream}. Prompt snippet: {prompt[:100]}...")

        try:
            if stream:
                response_stream = super().call(prompt=prompt, stream=True)
                print(f"{self.name}: LLM stream initiated.")
                return {"response_stream": response_stream, "error": None}
            else:
                llm_response_str = super().call(prompt=prompt, stream=False)
                response_text = llm_response_str.strip()
                print(f"{self.name}: LLM response received (non-streamed). Length: {len(response_text)}")
                return {"response_text": response_text, "error": None}
        except Exception as e:
            print(f"{self.name}: Error during LLM call for response generation: {e}")
            error_response = f"Sorry, I encountered an error while generating the response: {e}"
            return {"response_text": error_response if not stream else None, "response_stream": None, "error": str(e)}

class MyFirstTool(Tool):
    def __init__(self):
        super().__init__(
            name="MyFirstTool",
            description="A simple example tool."
        )

    def __call__(self, input_param: str) -> str:
        return f"Tool executed with input: {input_param}"
